#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>

#include "timespec.h"
#include "log.h"
#include "pavl.h"
#include "map.h"
#include "dlist.h"
#include "path.h"

#define PATH_STR_BUF 65535

/*****************************************************************************
 * structs
 ****************************************************************************/
struct path
{ /* {{{ */
	uint32_t src;
	uint32_t dst;
	int length;
	struct timespec tstamp;
	struct pathhop **hops;
	struct pavl_table *ifaces;
	uint32_t flags;
	int alias;
};
struct pathhop
{
	struct timespec tstamp;
	int ttl;
	struct iface **ifaces;
	int nifaces;
};
struct iface
{
	uint32_t ip;
	struct timespec tstamp;
	int ttl;
	int *flowids;
	int nflowids;
	double rttmin;
	double rttavg;
	double rttmax;
	double rttvar;
	char *flags;
};
struct pathdb
{
	int max_aliases;
	struct pavl_map *dst2entry;
};
struct pathentry
{
	uint32_t dst;
	int maxalias;
	struct dlist *dl;
}; /* }}} */

/*****************************************************************************
 * struct path static declarations
 ****************************************************************************/
static void path_destroy_void(void *path);
static void path_check_reachability(struct path *p);
static void path_remove_end_stars(struct path *p);
static void path_add_ifaces(struct path *p, const struct pathhop *h);
static void path_diff_fill_missing(struct path *p1, struct path *p2, int ttl);
static void path_diff_join(const struct path *p1, const struct path *p2,
						   int oi, int ni, int *oj, int *nj, uint32_t flags);
static void path_diff_fix_stars(struct path *p1, struct path *p2,
								int *i1, int *i2, int *j1, int *j2, uint32_t flags);
static int path_diff_fix_stars_1hop(struct path *p1,
									struct path *p2, int i1, int i2, int j1, int j2);

/*****************************************************************************
 * struct pathhop static declarations
 ****************************************************************************/
static int pathhop_eq(const struct pathhop *h1,
					  const struct pathhop *h2, uint32_t flags);
static void pathhop_dst_first(struct pathhop *h, uint32_t dst);

/*****************************************************************************
 * struct iface static declarations
 ****************************************************************************/
static struct iface *iface_create(uint32_t dst, uint8_t ttl);
static int iface_cmp_ip_qsort(const void *v1, const void *v2);

/*****************************************************************************
 * struct pathdb static declarations
 ****************************************************************************/
static struct pathentry *pathdb_init_dst(struct pathdb *db, uint32_t dst);
static void pathdb_free_dst2entry(void *dst, void *entry, void *dummy);
static int pathdb_cmp_path(void *p1, void *p2, void *dummy);
static struct pathentry *pathdb_entry_create(uint32_t dst);
static void pathdb_entry_destroy(struct pathentry *entry);

struct pathhop *pathhop_get_hop(struct path *path, int ttl)
{
	return path->hops[ttl];
}

/*****************************************************************************
 * struct path public implementations
 ****************************************************************************/
struct path *path_create_copy(const struct path *path) /* {{{ */
{
	struct path *newp = malloc(sizeof(struct path));
	if (!newp)
		logea(__FILE__, __LINE__, NULL);
	newp->src = path->src;
	newp->dst = path->dst;
	newp->length = path->length;
	newp->tstamp = path->tstamp;
	newp->flags = path->flags;
	newp->alias = path->alias;

	newp->hops = malloc(newp->length * sizeof(struct pathhop *));
	if (!newp->hops)
		logea(__FILE__, __LINE__, NULL);
	newp->ifaces = pavl_create(iface_cmp_ip_data, NULL, NULL);
	if (!newp->ifaces)
		logea(__FILE__, __LINE__, "pavl_create failed");

	for (int i = 0; i < newp->length; i++)
	{
		newp->hops[i] = pathhop_create_copy(path->hops[i]);
		if (!newp->hops[i])
			logea(__FILE__, __LINE__, "unreachable");
		path_add_ifaces(newp, newp->hops[i]);
	}
	return newp;
} /* }}} */

struct path *path_create_str(const char *buf) /* {{{ */
{
	struct path *p;
	char src[80], dst[80], hstr[PATH_STR_BUF];
	uint32_t srcip, dstip;
	long tvsec;
	int r;

	r = sscanf(buf, "%79s %79s %ld %9127s\n", src, dst, &tvsec, hstr);
	if (r < 4)
		goto out;
	if (!inet_pton(AF_INET, src, &srcip))
		goto out;
	if (!inet_pton(AF_INET, dst, &dstip))
		goto out;

