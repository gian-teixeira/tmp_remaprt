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
#include "path.h"

#include "remap.h"

#define MAX_PATH_LENGTH 32
#define RMP_SHIFT_CHANGE INT_MAX
#define PATH_STR_BUF 65535

static int measured_ttl[50] = {0};

/*****************************************************************************
 * declarations
 ****************************************************************************/
struct remap {
	/* New members that supports offline remaps */
	struct path *old_path;
	struct path *new_path;

	struct prober *prober;
	struct tqueue *tq;
	uint8_t startttl;
	int total_probes_sent;

	struct probedb *db;
	int shifts[MAX_PATH_LENGTH];
};

static int remap_local(struct remap *rmp, int ttl, int minttl, int first);
static void remap_binary(struct remap *rmp, int l, int r);

static struct remap * remap_create(const struct opts *opts);
static void remap_destroy(struct remap *rmp);
static void remap_print_result(const struct remap *rmp);
static struct pathhop * remap_get_hop(struct remap *rmp, int ttl);

static void remap_cb_hop(uint8_t ttl, int nprobes, struct pathhop *hop,
		void *rmp);

static void remap_cb_iface(uint8_t ttl, uint8_t flowid, struct iface *i,
		void *rmp);

/*****************************************************************************
 * public implementations
 ****************************************************************************/
void remap(const struct opts *opts) /* {{{ */
{
	struct remap *rmp = remap_create(opts);
	if(!rmp){ 
		logd(LOG_INFO, "%s: cannot create struct remap\n", __func__);
		goto out;
	}
	if(rmp->startttl > path_length(rmp->old_path)) goto out_length;

	/* Remap origin */
	struct pathhop *hop = remap_get_hop(rmp, rmp->startttl);

	/* If the router at start ttl can not be accessed, decrement the position
	   until the access is possible. If no router responds, the remap is
	   not executed */
	while(pathhop_is_star(hop) && rmp->startttl > 0) {
		logd(LOG_INFO, "%s: unresp hop, decreasing ttl\n", __func__);
		rmp->startttl--;
		hop = remap_get_hop(rmp, rmp->startttl);
	}
	if(pathhop_is_star(hop)){
		logd(LOG_INFO, "%s: cannot access hop\n", __func__);
	       	goto out;
	}
	

	/* Position if the origin in the old path. If it is equal to the position
	   in the new path, no remap is necessary. If the hop was not present, then
	   it can be used to start the remap itself. Else, the binary is used to
	   find a hop that fit the last condition */
	int ttl = path_search_hop(rmp->old_path, hop, 0);
	
	if(ttl == rmp->startttl) {
		/* The hop is already correct */
		logd(LOG_INFO, "%s: no remap to do\n", __func__);
		
		struct timespec ts;
		char *buf = malloc(PATH_STR_BUF);
		char *src = pathhop_tostr(pathhop_get_hop(rmp->old_path, 0));
		char *dst = pathhop_tostr(pathhop_get_hop(rmp->old_path, path_length(rmp->old_path)-1));
		char *hopstr = path_tostr(rmp->old_path);

		clock_gettime(CLOCK_REALTIME, &ts);
		if(!buf) logea(__FILE__, __LINE__, NULL);
		snprintf(buf, PATH_STR_BUF, "%d %s %s %d %s %d %d %d", 
			 	 rmp->total_probes_sent,
			 	 src, dst,
				 ts.tv_sec, 
				 hopstr);
		printf("%s\n", buf);

		free(hopstr);
		free(src);
		free(dst);
		free(buf);	
	}
	else {
		if(ttl == -1) {
			/* The hop is wrong itself. No search necessary */
			logd(LOG_INFO, "%s: starting with local remap\n", __func__);
			remap_local(rmp, rmp->startttl, 0, 1);
		} 
		else {
			/* The hop is shifted. Search used */
			logd(LOG_INFO, "%s: starting with binsearch\n", __func__);
			remap_binary(rmp, 0, rmp->startttl);
		}
		remap_print_result(rmp);
	}

	/* Taking the garbage and handle with the errors */
	remap_destroy(rmp);
	return;

	

	out_length:
	logd(LOG_INFO, "%s: can't start after old path length+1\n", __func__);
	out:
	remap_destroy(rmp);
	printf("remap failed. (try checking the logs)\n");
} /* }}} */

