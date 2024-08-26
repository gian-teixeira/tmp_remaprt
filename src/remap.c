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
	int total_ttl_measured;

	struct probedb *db;
	int shifts[MAX_PATH_LENGTH];

	double time_spent;
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

static void remap_result_append_hop(char *buf, int *bufsz, struct pathhop *hop);

/*****************************************************************************
 * public implementations
 ****************************************************************************/
void print_old_path(struct remap *rmp){
		struct timespec ts;
		char src[INET_ADDRSTRLEN], dst[INET_ADDRSTRLEN];
		char *buf = malloc(PATH_STR_BUF);
		int bufsz = PATH_STR_BUF - 1;
		char hstr[PATH_STR_BUF];

		int measured = 0;
		for(int i = 0; i < 50; i++) measured += measured_ttl[i];

		*hstr = '\0';
		for(int i = 0; i < path_length(rmp->old_path); ++i) {
			remap_result_append_hop(hstr, &bufsz, pathhop_get_hop(rmp->old_path,i));
		}
		*(strchr(hstr, '\0') - 1) = '\0';

		if(!inet_ntop(AF_INET, path_srcptr(rmp->old_path), src, INET_ADDRSTRLEN)) {
			logea(__FILE__, __LINE__, NULL);
		}
		if(!inet_ntop(AF_INET, path_dstptr(rmp->old_path), dst, INET_ADDRSTRLEN)) {
			logea(__FILE__, __LINE__, NULL);
		}
		clock_gettime(CLOCK_REALTIME, &ts);
		if(!buf) logea(__FILE__, __LINE__, NULL);
		snprintf(buf, PATH_STR_BUF, "%d %s %s %d %s", 
			 	 rmp->total_probes_sent,
			 	 src, dst,
				 ts.tv_sec,
				 hstr);
		// snprintf(buf, PATH_STR_BUF, "%d %s %s %d %s %d %d %.4lf", 
		// 	 	 rmp->total_probes_sent,
		// 	 	 src, dst,
		// 		 ts.tv_sec,
		// 		 hstr,
		// 		 path_length(rmp->new_path),
		// 	 	 measured, 
		// 		 rmp->time_spent);
		printf("%s\n", buf);
		free(buf);
}