	p = path_create_str_hops(hstr, dstip);
	if (p == NULL)
		return NULL;
	p->tstamp.tv_sec = (time_t)tvsec;
	p->src = srcip;

	return p;

out_path:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	path_destroy(p);
out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	logd(LOG_DEBUG, "failed to parse path. line [%s]\n", buf);
	return NULL;
} /* }}} */

struct path *path_create_str_hops(const char *buf, uint32_t dst) /* {{{ */
{
	struct path *p;
	char hstr[PATH_STR_BUF];

	p = malloc(sizeof(struct path));
	if (!p)
		logea(__FILE__, __LINE__, NULL);

	p->src = UINT32_MAX;
	p->dst = dst;
	p->tstamp.tv_sec = 0;
	p->tstamp.tv_nsec = 0;
	p->hops = NULL;
	p->length = 0;\
	p->flags = 0;
	p->alias = -1;
	p->ifaces = pavl_create(iface_cmp_ip_data, NULL, NULL);
	if (!p->ifaces)
		logea(__FILE__, __LINE__, NULL);

	strncpy(hstr, buf, PATH_STR_BUF);

	{
		struct pathhop *hops[256];
		char *curr;
		char *ptr = hstr;
		for (curr = strsep(&ptr, "|"); curr; curr = strsep(&ptr, "|"))
		{
			hops[p->length] = pathhop_create_str(curr, p->tstamp, p->length);
			//printf("%d -- %s\n", p->length, curr);
			if (!hops[p->length])
				continue;
			path_add_ifaces(p, hops[p->length]);
			p->length++;
		}
		if (p->length == 0)
			goto out_ifaces;
		p->hops = malloc(p->length * sizeof(struct pathhop *));
		if (!p->hops)
			logea(__FILE__, __LINE__, NULL);
		memcpy(p->hops, hops, p->length * sizeof(struct pathhop *));
	}

	path_check_reachability(p);

	return p;

out_ifaces:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	logd(LOG_DEBUG, "path could not be parsed. line [%s]\n", buf);
	pavl_destroy(p->ifaces, NULL);
	free(p);
	return NULL;
} /* }}} */

struct path *path_create_str_safe(const char *buf, uint32_t dst) /* {{{ */
{
	struct path *p = path_create_str(buf);
	if (p)
		return p;
	char *star = "255.255.255.255:0:0.00,0.00,0.00,0.00:";
	char aux[1024];
	char addr[INET_ADDRSTRLEN];
	if (!inet_ntop(AF_INET, &dst, addr, INET_ADDRSTRLEN))
		goto out;
	sprintf(aux, "0.0.0.0 %s 0 %s|%s|%s", addr, star, star, star);
	return path_create_str(aux);

out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	return NULL;
} /* }}} */

void path_destroy(struct path *p) /* {{{ */
{
	int i;
	pavl_destroy(p->ifaces, iface_destroy_void);
	for (i = 0; i < p->length; i++)
		pathhop_destroy(p->hops[i]);
	free(p->hops);
	free(p);
} /* }}} */

char *path_tostr(const struct path *p) /* {{{ */
{
	char src[INET_ADDRSTRLEN], dst[INET_ADDRSTRLEN], *hstr, *buf;

	if (!inet_ntop(AF_INET, &p->src, src, INET_ADDRSTRLEN))
		goto out;
	if (!inet_ntop(AF_INET, &p->dst, dst, INET_ADDRSTRLEN))
		goto out;

	if (p->length > 0)
	{
		int i, bufsz;
		hstr = malloc(PATH_STR_BUF);
		if (!hstr)
			logea(__FILE__, __LINE__, NULL);
		hstr[0] = '\0';
		bufsz = PATH_STR_BUF - 1;
		for (i = 0; i < p->length; i++)
		{
			char *s = pathhop_tostr(p->hops[i]);
			strncat(hstr, s, bufsz);
			bufsz -= strlen(s);
			free(s);
			bufsz = (bufsz < 0) ? 0 : bufsz;
			strncat(hstr, "|", bufsz);
			bufsz--;
			bufsz = (bufsz < 0) ? 0 : bufsz;
		}
		assert(*(strchr(hstr, '\0') - 1) == '|');
		*(strchr(hstr, '\0') - 1) = '\0'; /* remove trailing pipe */
	}
	else
	{
		hstr = malloc(1);
		if (!hstr)
			logea(__FILE__, __LINE__, NULL);
		*hstr = '\0';
	}

	buf = malloc(PATH_STR_BUF);
	if (!buf)
		logea(__FILE__, __LINE__, NULL);
	snprintf(buf, PATH_STR_BUF, "%s %s %d %s", src, dst,
			 (int)p->tstamp.tv_sec, hstr);
	free(hstr);
	return buf;

out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	return NULL;
} /* }}} */