static int remap_local(struct remap *rmp, int ttl, int minttl, int first)
{\
	struct pathhop *hop;
	int branch = ttl;

	/* Finds the ttl where the old path and new path diverge.
	   For that, walks on the path in left direction. */
	do {
		assert(branch >= 0);
		logd(LOG_INFO, "%s: looking for branch at ttl %d\n", __func__, branch);
		hop = remap_get_hop(rmp, branch);
		branch--;
	} while(pathhop_is_star(hop) || 
			path_search_hop(rmp->old_path, hop, 0) == -1);
	
	/* Saves the position of the branch in the old path */
	int oldpath_branch_ttl = path_search_hop(rmp->old_path, hop, 0);
	branch++;
	
	/* Like the last task, finds the ttl where the paths converge.
	   Works in right direction. */
	int join = ttl + 1;
	int join_last_responsive = ttl;

	do {
		if(join > MAX_PATH_LENGTH-1) logd(LOG_DEBUG, "path too long\n");
		if((join - join_last_responsive > 4) && first) {
			/* there may be responsive hops after join if
			 * remap_local was called from the binsearch
			 * method.  first checks this is not
			 * the case before exiting. */
			logd(LOG_DEBUG, "too many STARs\n");
			break;
		}

		logd(LOG_INFO, "%s: looking for join at ttl %d\n", __func__, join);
		
		hop = remap_get_hop(rmp, join);
		if(!pathhop_is_star(hop)) join_last_responsive = join;
		join++;

		/* If the current join contains the destiny IP, is not necessary
		   to continue searching for another join hop. */
		if(pathhop_contains_ip(hop, path_dst(rmp->old_path))) {
			logd(LOG_DEBUG, "hop contains dst\n");
			break;
		}
	} while((pathhop_is_star(hop) ||
			path_search_hop(rmp->old_path, hop, 0) < oldpath_branch_ttl) &&
			join < MAX_PATH_LENGTH);

	join--;

	

	if(!pathhop_is_star(hop)) {
		/* we have a join point */
		int oldpath_join_ttl = path_search_hop(rmp->old_path, hop, 0);
		rmp->shifts[join] = join - oldpath_join_ttl;
	}

	for(int i = branch+1; i < join; i++) rmp->shifts[i] = RMP_SHIFT_CHANGE;

	if(rmp->shifts[branch] != branch - oldpath_branch_ttl) {
		/* set rmp->shifts */
		remap_binary(rmp, minttl, branch);
	}
	
	return join;
}

static void remap_binary(struct remap *rmp, int l, int r) /* {{{ */
{
	printf("STARTED : %s\n", __func__);
	fflush(stdout);

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

		int p1ttl = path_search_hop(rmp->old_path, hop, 0);
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
	int shift = r - path_search_hop(rmp->old_path, hop, 0);
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
		int true_shift = ttl - path_search_hop(rmp->old_path, hop, 0);
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

	rmp->old_path = path_create_copy(opts->old_path);
	rmp->new_path = path_create_copy(opts->new_path);
	if(!rmp->old_path) goto out;

	rmp->db = probedb_create();
	if(!rmp->db) goto out_path;

	rmp->prober = prober_create(opts, remap_cb_hop, remap_cb_iface, rmp);
	if(!rmp->prober) goto out_db;

	rmp->tq = tqueue_create();
	if(!rmp->tq) goto out_prober;

	/* -1 because we do all computation counting from zero */
	rmp->startttl = opts->ttl - 1;
	rmp->total_probes_sent = 0;
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
	path_destroy(rmp->old_path);
	out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	free(rmp);
	return NULL;
} /* }}} */

