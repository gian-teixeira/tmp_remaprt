#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#include <pthread.h>
#include <errno.h>

#include <arpa/inet.h>

#include "pavl.h"
#include "map.h"
#include "tqueue.h"
#include "log.h"
#include "confirm.h"
#include "timespec.h"
#include "prober.h"
#include "path.h"

int PARIS_IFACE2PROBES[] = {6, 6, 11, 16, 21, 27, 33, 38, 44, 51, 57, 63, 70, 76, 83, 90, 96};
int PARIS_MAXIFACES = 15;

/*****************************************************************************
 * static declarations
 ****************************************************************************/
struct prober {
	pthread_t thread;
	uint32_t dst;
	prober_cb_iface iface_cb;
	prober_cb_hop hop_cb;
	void *cb_data;
	struct confirm *confirm;
	int refcnt;
	struct tqueue *tq;
};

struct hopremap {
	struct path *new_path;
	uint8_t ttl;
	int probes_sent;
	int pending_probes;
	struct pavl_table *ips;
	struct pavl_map *id2iface;
	struct prober *prober;
	/* NOTE: we do not have a mutex in pathhop_remap because all
	 * changes in this structure is made by the prober thread */
};

static void prober_iface_reply(struct confirm_query *q);
static void prober_hop_reply(struct confirm_query *q);
static void prober_iface_process(struct confirm_query *q);
static void prober_hop_process(struct confirm_query *q);
static struct iface * prober_parse(struct confirm_query *q);
static void * prober_thread(void *p);

static struct hopremap * hopremap_create(struct prober *prober, struct path *new_path, uint8_t ttl);
static void hopremap_destroy(struct hopremap *hr);
static void hopremap_free_id2iface(void *key, void *value, void *dummy);
static int hopremap_needed_probes(struct hopremap *hr);
static void hopremap_send_probes(struct hopremap *hr, int count);
static void hopremap_hop_add(struct hopremap *hr, struct iface *iff);
static struct pathhop * hopremap_build_hop(const struct hopremap *hr);

/*****************************************************************************
 * public implementations
 ****************************************************************************/
struct prober * prober_create(const struct opts *opts, /* {{{ */
		prober_cb_hop hop_cb, prober_cb_iface iface_cb, void *cb_data)
{
	log_line(__func__,__LINE__,"");
	struct prober *prober = malloc(sizeof(struct prober));
	if(!prober) logea(__FILE__, __LINE__, NULL);
	prober->dst = opts->dst;
	prober->iface_cb = iface_cb;
	prober->hop_cb = hop_cb;
	prober->cb_data = cb_data;
	prober->refcnt = 0;
	prober->confirm = confirm_create(opts->iface, opts->icmpid);
	if(!prober->confirm) goto out;
	prober->tq = tqueue_create();
	if(!prober->tq) goto out_confirm;
	if(pthread_create(&prober->thread, NULL, prober_thread, prober)) {
		goto out_tqueue;
	}
	logd(LOG_INFO, "%s: prober started\n", __func__);
	return prober;

	out_tqueue:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	tqueue_destroy(prober->tq);
	out_confirm:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	confirm_destroy(prober->confirm);
	out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	free(prober);
	return NULL;
} /* }}} */

void prober_destroy(struct prober *p)  /* {{{ */
{
	log_line(__func__,__LINE__,"");
	int i;
	void *r;
	logd(LOG_DEBUG, "entering %s\n", __func__);
	if(p->refcnt != 0) {
		logd(LOG_DEBUG, "%s: refcnt != 0\n", __func__);
		return;
	}
	if(pthread_cancel(p->thread)) loge(LOG_DEBUG, __FILE__, __LINE__);
	i = pthread_join(p->thread, &r);
	if(i || r != PTHREAD_CANCELED) {
		logd(LOG_DEBUG, "%s join(%d, %s) ret(%p)\n", __func__, i,
				strerror(errno), r);
	}
	tqueue_destroy(p->tq);
	confirm_destroy(p->confirm);
	free(p);
} /* }}} */

void prober_remap_iface(struct prober *p, uint8_t ttl, uint8_t flowid) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	logd(LOG_INFO, "%s creating query for iface %d,%d\n", __func__,
			(int)ttl, (int)flowid);
	struct confirm_query *q = confirm_query_create(p->dst, ttl, flowid);
	q->cb = prober_iface_reply;
	q->data = p;
	q->ntries = 3;
	p->refcnt++;
	confirm_query(p->confirm, q);
} /* }}} */

void prober_remap_hop(struct prober *p, struct path *new_path, uint8_t ttl) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	logd(LOG_INFO, "%s creating query for ttl %d\n", __func__, (int)ttl);
	struct hopremap *hr =  hopremap_create(p, new_path, ttl);
	int needed = hopremap_needed_probes(hr);
	assert(needed == PARIS_IFACE2PROBES[0]);
	hopremap_send_probes(hr, needed);
} /* }}} */