int path_diff(struct path *p1, struct path *p2, uint32_t flags) /* {{{ */
{
	int i1, i2, changes;
	/* we allow p1->src to be zero in case paristr crashed: */
	assert(p1->src == 0 || p2->src == 0 || p1->src == p2->src);
	assert(p1->dst == p2->dst);
	changes = 0;

	for (i1 = 0, i2 = 0; i1 < p1->length && i2 < p2->length; i1++, i2++)
	{
		int j1, j2;
		if (pathhop_eq(p1->hops[i1], p2->hops[i2], flags))
			continue;
		path_diff_join(p1, p2, i1, i2, &j1, &j2, flags);
		if (flags & PATH_DIFF_FLAG_FIX_STARS)
		{
			path_diff_fix_stars(p1, p2, &i1, &i2, &j1, &j2, flags);
		}
		if (j1 > i1 || j2 > i2)
			changes++;
		i1 = j1 - 1; /* i1 is incremented by the for loop */
		i2 = j2 - 1;
	}

	if (flags & PATH_DIFF_FLAG_FILL_MISSING && changes == 0)
	{
		assert(i1 == i2);
		path_diff_fill_missing(p1, p2, i1);
	}
	else if (i1 != p1->length || i2 != p2->length)
	{
		changes++;
	}

	return changes;
} /* }}} */

int path_check_change(const struct path *p, uint8_t ttl, /* {{{ */
					  uint8_t flowid, uint32_t ip)
{
	struct pathhop *hop = ttl < p->length ? p->hops[ttl] : NULL;

	char addr[INET_ADDRSTRLEN];
	if (!inet_ntop(AF_INET, &ip, addr, INET_ADDRSTRLEN))
		goto out;

	char *hopstr = hop ? pathhop_tostr(hop) : strdup("NULL");
	if (!hopstr)
		goto out;
	logd(LOG_EXTRA, "%s: ip=%s hop=%s\n", __func__, addr, hopstr);
	free(hopstr);

	if (ip == UINT32_MAX)
		return 0; /* no information in probe */
	if (hop == NULL)
		return 1; /* path has grown */
	if (pathhop_is_star(hop))
		return 0; /* anything goes */

	for (int i = 0; i < hop->nifaces; i++)
	{
		struct iface *iface = hop->ifaces[i];
		if (iface->ip == ip)
		{
			return 0;
			/* The following can be used to also check if [iface]
			 * contains [flowid]. It's commented out because we
			 * are not sure if flowids are stable over time or if
			 * the confirm module is sending the same flowids
			 * that paris-traceroute is sending.
			for(int j = 0; j < iface->nflowids; j++) {
				if(iface->flowids[j] == flowid) return 0;
			}
			logd(LOG_INFO, "%s: change due to flowid\n", __func__);
			 */
		}
	}

	return 1;

out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	return -1;
} /* }}} */

int path_search_hop(const struct path *p, const struct pathhop *hop, /* {{{ */
					uint32_t flags)
{
	// if(pathhop_is_star(hop))
	// 	logd(LOG_DEBUG, "%s: STAR %d\n", __func__, pathhop_ttl(hop));
	assert(!pathhop_is_star(hop));
	for (int i = 0; i < p->length; i++)
	{
		if (pathhop_eq(p->hops[i], hop, flags))
			return i;
	}
	if (pathhop_contains_ip(hop, p->dst) &&
		!(p->flags & PATH_FLAG_NO_REACHABILITY))
	{
		logd(LOG_DEBUG, "%s: hopdst w reach, returning %d\n",
			 __func__, p->length - 1);
		return p->length - 1;
	}
	return -1;
} /* }}} */

uint32_t path_dst(const struct path *p) { return p->dst; }
const uint32_t *path_dstptr(const struct path *p) { return &p->dst; }
const uint32_t *path_srcptr(const struct path *p) { return &p->src; }
int path_length(const struct path *p) { return p->length; }
struct timespec path_tstamp(const struct path *p) { return p->tstamp; }
struct pavl_table *path_interfaces(const struct path *p) { return p->ifaces; }
int path_alias(const struct path *p) { return p->alias; }
void path_alias_set(struct path *p, int alias) { p->alias = alias; }

/*****************************************************************************
 * struct path static implementations
 ****************************************************************************/
static void path_destroy_void(void *p) /* {{{ */
{
	path_destroy(p);
} /* }}} */

