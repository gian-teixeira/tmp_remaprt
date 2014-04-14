#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <errno.h>
#include <assert.h>
#include <limits.h>
#include <arpa/inet.h>

#include "probedb.h"
#include "prober.h"
#include "path.h"
#include "log.h"
#include "pavl.h"
#include "tqueue.h"
#include "timespec.h"

#include "remap.h"

#define MAX_PATH_LENGTH 32
#define RMP_SHIFT_CHANGE INT_MAX
#define PATH_STR_BUF 65535

/*****************************************************************************
 * declarations
 ****************************************************************************/
struct remap {
	struct path *path;
	struct prober *prober;
	struct tqueue *tq;
	uint8_t startttl;

	struct probedb *db;
	int shifts[MAX_PATH_LENGTH];
};

static int remap_local(struct remap *rmp, int ttl, int minttl, int first);
static void remap_binary(struct remap *rmp, int l, int r);

static struct remap * remap_create(const struct opts *opts);
static void remap_destroy(struct remap *rmp);
static void remap_print_result(const struct remap *rmp);
static struct pathhop * remap_get_hop(struct remap *rmp, int ttl);

static void remap_cb_hop(uint8_t ttl, struct pathhop *hop, void *rmp);

static void remap_cb_iface(uint8_t ttl, uint8_t flowid, struct iface *i,
		void *rmp);


/*****************************************************************************
 * public implementations
 ****************************************************************************/
void remap(const struct opts *opts) /* {{{ */
{
	struct remap *rmp = remap_create(opts);
	if(!rmp) goto out;

	if(rmp->startttl > path_length(rmp->path)) goto out_length;

	struct pathhop *hop = remap_get_hop(rmp, rmp->startttl);

	while(pathhop_is_star(hop) && rmp->startttl > 0) {
		logd(LOG_INFO, "%s: unresp hop, decreasing ttl\n", __func__);
		rmp->startttl--;
		hop = remap_get_hop(rmp, rmp->startttl);
	}
	if(pathhop_is_star(hop)) goto out;

	/* TODO FIXME improve this so we probe backwards; make it so we can
	 * remap paths that become shorter. */

	int ttl = path_search_hop(rmp->path, hop, 0);
	if(ttl == rmp->startttl) {
		logd(LOG_INFO, "%s: no remap to do\n", __func__);
	} else if(ttl == -1) {
		logd(LOG_INFO, "%s: starting with local remap\n", __func__);
		remap_local(rmp, rmp->startttl, 0, 1);
	} else {
		logd(LOG_INFO, "%s: starting with binsearch\n", __func__);
		remap_binary(rmp, 0, rmp->startttl);
	}

	remap_print_result(rmp);
	remap_destroy(rmp);
	return;

	out_length:
	logd(LOG_INFO, "%s: can't start after old path length+1\n", __func__);
	out:
	remap_destroy(rmp);
	printf("remap failed. (try checking the logs)\n");
} /* }}} */

static int remap_local(struct remap *rmp, int ttl, int minttl, /* {{{ */
		int first)
{
	struct pathhop *hop;
	int branch = ttl;
	do {
		assert(branch >= 0);
		logd(LOG_INFO, "%s: looking for branch at ttl %d\n",
				__func__, branch);
		hop = remap_get_hop(rmp, branch);
		branch--;
	} while(pathhop_is_star(hop) ||
			path_search_hop(rmp->path, hop, 0) == -1);
	int p1branch = path_search_hop(rmp->path, hop, 0);
	branch++;

	int join = ttl + 1;
	int join_last_responsive = ttl;
	do {
		if(join > MAX_PATH_LENGTH-1) {
			logd(LOG_DEBUG, "path too long\n");
		}
		if((join - join_last_responsive > 4) && first) {
			/* there may be responsive hops after join if
			 * remap_local was called from the binsearch
			 * method.  first checks this is not
			 * the case before exiting. */
			logd(LOG_DEBUG, "too many STARs\n");
			break;
		}
		logd(LOG_INFO, "%s: looking for join at ttl %d\n", __func__,
				join);
		hop = remap_get_hop(rmp, join);
		if(!pathhop_is_star(hop)) join_last_responsive = join;
		join++;
		if(pathhop_contains_ip(hop, path_dst(rmp->path))) {
			logd(LOG_DEBUG, "hop contains dst\n");
			break;
		}
	} while((pathhop_is_star(hop) ||
			path_search_hop(rmp->path, hop, 0) < p1branch) &&
			join < MAX_PATH_LENGTH);
	join--;
	if(!pathhop_is_star(hop)) {
		/* we have a join point */
		int p1join = path_search_hop(rmp->path, hop, 0);
		rmp->shifts[join] = join - p1join;
	}

	for(int i = branch+1; i < join; i++) rmp->shifts[i] = RMP_SHIFT_CHANGE;

	if(rmp->shifts[branch] != branch - p1branch) {
		/* set rmp->shifts */
		remap_binary(rmp, minttl, branch);
	}

	return join;
} /* }}} */