int fix_first_hop(struct remap *rmp){
	struct pathhop *firsthop = pathhop_get_hop(rmp->old_path, 0);
	if(!pathhop_is_star(firsthop)) return 1;
	logd(LOG_DEBUG, "%s: first hop is star. Try to fix\n", __func__);
	firsthop = remap_get_hop(rmp, 0);
	if(pathhop_is_star(firsthop)){ 
		logd(LOG_INFO, "%s: first hop didnt answer. Skipping!\n", __func__);
		// pathhop_destroy(firsthop);
		return 0;
	}
	logd(LOG_DEBUG, "%s: first hop fixed!\n", __func__);
	path_set_hop(rmp->old_path, 0, pathhop_create_copy(firsthop));
	logd(LOG_DEBUG, "%s: first hop updated!\n", __func__);
	return 1;
}

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
		assert(rmp->startttl == 0);
		if(!fix_first_hop(rmp)){
			logd(LOG_DEBUG, "%s: cannot access hop\n", __func__);
	       	goto out;
		}
		hop = pathhop_get_hop(rmp->old_path, 0);
	}

	if(!fix_first_hop(rmp)) {
		logd(LOG_DEBUG, "%s: first hop is star!\n", __func__);
		goto out;
	}
	assert(!pathhop_is_star(hop));

	/* Position if the origin in the old path. If it is equal to the position
	   in the new path, no remap is necessary. If the hop was not present, then
	   it can be used to start the remap itself. Else, the binary is used to
	   find a hop that fit the last condition */
	int ttl = path_search_hop(rmp->old_path, hop, 0);

	if(ttl == rmp->startttl) {
		/* The hop is already correct */
		logd(LOG_INFO, "%s: no remap to do\n", __func__);
		print_old_path(rmp);
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

	logd(LOG_DEBUG, "%s: remap_destroy init\n", __func__);
	remap_destroy(rmp);
	logd(LOG_DEBUG, "%s: remap_destroy end\n", __func__);
	return;
	
	out_length:
	logd(LOG_INFO, "%s: can't start after old path length+1\n", __func__);
	out:
	print_old_path(rmp);
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
		// if(branch < 0){
		// 	logd(LOG_DEBUG,"FAILED: %s\n", path_tostr(rmp->old_path));
		// }
		// assert(branch >= 0);
		// logd(LOG_INFO, "%s: looking for branch at ttl %d\n", __func__, branch);
		// hop = remap_get_hop(rmp, branch);
		// branch--;
		if(branch < 0){
			struct pathhop *h = remap_get_hop(rmp, 0);
			if(pathhop_is_star(h)){ 
				logd(LOG_DEBUG,"fix negative branch failed\n");
				print_old_path(rmp);
				exit(0);
			}
			path_set_hop(rmp->old_path, 0, pathhop_create_copy(h));
			logd(LOG_DEBUG,"fix negative branch: %s\n", path_tostr(rmp->old_path));
			branch = 0;
		} else {
			// assert(branch >= 0);
			logd(LOG_INFO, "%s: looking for branch at ttl %d\n", __func__, branch);
			hop = remap_get_hop(rmp, branch);
			branch--;
		}
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
	//printf("STARTED : %s\n", __func__);
	fflush(stdout);

	struct pathhop *hop;
	int right_boundary = r;
	int p1left = 0;
	int p1right = MAX_PATH_LENGTH;
	
	while(r > l) {
		logd(LOG_DEBUG, "init l=%d r=%d\n", l, r);
		int i = (l + r)/2;
		hop = remap_get_hop(rmp, i);
		while(pathhop_is_star(hop)) {
			i--;
			if(i < 0){
				logd(LOG_DEBUG, "didnt find left most hop\n");
				print_old_path(rmp);
				exit(0);
			}
			hop = remap_get_hop(rmp, i);
		}
		
		if(i == l) {
			/* STARs made us reach the left limit, fallback */
			logd(LOG_DEBUG, "left most hop reached\n");
			r = remap_local(rmp, (l + r)/2, l, 0);
			break;
		}

		int p1ttl = path_search_hop(rmp->old_path, hop, 0);
		logd(LOG_DEBUG, "CHECKME: i %d p1ttl %d shift %d\n",
				i, p1ttl, rmp->shifts[i]);
		for(int k=0; k<MAX_PATH_LENGTH; k++) logd(LOG_DEBUG, "%d ", rmp->shifts[k]);
		logd(LOG_DEBUG, "\n");
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
			logd(LOG_DEBUG, "Calling remap_local minttl=%d ttl=%d\n",
				i, l);
			r = remap_local(rmp, i, l, 0);
			break;
		}
		logd(LOG_DEBUG, "end l=%d r=%d\n", l, r);
	}

	hop = probedb_find_hop(rmp->db, r);
	assert(hop);
	int shift = r - path_search_hop(rmp->old_path, hop, 0);
	logd(LOG_DEBUG, "hop_ref_shift=%s shift=%d\n", pathhop_tostr(hop), shift);
	for(int i = r; i <= right_boundary; i++) rmp->shifts[i] = shift;

	struct pavl_traverser trav;
	int pttl = r; // Must start from r.
	for(hop = pavl_t_first(&trav, rmp->db->hops); hop;
			hop = pavl_t_next(&trav)) {
		int ttl = pathhop_ttl(hop);
		if(ttl > right_boundary) continue;
		if(ttl <= r) continue;
		assert(rmp->shifts[ttl] != RMP_SHIFT_CHANGE);
		if(pathhop_is_star(hop)) continue;
		int true_shift = ttl - path_search_hop(rmp->old_path, hop, 0);
		logd(LOG_DEBUG, "remapping true_shift=%d rmp_shift=%d hop=%s\n", true_shift, 
			rmp->shifts[ttl], pathhop_tostr(hop));
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

	rmp->time_spent = 0.0;
	rmp->old_path = path_create_copy(opts->old_path);
	rmp->new_path = opts->new_path;
	if(opts->new_path) 
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
	rmp->total_ttl_measured = 0;
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
	struct pathhop *outpath[MAX_PATH_LENGTH];
	memset(outpath, 0, sizeof(outpath));
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


	int added_hops = 0;
	struct pathhop *rmphop = pavl_t_first(&trav, rmp->db->hops);
	struct pathhop *branch = rmphop;
	struct pathhop *join;
	int join_new_ttl;
	for(; rmphop; rmphop = pavl_t_next(&trav)) {
		char *rmphopstr = pathhop_tostr(rmphop);
		logd(LOG_INFO, "printing %s %d\n", rmphopstr, pathhop_ttl(rmphop));
		free(rmphopstr);
		outpath[pathhop_ttl(rmphop)] = rmphop;
		join = rmphop;
		join_new_ttl = pathhop_ttl(rmphop);
	}

	int ttl_branch_oldpath = path_search_hop(rmp->old_path, branch, 0);
	int ttl_join_oldpath = pathhop_is_star(join)? -1 : path_search_hop(rmp->old_path, join, 0);

	logd(LOG_INFO, "branch=%d join=%d\n", ttl_branch_oldpath, ttl_join_oldpath);

	for(int i=0; i < ttl_branch_oldpath; i++){
		if(outpath[i] == NULL) outpath[i] = pathhop_get_hop(rmp->old_path, i);
	}

	// Only print oldpath if the join exists.
	if(ttl_join_oldpath != -1){
		for(int i=1; ttl_join_oldpath+i < path_length(rmp->old_path); i++){
			if(outpath[join_new_ttl+i] == NULL)
				outpath[join_new_ttl+i] = pathhop_get_hop(rmp->old_path, ttl_join_oldpath+i);
		}
	}

	// Fill missing hops in outpath.
	int outpath_size;
	for(int i=0; i<MAX_PATH_LENGTH; i++) 
		if(outpath[i] != NULL) 
			outpath_size = i;

	int oldpath_counter = 0;
	for(int i=0; i < outpath_size; i++){
		if(outpath[i] == NULL){
			/* New hops must be surrounded by branch and join OR
			   if there is no join, no missing hops is possible as
			   rmprt will probe from new hop till it find 4 stars.
			*/
			assert(oldpath_counter >= 0); 
			outpath[i] = pathhop_get_hop(rmp->old_path, oldpath_counter);
			oldpath_counter++;
		} else {
			if(!pathhop_is_star(outpath[i]))
				oldpath_counter = path_search_hop(rmp->old_path, outpath[i], 0)+1;
		}
	}

	int bufsz = PATH_STR_BUF - 1;
	hstr = malloc(PATH_STR_BUF);
	if(!hstr) logea(__FILE__, __LINE__, NULL);
	hstr[0] = '\0';
	for(int i=0; outpath[i] != NULL; i++) {
		remap_result_append_hop(hstr, &bufsz, outpath[i]);
	}
	assert(*(strchr(hstr, '\0') - 1) == '|');
	*(strchr(hstr, '\0') - 1) = '\0'; /* remove trailing pipe */

	int measured = 0;
	for(int i = 0; i < 50; i++) measured += measured_ttl[i];

	buf = malloc(PATH_STR_BUF);
	if(!buf) logea(__FILE__, __LINE__, NULL);
	snprintf(buf, PATH_STR_BUF, "%d %s %s %d %s", 
			 rmp->total_probes_sent,
			 src, dst, time, hstr);

			//  added_hops, path_length(rmp->new_path),
			//  measured, rmp->time_spent);
	printf("%s\n", buf);
	free(hstr);
	free(buf);
} /* }}} */