static void path_diff_join(const struct path *p1, /* {{{ */
						   const struct path *p2,
						   int oi, int ni, int *oj, int *nj, uint32_t flags)
{
	int noi, nni;
	for (nni = ni; nni < p2->length; nni++)
	{
		if (pathhop_is_star(p2->hops[nni]))
			continue;
		for (noi = oi; noi < p1->length; noi++)
		{
			if (pathhop_eq(p1->hops[noi], p2->hops[nni], flags))
			{
				*oj = noi;
				*nj = nni;
				return;
			}
		}
	}
	assert(!(flags & PATH_DIFF_FLAG_IGNORE_BALANCERS) ||
		   p1->flags & PATH_FLAG_NO_REACHABILITY ||
		   p2->flags & PATH_FLAG_NO_REACHABILITY);
	*oj = p1->length;
	*nj = p2->length;
} /* }}} */

static void path_diff_fix_stars(struct path *p1, struct path *p2, /* {{{ */
								int *i1, int *i2, int *j1, int *j2, uint32_t flags)
{
	int i, j, threshold;
	threshold = (*j1 - *i1 < *j2 - *i2) ? *j1 - *i1 : *j2 - *i2;
	for (i = 0; i < threshold; i++)
	{
		if (!path_diff_fix_stars_1hop(p1, p2, *i1 + i, *i2 + i, *j1, *j2))
		{
			break;
		}
	}
	*i1 += i;
	*i2 += i;
	threshold = (*j1 - *i1 < *j2 - *i2) ? *j1 - *i1 : *j2 - *i2;
	for (j = 0; j < threshold; j++)
	{
		int ttl1 = *j1 - j - 1;
		int ttl2 = *j2 - j - 1;
		if (!path_diff_fix_stars_1hop(p1, p2, ttl1, ttl2, *j1, *j2))
		{
			break;
		}
	}
	*j1 -= j;
	*j2 -= j;

	assert(*i1 <= *j1 && *i2 <= *j2);
	path_check_reachability(p1);
	path_check_reachability(p2);
} /* }}} */

static int path_diff_fix_stars_1hop(struct path *p1, /* {{{ */
									struct path *p2, int i1, int i2, int j1, int j2)
{
	struct pathhop *h1, *h2, *srch, *newh;
	struct path *starp;
	int stari, starj;
	
	h1 = p1->hops[i1];
	h2 = p2->hops[i2];
	if (pathhop_is_star(h1) && pathhop_is_star(h2))
		return 1;
	if (!pathhop_is_star(h1) && !pathhop_is_star(h2))
		return 0;

	if (pathhop_is_star(h1))
	{
		starp = p1;
		stari = i1;
		starj = j1;
		srch = h2;
	}
	else
	{
		starp = p2;
		stari = i2;
		starj = j2;
		srch = h1;
	}

	/* not fixing with load balancer: */
	if (srch->nifaces > 1)
		return 0;
	/* not fixing with interface already in another hop: */
	if (pavl_find(starp->ifaces, srch->ifaces[0]))
		return 0;
	/* not fixing with dst if it's not the last hop in the path: */
	if (srch->ifaces[0]->ip == starp->dst && stari + 1 != starj)
		return 0;

	newh = pathhop_create_copy(srch);
	path_set_hop(starp, stari, newh);
	return 1;
} /* }}} */

static void path_diff_fill_missing(struct path *p1, /* {{{ */
								   struct path *p2, int ttl)
{
	struct path *shorter, *longer;
	struct pathhop **hops;
	assert(ttl == p1->length || ttl == p2->length);

	shorter = (p1->length < p2->length) ? p1 : p2;
	longer = (p1->length < p2->length) ? p2 : p1;

	hops = malloc(longer->length * sizeof(struct pathhop *));
	if (!hops)
		logea(__FILE__, __LINE__, NULL);
	memset(hops, 0, longer->length * sizeof(struct pathhop *));
	memcpy(hops, shorter->hops, shorter->length * sizeof(struct pathhop *));
	free(shorter->hops);
	shorter->hops = hops;
	shorter->length = longer->length;

	for (; ttl < longer->length; ttl++)
	{
		struct pathhop *newh;
		newh = pathhop_create_copy(longer->hops[ttl]);
		path_set_hop(shorter, ttl, newh);
	}

	return;
} /* }}} */