static void remap_binary(struct remap *rmp, int l, int r) /* {{{ */
{
	struct pathhop *hop;
	int right_boundary = r;
	int p1left = 0;
	int p1right = MAX_PATH_LENGTH;

	while(r > l+1) {
		int i = (l + r)/2;
		hop = remap_get_hop(rmp, i);
		while(pathhop_is_star(hop)) {
			i--;
			hop = remap_get_hop(rmp, i);
		}
		if(i == l) {
			/* STARs made us reach the left limit, fallback */
			r = remap_local(rmp, (l + r)/2, l, 0);
			break;
		}

		int p1ttl = path_search_hop(rmp->path, hop, 0);
		logd(LOG_DEBUG, "CHECKME: i %d p1ttl %d shift %d\n",
				i, p1ttl, rmp->shifts[i]);
		if((i - p1ttl) == rmp->shifts[i]) {
			/* hop at expected position, change is to the right */
			l = i;
			p1left = p1ttl;
		} else if((p1left <= p1ttl) && (p1ttl <= p1right)) {
			/* hop at the wrong position; checking p1left and
			 * p1right is necessary because some times the old and
			 * new paths are all twisted (like abcde > aedcb). */
			r = i;
			p1right = p1ttl;
		} else {
			/* found a hop that is not in the old path */
			r = remap_local(rmp, i, l, 0);
			break;
		}
	}

	hop = probedb_find_hop(rmp->db, r);
	assert(hop);
	int shift = r - path_search_hop(rmp->path, hop, 0);
	for(int i = r; i <= right_boundary; i++) rmp->shifts[i] = shift;

	struct pavl_traverser trav;
	int pttl = 0;
	for(hop = pavl_t_first(&trav, rmp->db->hops); hop;
			hop = pavl_t_next(&trav)) {
		int ttl = pathhop_ttl(hop);
		if(ttl > right_boundary) continue;
		if(ttl <= r) continue;
		assert(rmp->shifts[ttl] != RMP_SHIFT_CHANGE);
		if(pathhop_is_star(hop)) continue;
		int true_shift = ttl - path_search_hop(rmp->path, hop, 0);
		if(true_shift != rmp->shifts[ttl]) {
			remap_binary(rmp, pttl, ttl);
		}
		pttl = ttl;
	}
} /* }}} */


/*****************************************************************************
 * static implementations
 ****************************************************************************/
static struct remap * remap_create(const struct opts *opts) /* {{{ */
{
	struct remap *rmp = malloc(sizeof(struct remap));
	if(!rmp) logea(__FILE__, __LINE__, NULL);
	rmp->path = path_create_copy(opts->path);
	if(!rmp->path) goto out;
	rmp->db = probedb_create();
	if(!rmp->db) goto out_path;
	rmp->prober = prober_create(opts->iface, path_dst(rmp->path),
			remap_cb_hop, remap_cb_iface, rmp);
	if(!rmp->prober) goto out_db;
	rmp->tq = tqueue_create();
	if(!rmp->tq) goto out_prober;

	rmp->startttl = opts->ttl;
	memset(rmp->shifts, 0, MAX_PATH_LENGTH*sizeof(int));

	return rmp;