/*****************************************************************************
 * static functions
 ****************************************************************************/
static void prober_iface_reply(struct confirm_query *q) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	logd(LOG_INFO, "%s ttl %d flowid %d\n", __func__, (int)q->ttl,
			(int)q->flowid);
	q->cb = prober_iface_process;
	struct prober *p = q->data;
	tqsend(p->tq, q);
} /* }}} */

static void prober_hop_reply(struct confirm_query *q) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	logd(LOG_INFO, "%s ttl %d flowid %d\n", __func__, (int)q->ttl,
			(int)q->flowid);
	q->cb = prober_hop_process;
	struct hopremap *hr = q->data;
	tqsend(hr->prober->tq, q);
} /* }}} */

static void prober_iface_process(struct confirm_query *q) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	struct iface *iff = prober_parse(q);
	struct prober *p = (struct prober *)q->data;
	p->iface_cb(q->ttl, q->flowid, iff, p->cb_data);
	confirm_query_destroy(q);
	p->refcnt--;
	return;
} /* }}} */

static void prober_hop_process(struct confirm_query *q) /* {{{ */
{
	log_line(__func__,__LINE__,".... hop process started");
	struct hopremap *hr = q->data;
	struct prober *prober = hr->prober;
	struct iface *iff = prober_parse(q);
	confirm_query_destroy(q);
	prober->refcnt--;
	hopremap_hop_add(hr, iff);
	int needed = hopremap_needed_probes(hr);
	if(needed == 0 && hr->pending_probes == 0) {
		struct pathhop *hop = hopremap_build_hop(hr);
		prober->hop_cb(hr->ttl, hr->probes_sent, hop, prober->cb_data);
		hopremap_destroy(hr);
	} else if(needed > 0) {
		hopremap_send_probes(hr, needed);
	}
	log_line(__func__,__LINE__,".... hop process finished");
} /* }}} */

static struct iface * prober_parse(struct confirm_query *q) /* {{{ */
{
	char ifstr[128];
	char daddr[INET_ADDRSTRLEN] = "0.0.0.0";
	char haddr[INET_ADDRSTRLEN] = "0.0.0.0";
	struct timespec tstamp, rttts;

	inet_ntop(AF_INET, &(q->dst), daddr, INET_ADDRSTRLEN);
	inet_ntop(AF_INET, &(q->ip), haddr, INET_ADDRSTRLEN);
	logd(LOG_EXTRA, "query dst %s ttl %d flowid %d -> %s\n", daddr,
			q->ttl, q->flowid, haddr);
	
	if(clock_gettime(CLOCK_REALTIME, &tstamp)) goto out_error;

	timespec_sub(tstamp, q->start, &rttts);
	double rtt = timespec_todouble(rttts) * 1000;

	snprintf(ifstr, 128, "%s:%d:%.2f,%.2f,%.2f,%.2f:", haddr, q->flowid,
			rtt, rtt, rtt, rtt);
	struct iface *iff = iface_create_str(ifstr, tstamp, q->ttl);

	
	return iff;

	out_error:
	loge(LOG_FATAL, __FILE__, __LINE__);
	return NULL;
} /* }}} */

static void * prober_thread(void *vprober) /* {{{ */
{
	logd(LOG_INFO, "%s started\n", __func__);
	struct prober *p = vprober;
	while(1) {
		log_line(__func__,__LINE__,"--------------------------------- thread started");
		void *ptr = tqrecv(p->tq);
		struct confirm_query *q = ptr;
		q->cb(q);
		log_line(__func__,__LINE__,"--------------------------------- thread finished");
	}
} /* }}} */

/*****************************************************************************
 * pathhop_remap functions
 ****************************************************************************/
static struct hopremap * hopremap_create(struct prober *p, struct path *new_path, uint8_t ttl) /*{{{*/
{
	struct hopremap *hr = malloc(sizeof(struct hopremap));
	if(!hr) logea(__FILE__, __LINE__, NULL);
	hr->ips = pavl_create(map_cmp_uint32, NULL, NULL);
	if(!hr->ips) goto out;
	hr->id2iface = map_create(map_cmp_uint32, NULL, NULL);
	if(!hr->id2iface) goto out_ips;
	hr->prober = p;
	hr->new_path = new_path;
	hr->ttl = ttl;
	hr->probes_sent = 0;
	hr->pending_probes = 0;
	return hr;

	out_ips:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	pavl_destroy(hr->ips, NULL);
	out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	free(hr);
	return NULL;
} /* }}} */

static void hopremap_destroy(struct hopremap *hr) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	map_destroy(hr->id2iface, hopremap_free_id2iface);
	pavl_destroy(hr->ips, pavl_item_free);
	free(hr);
} /* }}} */