static void path_check_reachability(struct path *p) /* {{{ */
{
	path_remove_end_stars(p);
	struct pathhop *last = (p->length > 0) ? p->hops[p->length - 1] : NULL;
	if (last && pathhop_contains_ip(last, p->dst))
	{
		p->flags &= ~PATH_FLAG_NO_REACHABILITY;
		/* asymmetric load balancers may put extra IPs on the last hop
		 * in a path. this is to ensure we can path_diff_join two
		 * different paths with reachability.  */
		pathhop_dst_first(last, p->dst);
	}
	else
	{
		p->flags |= PATH_FLAG_NO_REACHABILITY;
		/* not scheduling probes where we dont't measure them: */
		if (p->length >= 30)
			return;
		/* otherwise check for incrase in path length: */
		struct iface *dstif = iface_create(p->dst, p->length);
		struct iface *oldif = pavl_insert(p->ifaces, dstif);
		if (oldif)
			iface_destroy(dstif);
	}
} /* }}} */

void path_set_hop(struct path *p, int ttl, struct pathhop *h) /* {{{ */
{
	assert(p->hops[ttl] == NULL || pathhop_is_star(p->hops[ttl]) || ttl == 0);
	path_add_ifaces(p, h);
	/* no path_del_ifaces because current hop is either NULL or a STAr */
	if (p->hops[ttl])
		pathhop_destroy(p->hops[ttl]);
	h->ttl = ttl;
	p->hops[ttl] = h;
} /* }}} */

static void path_add_ifaces(struct path *p, const struct pathhop *h) /* {{{ */
{
	int i;
	if (pathhop_is_star(h))
		return;
	for (i = 0; i < h->nifaces; i++)
	{
		struct iface *newif = iface_create_copy(h->ifaces[i]);
		struct iface *oldif = pavl_insert(p->ifaces, newif);
		if (oldif)
			iface_destroy(newif);
	}
} /* }}} */

static void path_remove_end_stars(struct path *p) /* {{{ */
{
	while (p->length > 0 && pathhop_is_star(p->hops[p->length - 1]))
	{
		pathhop_destroy(p->hops[p->length - 1]);
		p->length--;
	}
} /* }}} */

/*****************************************************************************
 * pathhop implementations
 ****************************************************************************/
struct pathhop *pathhop_create_copy(const struct pathhop *h) /* {{{ */
{
	int i;
	struct pathhop *newh;

	newh = malloc(sizeof(struct pathhop));
	if (!newh)
		logea(__FILE__, __LINE__, NULL);

	newh->tstamp = h->tstamp;
	newh->ttl = h->ttl;
	newh->nifaces = h->nifaces;
	newh->ifaces = malloc(newh->nifaces * sizeof(struct iface *));
	if (!newh->ifaces)
		logea(__FILE__, __LINE__, NULL);
	
	for (i = 0; i < newh->nifaces; i++)
	{
		newh->ifaces[i] = iface_create_copy(h->ifaces[i]);
	}

	return newh;
} /* }}} */

struct pathhop *pathhop_create_str(const char *cbuf, /* {{{ */
								   struct timespec tstamp, int ttl)
{
	struct pathhop *hop;
	struct iface *ifaces[256]; /* Widest balancer seen is 32. */
	char *ifs, *buf, *ptr;
	int i;

	buf = strdup(cbuf);
	if (!buf)
		logea(__FILE__, __LINE__, NULL);
	ptr = buf;

	hop = malloc(sizeof(struct pathhop));
	if (!hop)
		logea(__FILE__, __LINE__, NULL);

	hop->tstamp = tstamp;
	hop->ttl = ttl;
	hop->nifaces = 0;
	for (ifs = strsep(&ptr, ";"); ifs; ifs = strsep(&ptr, ";"))
	{
		ifaces[hop->nifaces] = iface_create_str(ifs, tstamp, ttl);
		if (!ifaces[hop->nifaces])
			goto out_ifaces;
		hop->nifaces++;
	}
	
	hop->ifaces = malloc(hop->nifaces * sizeof(struct iface *));
	if (!hop->ifaces)
		logea(__FILE__, __LINE__, NULL);
	memcpy(hop->ifaces, ifaces, hop->nifaces * sizeof(struct iface *));
	qsort(hop->ifaces, hop->nifaces, sizeof(struct iface *),
		  iface_cmp_ip_qsort);

	free(buf);

	return hop;

out_ifaces:
	loge(LOG_FATAL, __FILE__, __LINE__);
	for (i = 0; i < hop->nifaces; i++)
		iface_destroy(ifaces[i]);
	free(hop);
	free(buf);
	return NULL;
} /* }}} */

void pathhop_destroy(struct pathhop *h) /* {{{ */
{
	int i;
	for (i = 0; i < h->nifaces; i++)
		iface_destroy(h->ifaces[i]);
	free(h->ifaces);
	free(h);
} /* }}} */