static void remap_destroy(struct remap *rmp) /* {{{ */
{
	logd(LOG_DEBUG, "entering %s\n", __func__);
	path_destroy(rmp->old_path);
	if(rmp->new_path) {
		path_destroy(rmp->new_path);
	}
	probedb_destroy(rmp->db);
	prober_destroy(rmp->prober);
	tqueue_destroy(rmp->tq);
	free(rmp);
} /* }}} */

static void remap_result_append_hop(char *buf, int *bufsz, struct pathhop *hop)
{
	char *hop_str = pathhop_tostr(hop);
	strncat(buf, hop_str, *bufsz);
	*bufsz -= strlen(hop_str);
	*bufsz = (*bufsz < 0) ? 0 : *bufsz;
	strncat(buf, "|", *bufsz);
	*bufsz -= 1;
	*bufsz = (*bufsz < 0) ? 0 : *bufsz;
	free(hop_str);
}

static void remap_print_result(const struct remap *rmp) /* {{{ */
{
	struct pavl_traverser trav;
	char src[INET_ADDRSTRLEN], dst[INET_ADDRSTRLEN];
	char *hstr, *buf;

	if(!inet_ntop(AF_INET, path_srcptr(rmp->old_path), src, INET_ADDRSTRLEN)) {
		logea(__FILE__, __LINE__, NULL);
	}
	if(!inet_ntop(AF_INET, path_dstptr(rmp->old_path), dst, INET_ADDRSTRLEN)) {
		logea(__FILE__, __LINE__, NULL);
	}

	struct timespec ts;
	clock_gettime(CLOCK_REALTIME, &ts);
	unsigned time = ts.tv_sec;

	int bufsz = PATH_STR_BUF - 1;
	hstr = malloc(PATH_STR_BUF);
	if(!hstr) logea(__FILE__, __LINE__, NULL);
	hstr[0] = '\0';

	int added_hops = 0;
	int last_oldpath_ttl = 0;
	struct pathhop *rmphop = pavl_t_first(&trav, rmp->db->hops);

	for(int i = 0; i < path_length(rmp->old_path); i++) {
		assert(!rmphop || pathhop_ttl(rmphop) >= i);
		struct pathhop *strhop = NULL;

		/* Use rmphop if it doesnt appear in oldpath */
		if(rmphop && pathhop_ttl(rmphop) == i && pathhop_is_star(rmphop)) {
			strhop = rmphop;
			rmphop = pavl_t_next(&trav);
			if(rmphop && !pathhop_is_star(rmphop) && path_search_hop(rmp->old_path, rmphop, 0) != -1) 
				last_oldpath_ttl = path_search_hop(rmp->old_path, rmphop, 0);
		}
		else if(rmphop && pathhop_ttl(rmphop) == i && path_search_hop(rmp->old_path, rmphop, 0) == -1) {
			strhop = rmphop;
			rmphop = pavl_t_next(&trav);
			/* We need to update last_oldpath_ttl for the next iteration. */
			if(rmphop && !pathhop_is_star(rmphop) && path_search_hop(rmp->old_path, rmphop, 0) != -1) 
				last_oldpath_ttl = path_search_hop(rmp->old_path, rmphop, 0);
		} else {
			strhop = pathhop_get_hop(rmp->old_path, last_oldpath_ttl);
			last_oldpath_ttl++;
			/* We need to update avl hops to follow oldpath ttl. */
			while(rmphop && pathhop_ttl(rmphop) <= i)
				rmphop = pavl_t_next(&trav);
		}

		remap_result_append_hop(hstr, &bufsz, strhop);
	}

	int rmp_appended = 0;
	for(; rmphop; rmphop = pavl_t_next(&trav)) {
		remap_result_append_hop(hstr, &bufsz, rmphop);
		last_oldpath_ttl = path_search_hop(rmp->old_path, rmphop, 0);
		rmp_appended = 1;
	}

	/* If oldpath reaches the end but remaprt doesnt probe from some ttl to
		the end, we use the oldpath remaining hops to complete. */
	struct pathhop *lasthop = pathhop_get_hop(rmp->old_path, path_length(rmp->old_path)-1);
	if(pathhop_contains_ip(lasthop, path_dst(rmp->old_path)) && last_oldpath_ttl != -1){
		for(int i=last_oldpath_ttl+rmp_appended; i<path_length(rmp->old_path); i++){
			struct pathhop *strhop = pathhop_get_hop(rmp->old_path, i);
			remap_result_append_hop(hstr, &bufsz, strhop);
		}
	}

	assert(*(strchr(hstr, '\0') - 1) == '|');
	*(strchr(hstr, '\0') - 1) = '\0'; /* remove trailing pipe */

	int measured = 0;
	for(int i = 0; i < 50; i++) measured += measured_ttl[i];

	buf = malloc(PATH_STR_BUF);
	if(!buf) logea(__FILE__, __LINE__, NULL);
	snprintf(buf, PATH_STR_BUF, "%d %s %s %d %s %d %d %d", 
			 rmp->total_probes_sent,
			 src, dst, time, hstr, 
			 added_hops, path_length(rmp->new_path),
			 measured);
	printf("%s\n", buf);
	free(hstr);
	free(buf);
} /* }}} */