static void hopremap_free_id2iface(void *key, void *value, void *dummy) /*{{{*/
{
	log_line(__func__,__LINE__,"");
	free(key);
	iface_destroy((struct iface *)value);
} /* }}} */

static int hopremap_needed_probes(struct hopremap *hr) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	int ips = pavl_count(hr->ips);
	if(ips >= PARIS_MAXIFACES) return 0;
	int needed = PARIS_IFACE2PROBES[ips] - hr->probes_sent;
	assert(needed >= 0);
	return needed;
} /* }}} */

static void hopremap_send_probes(struct hopremap *hr, int count) /* {{{ */
{
	log_line(__func__,__LINE__,"------------------------------ sending probes");
	logd(LOG_INFO, "%s probes %d ttl %d\n", __func__, count, hr->ttl);
	struct prober *p = hr->prober;
	assert(hr->probes_sent + count < UINT8_MAX);
	for(int i = 0; i < count; i++) {
		uint8_t id = i + hr->probes_sent;
		struct confirm_query *q = confirm_query_create(
				hr->prober->dst, hr->ttl, id);
		q->cb = prober_hop_reply;
		q->data = hr;
		q->ntries = 1;
		p->refcnt++;
		confirm_query(p->confirm, q);
	}
	hr->probes_sent += count;
	hr->pending_probes += count;
} /* }}} */

static void hopremap_hop_add(struct hopremap *hr, struct iface *iff) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	hr->pending_probes--;
	if(iface_is_star(iff)) {
		iface_destroy(iff);
		return;
	}

	uint32_t *newptr = malloc(sizeof(uint32_t));
	if(!newptr) logea(__FILE__, __LINE__, NULL);
	*newptr = iface_ip(iff);
	uint32_t *oldptr = pavl_insert(hr->ips, newptr);
	if(oldptr != NULL && oldptr != newptr) free(newptr);
	logd(LOG_INFO, "%s seen %d ips so far on ttl %d\n", __func__,
			pavl_count(hr->ips), (int)hr->ttl);

	int *idptr = malloc(sizeof(int));
	if(!idptr) logea(__FILE__, __LINE__, NULL);
	*idptr = iface_first_flowid(iff);
	map_assert_insert(hr->id2iface, idptr, iff);
} /* }}} */

static struct pathhop * hopremap_build_hop(const struct hopremap *hr) /* {{{ */
{
	log_line(__func__,__LINE__,"");
	char str[4096]; str[0] = '\0';
	struct timespec tstamp;
	clock_gettime(CLOCK_REALTIME, &tstamp);
	
	if(pavl_count(hr->ips) == 0) {
		char *str = "255.255.255.255:0:0.0,0.0,0.0,0.0:";
		struct pathhop * hop = pathhop_create_str(str, tstamp, hr->ttl);
		assert(pathhop_is_star(hop));
		return hop;
	}

	// Verificar a existência do caminho
	
	struct pavl_traverser trav;
	uint32_t *ip;
	for(ip = pavl_t_first(&trav, hr->ips); ip; ip = pavl_t_next(&trav)) {
		char addr[INET_ADDRSTRLEN];
		inet_ntop(AF_INET, ip, addr, INET_ADDRSTRLEN);
		double rttmin = 1e100;
		double rttmax = 0;
		double sx = 0;
		double ssx = 0;
		int n = 0;

		const void *key;
		struct iface *iff;
		struct pavl_map_trav mtrav;
		char idstr[256]; idstr[0] = '\0';
		for(iff = map_t_first(&mtrav, hr->id2iface, &key); iff;
				iff = map_t_next(&mtrav, &key)) {
			if(iface_ip(iff) != *ip) continue;
			int clen = strlen(idstr);
			snprintf(idstr + clen, 256 - clen - 1, "%d,", *(int *)key);
			double rtt = iface_rttavg(iff);
			assert(rtt > 0);
			rttmin = (rttmin < rtt) ? rttmin : rtt;
			rttmax = (rttmax > rtt) ? rttmax : rtt;
			sx += rtt;
			ssx += (rtt * rtt);
			n++;
		}
		idstr[strlen(idstr)-1] = '\0'; /* removing last comma */

		snprintf(str+strlen(str), 4096-strlen(str),
				"%s:%s:%.2f,%.2f,%.2f,%.2f:;",
				addr, idstr, rttmin, sx/n, rttmax,
				(ssx/n - (sx/n)*(sx/n)));
	}

	str[strlen(str)-1] = '\0'; /* removing last semicolon */
	logd(LOG_INFO, "%s str %s\n", __func__, str);
	struct pathhop *hop = pathhop_create_str(str, tstamp, hr->ttl);
	return hop;
} /* }}} */

int prober_iface2probes(int ips) 
{
	if(ips >= PARIS_MAXIFACES) return 0;
	return PARIS_IFACE2PROBES[ips];
}