void pathhop_destroy_void(void *pathhop, void *dummy) /* {{{ */
{
	pathhop_destroy((struct pathhop *)pathhop);
} /* }}} */

char *pathhop_tostr(const struct pathhop *h) /* {{{ */
{
	char *buf;
	int i, bufsz;

	buf = malloc(PATH_STR_BUF);
	if (!buf)
		logea(__FILE__, __LINE__, NULL);
	buf[0] = '\0';
	bufsz = PATH_STR_BUF - 1;

	for (i = 0; i < h->nifaces; i++)
	{
		char *istr = iface_tostr(h->ifaces[i]);
		if (!istr)
			break;
		strncat(buf, istr, bufsz);
		bufsz -= strlen(istr);
		free(istr);
		if (bufsz <= 0)
			goto out_bufsz;
		strncat(buf, ";", bufsz);
		bufsz -= 1;
		if (bufsz <= 0)
			goto out_bufsz;
	}

	if (strlen(buf) > 0)
	{
		assert(*(strchr(buf, '\0') - 1) == ';');
		*(strchr(buf, '\0') - 1) = '\0'; /* rm trailing semicolon */
	}
	return buf;

out_bufsz:
	logd(LOG_WARN, "%s:%d: bufsz == 0.\n", __FILE__, __LINE__);
	sprintf(buf, "255.255.255.255:0:0.00,0.00,0.00,0.00:");
	return buf;
} /* }}} */

int pathhop_is_star(const struct pathhop *h) /* {{{ */
{
	if (h->nifaces > 1)
		return 0;
	if (h->ifaces[0]->ip != UINT32_MAX)
		return 0;
	return 1;
} /* }}} */

int pathhop_ttl(const struct pathhop *h)
{
	if (h != NULL)
		return h->ttl;
	else
		return (-1);
}

int *pathhop_ttlptr(struct pathhop *hop)
{
	if (hop != NULL)
		return &(hop->ttl);
	else
		return NULL;
}

int pathhop_contains_ip(const struct pathhop *h, uint32_t ip) /* {{{ */
{
	int i;
	for (i = 0; i < h->nifaces; i++)
	{
		if (h->ifaces[i]->ip == ip)
			return 1;
	}
	return 0;
} /* }}} */

static int pathhop_eq(const struct pathhop *h1, /* {{{ */
					  const struct pathhop *h2, uint32_t flags)
{
	if (flags & PATH_DIFF_FLAG_IGNORE_BALANCERS)
	{
		return h1->ifaces[0]->ip == h2->ifaces[0]->ip;
	}
	else
	{
		int i;
		if (h1->nifaces != h2->nifaces)
			return 0;
		for (i = 0; i < h1->nifaces; i++)
		{
			if (h1->ifaces[i]->ip != h2->ifaces[i]->ip)
				return 0;
		}
	}
	return 1;
} /* }}} */

static void pathhop_dst_first(struct pathhop *h, uint32_t dst) /* {{{ */
{
	assert(pathhop_contains_ip(h, dst));
	int di = 0;
	/* why, god, why is search.h so useless? */
	for (; di < h->nifaces && h->ifaces[di]->ip != dst; di++)
		;
	assert(di < h->nifaces);

	struct iface *tmp = h->ifaces[0];
	h->ifaces[0] = h->ifaces[di];
	h->ifaces[di] = tmp;

	qsort(h->ifaces + 1, h->nifaces - 1, sizeof(struct iface *),
		  iface_cmp_ip_qsort);
} /* }}} */

int pathhop_nifaces(struct pathhop *h)
{
	return h->nifaces;
}

/*****************************************************************************
 * iface implementations
 ****************************************************************************/
struct iface *iface_create_copy(const struct iface *orig) /* {{{ */
{
	struct iface *iface = malloc(sizeof(struct iface));
	if (!iface)
		logea(__FILE__, __LINE__, NULL);
	memcpy(iface, orig, sizeof(struct iface));
	iface->flowids = malloc(iface->nflowids * sizeof(int));
	if (!iface->flowids)
		logea(__FILE__, __LINE__, NULL);
	memcpy(iface->flowids, orig->flowids, iface->nflowids * sizeof(int));
	if (orig->flags)
		iface->flags = strdup(orig->flags);
	return iface;
} /* }}} */

struct iface *iface_create_str(const char *buf, /* {{{ */
							   struct timespec tstamp, int ttl)
{
	// 150.164.11.94:0:33.62,42.64,49.93,6.86:
	struct iface *iface;
	char addr[80], flowids[1024], flags[1024];
	int r;