struct pathhop * remap_get_hop(struct remap *rmp, int ttl) /* {{{ */
{
	measured_ttl[ttl] = 1;

	struct pathhop *hop = probedb_find_hop(rmp->db, ttl);
	if(!hop) {
		struct pathhop *newhop = NULL;
		
		if(rmp->new_path) {
			if(ttl < path_length(rmp->new_path)) {
				newhop = pathhop_create_copy(pathhop_get_hop(rmp->new_path, ttl));
				int nifaces = pathhop_nifaces(newhop);
				rmp->total_probes_sent += prober_iface2probes(nifaces);
			}
			else {
				struct timespec tstamp;
				clock_gettime(CLOCK_REALTIME, &tstamp);
				newhop = pathhop_create_str(
					"255.255.255.255:0:0.00,0.00,0.00,0.00:", 
					tstamp, ttl);
			}
		} else {
			// +1 because inside paths we count from zero 
			prober_remap_hop(rmp->prober, rmp->new_path, ttl+1);
			newhop = tqrecv(rmp->tq);
		}
		
		*pathhop_ttlptr(newhop) = ttl;
		hop = probedb_add_hop(rmp->db, newhop);
		pathhop_destroy(newhop);
	}
	return hop;
} /* }}} */

static void remap_cb_hop(uint8_t ttl, int nprobes, struct pathhop *hop,/*{{{*/
		void *vrmp)
{
	struct remap *rmp = vrmp;
	rmp->total_probes_sent += nprobes;
	logd(LOG_INFO, "%s reply for hop at TTL %d\n", __func__, (int)ttl);
	tqsend(rmp->tq, hop);
	log_line(__func__,__LINE__,tq_getid(rmp->tq));
} /* }}} */

static void remap_cb_iface(uint8_t ttl, uint8_t flowid,  /* {{{ */
		struct iface *iface, void *vrmp)
{
	struct remap *rmp = vrmp;
	logd(LOG_INFO, "%s reply for iface %d,%d\n", __func__, (int)ttl,
			(int)flowid);
	assert(0);
	/* FIXME TODO implement logic */
	char *str = iface_tostr(iface);
	fprintf(stdout, "%d:%d %s\n", (int)ttl, (int)flowid, str);
	free(str);
	/* probedb_add_iface(rmp->db, iface); iface_destroy(iface); */
}