struct pathhop * remap_get_hop(struct remap *rmp, int ttl) /* {{{ */
{

	struct pathhop *hop = probedb_find_hop(rmp->db, ttl);
	if(!hop) {
		struct pathhop *newhop = NULL;
		
		if(rmp->new_path) {
			logd(LOG_DEBUG, "%s: offline\n", __func__);
			if(ttl < path_length(rmp->new_path)) {
				newhop = pathhop_create_copy(pathhop_get_hop(rmp->new_path, ttl));
				int nifaces = pathhop_nifaces(newhop);
				if(!measured_ttl[ttl])
					rmp->total_probes_sent += prober_iface2probes(nifaces);
			}
			else {
				struct timespec tstamp;
				clock_gettime(CLOCK_REALTIME, &tstamp);
				newhop = pathhop_create_str(
					"255.255.255.255:0:0.00,0.00,0.00,0.00:", 
					tstamp, ttl);
			}
			measured_ttl[ttl] = 1;
		} else {
			// +1 because inside paths we count from zero 
			logd(LOG_DEBUG, "%s: probing\n", __func__);
			prober_remap_hop(rmp->prober, rmp->new_path, ttl+1);
			newhop = tqrecv(rmp->tq);
		}
		// logd(LOG_INFO, "%s: %d %s\n", __func__, ttl, pathhop_tostr(newhop));
		*pathhop_ttlptr(newhop) = ttl;
		hop = probedb_add_hop(rmp->db, newhop);

		if(pathhop_is_star(newhop)) rmp->time_spent += 3.0;
		else rmp->time_spent = pathhop_rttavg_sample(newhop);

		pathhop_destroy(newhop);
	}
	return hop;
} /* }}} */