	out_prober:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	prober_destroy(rmp->prober);
	out_db:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	probedb_destroy(rmp->db);
	out_path:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	path_destroy(rmp->path);
	out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	free(rmp);
	return NULL;
} /* }}} */

static void remap_destroy(struct remap *rmp) /* {{{ */
{
	logd(LOG_DEBUG, "entering %s\n", __func__);
	path_destroy(rmp->path);
	probedb_destroy(rmp->db);
	prober_destroy(rmp->prober);
	tqueue_destroy(rmp->tq);
	free(rmp);
} /* }}} */

static void remap_print_result(const struct remap *rmp) /* {{{ */
{
	struct pavl_traverser trav;
	char src[INET_ADDRSTRLEN], dst[INET_ADDRSTRLEN];
	char *hstr, *buf;

	if(!inet_ntop(AF_INET, path_srcptr(rmp->path), src, INET_ADDRSTRLEN)) {
		logea(__FILE__, __LINE__, NULL);
	}
	if(!inet_ntop(AF_INET, path_dstptr(rmp->path), dst, INET_ADDRSTRLEN)) {
		logea(__FILE__, __LINE__, NULL);
	}

	struct timespec ts;
	clock_gettime(CLOCK_REALTIME, &ts);
	unsigned time = ts.tv_sec;

	int bufsz = PATH_STR_BUF - 1;
	hstr = malloc(PATH_STR_BUF);
	if(!hstr) logea(__FILE__, __LINE__, NULL);
	hstr[0] = '\0';

	struct pathhop *rmphop = pavl_t_first(&trav, rmp->db->hops);
	for(int i = 0; i < path_length(rmp->path); i++) {
		assert(!rmphop || pathhop_ttl(rmphop) >= i);
		struct pathhop *strhop;
		if(rmphop && pathhop_ttl(rmphop) == i) {
			strhop = rmphop;
			rmphop = pavl_t_next(&trav);
		} else {
			strhop = pathhop_get_hop(rmp->path, i);
		}

		char *s = pathhop_tostr(strhop);
		strncat(hstr, s, bufsz);
		bufsz -= strlen(s);
		bufsz = (bufsz < 0) ? 0 : bufsz;
		strncat(hstr, "|", bufsz);
		bufsz--;
		bufsz = (bufsz < 0) ? 0 : bufsz;
		free(s);
	}

	assert(*(strchr(hstr, '\0') - 1) == '|');
	*(strchr(hstr, '\0') - 1) = '\0'; /* remove trailing pipe */

	buf = malloc(PATH_STR_BUF);
	if(!buf) logea(__FILE__, __LINE__, NULL);
	snprintf(buf, PATH_STR_BUF, "%s %s %d %s", src, dst, time, hstr);
	printf("%s\n", buf);
	free(hstr);
	free(buf);
} /* }}} */

struct pathhop * remap_get_hop(struct remap *rmp, int ttl) /* {{{ */
{
	struct pathhop *hop = probedb_find_hop(rmp->db, ttl);
	if(!hop) {
		prober_remap_hop(rmp->prober, ttl);
		struct pathhop * newhop = tqrecv(rmp->tq);
		assert(pathhop_ttl(newhop) == ttl);
		hop = probedb_add_hop(rmp->db, newhop);
		pathhop_destroy(newhop);
	}
	return hop;
} /* }}} */

static void remap_cb_hop(uint8_t ttl, struct pathhop *hop, void *vrmp) /*{{{*/
{
	struct remap *rmp = vrmp;
	logd(LOG_INFO, "%s reply for hop at TTL %d\n", __func__, (int)ttl);
	tqsend(rmp->tq, hop);
} /* }}} */

static void remap_cb_iface(uint8_t ttl, uint8_t flowid,  /* {{{ */
		struct iface *iface, void *vrmp)
{
	struct remap *rmp = vrmp;
	logd(LOG_INFO, "%s reply for iface %d,%d\n", __func__, (int)ttl,
			(int)flowid);

	/* FIXME TODO implement logic */
	char *str = iface_tostr(iface);
	fprintf(stdout, "%d:%d %s\n", (int)ttl, (int)flowid, str);
	free(str);
	/* probedb_add_iface(rmp->db, iface); iface_destroy(iface); */
}