	iface = malloc(sizeof(struct iface));
	if (!iface)
		logea(__FILE__, __LINE__, NULL);

	iface->tstamp = tstamp;
	iface->ttl = ttl;
	iface->flags = NULL;

	flags[0] = '\0';
	r = sscanf(buf, "%80[^:]:%1023[^:]:%lf,%lf,%lf,%lf:%1023s", addr,
			   flowids, &iface->rttmin, &iface->rttavg,
			   &iface->rttmax, &iface->rttvar, flags);
	if (r < 6)
		goto out_iface;

	if (!inet_pton(AF_INET, addr, &iface->ip))
		goto out_iface;

	{
		int ids[256];
		char *id, *ptr;
		iface->nflowids = 0;
		ptr = flowids;
		for (id = strsep(&ptr, ","); id; id = strsep(&ptr, ","))
		{
			ids[iface->nflowids] = atoi(id);
			iface->nflowids++;
		}
		iface->flowids = malloc(iface->nflowids * sizeof(int));
		if (!iface->flowids)
			logea(__FILE__, __LINE__, NULL);
		memcpy(iface->flowids, ids, iface->nflowids * sizeof(int));
	}

	if (strlen(flags) > 0)
	{
		iface->flags = strdup(flags);
		if (!iface->flags)
			logea(__FILE__, __LINE__, NULL);
	}

	return iface;

out_iface:
	loge(LOG_FATAL, __FILE__, __LINE__);
	free(iface);
	return NULL;
} /* }}} */

void iface_destroy(struct iface *iface) /* {{{ */
{
	if (iface->flags)
		free(iface->flags);
	free(iface->flowids);
	free(iface);
} /* }}} */

void iface_destroy_void(void *vi, void *dummy) /* {{{ */
{
	iface_destroy(vi);
} /* }}} */

char *iface_tostr(const struct iface *iface) /* {{{ */
{
	char flowids[1024], addr[INET_ADDRSTRLEN];
	char *buf;
	int i, bufsz;

	if (!inet_ntop(AF_INET, &iface->ip, addr, INET_ADDRSTRLEN))
		goto out;

	flowids[0] = '\0';
	bufsz = 1024 - 1;
	for (i = 0; i < iface->nflowids; i++)
	{
		char id[80];
		id[0] = '\0';
		snprintf(id, 80, "%d", iface->flowids[i]);
		strncat(flowids, id, bufsz);
		bufsz -= strlen(id);
		bufsz = (bufsz < 0) ? 0 : bufsz;
		strncat(flowids, ",", bufsz);
		bufsz--;
		bufsz = (bufsz < 0) ? 0 : bufsz;
	}
	assert(*(strchr(flowids, '\0') - 1) == ',');
	*(strchr(flowids, '\0') - 1) = '\0'; /* remove trailing comma */

	buf = malloc(1024);
	if (!buf)
		logea(__FILE__, __LINE__, NULL);
	buf[0] = '\0';
	snprintf(buf, 1024, "%s:%s:%.2f,%.2f,%.2f,%.2f:%s",
			 addr, flowids, iface->rttmin, iface->rttavg,
			 iface->rttmax, iface->rttvar,
			 (iface->flags ? iface->flags : ""));

	return buf;

out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	return NULL;
} /* }}} */

uint32_t iface_ip(const struct iface *iff) { return iff->ip; }

int iface_is_star(const struct iface *iff) { return iff->ip == UINT32_MAX; }

int iface_ttl(const struct iface *iface) { return iface->ttl; }

int iface_first_flowid(const struct iface *iface) { return iface->flowids[0]; }

double iface_rttavg(const struct iface *iface) { return iface->rttavg; }

double pathhop_rttavg_sample(const struct pathhop *hop) { 
	return iface_rttavg(hop->ifaces[0]);	
}


int iface_random_flowid(const struct iface *iface)
{ /* {{{ */
	int i = drand48() * iface->nflowids;
	return iface->flowids[i];
} /* }}} */

int iface_cmp_ip(const void *v1, const void *v2) /* {{{ */
{
	struct iface *i1 = (struct iface *)v1;
	struct iface *i2 = (struct iface *)v2;
	return (i1->ip > i2->ip) - (i1->ip < i2->ip);
} /* }}} */

int iface_cmp_ip_data(const void *v1, const void *v2, void *dummy) /* {{{ */
{
	return iface_cmp_ip(v1, v2);
} /* }}} */

int iface_cmp_ip_ttl_data(const void *v1, const void *v2, void *dummy) /* {{{ */
{
	struct iface *i1 = (struct iface *)v1;
	struct iface *i2 = (struct iface *)v2;
	return 2 * ((i1->ip > i2->ip) - (i1->ip < i2->ip)) +
		   (i1->ttl > i2->ttl) - (i1->ttl < i2->ttl);
} /* }}} */