static void remap_cb_hop(uint8_t ttl, int nprobes, struct pathhop *hop,/*{{{*/
		void *vrmp)
{
	struct remap *rmp = vrmp;
	rmp->total_probes_sent += nprobes;
	char *hopstr = pathhop_tostr(hop);
	logd(LOG_INFO, "%s reply for hop at TTL %d: %s\n", __func__, (int)ttl, hopstr);
	free(hopstr);
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
	// fprintf(stdout, "%d:%d %s\n", (int)ttl, (int)flowid, str);
	free(str);
	/* probedb_add_iface(rmp->db, iface); iface_destroy(iface); */
}


/* 
	struct pathhop *joinhop = NULL;
	struct pathhop *tkhop = NULL;
	struct pathhop *rmphop = pavl_t_first(&trav, rmp->db->hops);
	
	int consecutive_stars = 0;
	int added_hops = 0;
	int oldshift = 0;
	int joinstar = 0;
	int last_join;

	// last join
	//int i = 0;

	//printf("%s : remaphop = %s (ttl %d)\n", __func__, pathhop_tostr(rmphop), pathhop_ttl(rmphop));
	//printf("%s : Inner loop start!\n", __func__);
	//fflush(stdout);

	//printf("%d\n", path_length(rmp->old_path));
	for(int32_t i = 0; i + oldshift < path_length(rmp->old_path) || rmphop; ++i) {
		//printf("%d %s %s\n", i, 
		//	rmphop ? pathhop_tostr(rmphop) : "NULL", 
		//	joinhop ? pathhop_tostr(joinhop) : "NULL");
		//printf("%d\n", i);
		//fflush(stdout);

		if(rmphop && pathhop_ttl(rmphop) == i) {
			//printf("%d %s ", i, pathhop_tostr(rmphop));
			if(!pathhop_is_star(rmphop)) {
				int j = path_search_hop(rmp->old_path, rmphop, 0);
				oldshift = j-i;
			}
			//printf("%d\n", oldshift);
			tkhop = rmphop;
			rmphop = pavl_t_next(&trav);
		}
		else {
			tkhop = pathhop_get_hop(rmp->old_path, i + oldshift);
		}

		if(pathhop_is_star(tkhop) && ++consecutive_stars == 4) break;
		else consecutive_stars = 0;

		char *s = pathhop_tostr(tkhop);
		//printf("%s\n", s);
		//fflush(stdout);

		strncat(hstr, s, bufsz);
		bufsz -= strlen(s);
		bufsz = (bufsz < 0) ? 0 : bufsz;
		strncat(hstr, "|", bufsz);
		bufsz--;
		bufsz = (bufsz < 0) ? 0 : bufsz;
		free(s);
	}
	*/

/*
	for(int32_t i = 0; i + oldshift < path_length(rmp->old_path) || rmphop || joinhop; ++i) {
		printf("%d %s %s\n", i, 
			rmphop ? pathhop_tostr(rmphop) : "NULL", 
			joinhop ? pathhop_tostr(joinhop) : "NULL");
		fflush(stdout);

		if(rmphop && pathhop_ttl(rmphop) == i) {
			tkhop = joinhop = rmphop;
			rmphop = pavl_t_next(&trav);
		}
		else {
			if(joinhop && !pathhop_is_star(joinhop)) {
				int j = path_search_hop(rmp->old_path, joinhop, PATH_DIFF_FLAG_IGNORE_BALANCERS) + 1;
				oldshift = j-i;
				joinhop = NULL;
				continue;
			}
			tkhop = pathhop_get_hop(rmp->old_path, i + oldshift);
		}

		if(pathhop_is_star(tkhop) && ++consecutive_stars == 4) break;
		else consecutive_stars = 0;

		char *s = pathhop_tostr(tkhop);
		//printf("%s\n", s);
		fflush(stdout);

		strncat(hstr, s, bufsz);
		bufsz -= strlen(s);
		bufsz = (bufsz < 0) ? 0 : bufsz;
		strncat(hstr, "|", bufsz);
		bufsz--;
		bufsz = (bufsz < 0) ? 0 : bufsz;
		free(s);
	}
*/