void iface_logd(unsigned verbosity, const struct iface *iface) /* {{{ */
{
	char *s = iface_tostr(iface);
	if (!s)
		return;
	logd(verbosity, "%s", s);
	free(s);
} /* }}} */

void iface_logl(unsigned verbosity, const struct iface *iface) /* {{{ */
{
	char *s = iface_tostr(iface);
	if (!s)
		return;
	logd(verbosity, "%s\n", s);
	free(s);
} /* }}} */

static struct iface *iface_create(uint32_t dst, uint8_t ttl) /* {{{ */
{
	struct iface *iface;
	iface = iface_create_str("255.255.255.255:0:0.0,0.0,0.0,0.0:",
							 (struct timespec){0, 0}, ttl);
	iface->ip = dst;
	return iface;
} /* }}} */

static int iface_cmp_ip_qsort(const void *v1, const void *v2) /* {{{ */
{
	struct iface *i1 = *(struct iface **)v1;
	struct iface *i2 = *(struct iface **)v2;
	return (i1->ip > i2->ip) - (i1->ip < i2->ip);
} /* }}} */

/*****************************************************************************
 * pathdb implementations
 ****************************************************************************/
struct pathdb *pathdb_create(int max_aliases) /* {{{ */
{
	struct pathdb *db = malloc(sizeof(struct pathdb));
	if (!db)
		logea(__FILE__, __LINE__, NULL);
	db->max_aliases = max_aliases;
	db->dst2entry = map_create(map_cmp_uint32, NULL, NULL);
	if (!db->dst2entry)
		logea(__FILE__, __LINE__, "map_create failed");
	return db;
} /* }}} */

void pathdb_destroy(struct pathdb *db)
{ /* {{{ */
	map_destroy(db->dst2entry, pathdb_free_dst2entry);
	free(db);
} /* }}} */

void pathdb_alias(struct pathdb *db, struct path *p) /* {{{ */
{
	struct path *newp, *oldp;
	struct pathentry *e = pathdb_init_dst(db, p->dst);
	newp = path_create_copy(p);
	oldp = dlist_find_remove(e->dl, newp, pathdb_cmp_path, NULL);
	if (oldp)
	{
		dlist_push_right(e->dl, oldp);
		assert(e->dl->count <= db->max_aliases);
		path_destroy(newp);
		p->alias = oldp->alias;
	}
	else
	{
		dlist_push_right(e->dl, newp);
		while (e->dl->count > db->max_aliases)
		{
			path_destroy(dlist_pop_left(e->dl));
		}
		newp->alias = e->maxalias;
		e->maxalias++;
		p->alias = newp->alias;
	}
} /* }}} */

int pathdb_naliases(struct pathdb *db, uint32_t dst) /* {{{ */
{
	struct pathentry *e = pathdb_init_dst(db, dst);
	return e->maxalias;
} /* }}} */

static int pathdb_cmp_path(void *p1, void *p2, void *dummy) /* {{{ */
{
	uint32_t flags = PATH_DIFF_FLAG_FIX_STARS |
					 PATH_DIFF_FLAG_FILL_MISSING;
	return path_diff(p1, p2, flags);
} /* }}} */

static void pathdb_free_dst2entry(void *dst, void *entry, void *dummy) /* {{{ */
{
	struct pathentry *e = (struct pathentry *)entry;
	assert(dst == &(e->dst));
	pathdb_entry_destroy(e);
} /* }}} */

static struct pathentry *pathdb_init_dst(struct pathdb *db, uint32_t dst) /* {{{ */
{
	struct pathentry *e = map_find(db->dst2entry, &dst, NULL);
	if (!e)
	{
		e = pathdb_entry_create(dst);
		map_assert_insert(db->dst2entry, &(e->dst), e);
	}
	return e;
} /* }}} */

static struct pathentry *pathdb_entry_create(uint32_t dst) /* {{{ */
{
	struct pathentry *e = malloc(sizeof(struct pathentry));
	if (!e)
		logea(__FILE__, __LINE__, NULL);
	e->dst = dst;
	e->maxalias = 0;
	e->dl = dlist_create();
	if (!e->dl)
		logea(__FILE__, __LINE__, "dlist_create failed");
	return e;
} /* }}} */

static void pathdb_entry_destroy(struct pathentry *entry) /* {{{ */
{
	dlist_destroy(entry->dl, path_destroy_void);
	free(entry);
} /* }}} */
