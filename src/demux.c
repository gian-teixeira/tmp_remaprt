#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>
#include <time.h>

#include <arpa/inet.h>
#include <assert.h>

#include <pcap.h>
#include <libnet.h>

#include "sniffer.h"
#include "log.h"
#include "demux.h"

static struct demux *demux = NULL;

/*****************************************************************************
 * static declarations
 ****************************************************************************/
struct demux_listener {
	struct demux_listener *next;
	demux_listener_fn cb;
	void *data;
};

struct demux {
	pthread_t thread;
	struct sniffer **caps;
	pthread_cond_t read;
	pthread_mutex_t imut;
	unsigned int readidx;
	unsigned int writeidx;
	unsigned int usedbuf;
	struct packet packets[DEMUX_BUFSZ];

	struct demux_listener *listeners;
	pthread_mutex_t listenmut;
};

/* This function calls |test| for all interfaces on the computer. If |testif|
 * returns non-zero, then capture_create is called for that interface. returns
 * NULL-terminated array of sniffer structs or NULL on error. */
static void * demux_thread(void *nothing);
static struct sniffer ** demux_createcaps(const char *ifn, pcap_handler cb);
static void demux_callback(unsigned char *vcap,
		const struct pcap_pkthdr *pkthdr, const unsigned char *pkt);
static int demux_check_iface(const char *iface, pcap_if_t *pcapif);

static void packet_fillheaders(struct packet *pkt);

static void demux_mutex_unlock(void *vmutex);


/*****************************************************************************
 * public implementations
 ****************************************************************************/
int demux_init(const char *ifname) /* {{{ */
{
	if(demux) return 0;
	demux = malloc(sizeof(struct demux));
	if(!demux) logea(__FILE__, __LINE__, NULL);

	demux->readidx = 0;
	demux->writeidx = 0;
	demux->usedbuf = 0;
	pthread_cond_init(&demux->read, NULL);
	pthread_mutex_init(&demux->imut, NULL);
	pthread_mutex_init(&demux->listenmut, NULL);
	demux->listeners = NULL;

	if(pthread_create(&demux->thread, NULL, demux_thread, NULL)) {
		goto out_mutex2;
	}

	demux->caps = demux_createcaps(ifname, demux_callback);
	if(!demux->caps) goto out_thread;

	return 0;

	out_thread:
	loge(LOG_FATAL, __FILE__, __LINE__);
	pthread_cancel(demux->thread);
	pthread_join(demux->thread, NULL);
	out_mutex2:
	loge(LOG_FATAL, __FILE__, __LINE__);
	pthread_mutex_destroy(&demux->listenmut);
	pthread_mutex_destroy(&demux->imut);
	pthread_cond_destroy(&demux->read);
	free(demux);
	demux = NULL;
	return -1;
} /* }}} */

void demux_destroy(void) /* {{{ */
{
	int i;
	void *r;

	if(demux == NULL) return;
	for(i = 0; demux->caps[i]; i++) sniffer_destroy(demux->caps[i]);
	free(demux->caps);

	pthread_cancel(demux->thread);
	i = pthread_join(demux->thread, &r);
	if(i || r != PTHREAD_CANCELED) {
		logd(LOG_DEBUG, "%s:%d: join(%s) ret(%p)\n", __FILE__,
				__LINE__, strerror(errno), r);
	}

	i = pthread_cond_destroy(&demux->read);
	if(i) logd(LOG_DEBUG, "%s read %s\n", __func__, strerror(errno));
	i = pthread_mutex_destroy(&demux->imut);
	if(i) logd(LOG_DEBUG, "%s imut %s\n", __func__, strerror(errno));
	i = pthread_mutex_destroy(&demux->listenmut);
	if(i) logd(LOG_DEBUG, "%s listenmut %s\n", __func__, strerror(errno));

	while(demux->listeners) {
		struct demux_listener *del = demux->listeners;
		demux->listeners = demux->listeners->next;
		free(del);
	}
	while(demux->readidx != demux->writeidx) {
		free(demux->packets[demux->readidx].pkt);
		demux->readidx = (demux->readidx + 1) % DEMUX_BUFSZ;
	}

	free(demux);
	demux = NULL;
} /* }}} */

void demux_listener_add(demux_listener_fn cb, void *data) /* {{{ */
{
	if(!demux) {
		logd(LOG_DEBUG, "%s:%d: !demux\n", __FILE__, __LINE__);
		return;
	}
	struct demux_listener *nl = malloc(sizeof(struct demux_listener));
	if(!nl) logea(__FILE__, __LINE__, NULL);
	nl->next = demux->listeners;
	nl->cb = cb;
	nl->data = data;
	pthread_mutex_lock(&demux->listenmut);
	demux->listeners = nl;
	pthread_mutex_unlock(&demux->listenmut);
	return;
} /* }}} */

void demux_listener_del(demux_listener_fn cb, void *data) /* {{{ */
{
	struct demux_listener *curr, *del;
	if(!demux) {
		logd(LOG_DEBUG, "%s:%d: !demux\n", __FILE__, __LINE__);
		return;
	}
	pthread_mutex_lock(&demux->listenmut);
	if(demux->listeners->cb == cb && demux->listeners->data == data) {
		del = demux->listeners;
		demux->listeners = demux->listeners->next;
		free(del);
	} else {
		curr = demux->listeners;
		while(curr->next && (curr->next->cb != cb ||
				curr->next->data != data))
			curr = curr->next;
		if(curr->next) {
			del = curr->next;
			curr->next = curr->next->next;
			free(del);
		}
	}
	pthread_mutex_unlock(&demux->listenmut);
} /* }}} */

void packet_logd(unsigned verbosity, const struct packet *pkt) /* {{{ */
{
	char src[INET_ADDRSTRLEN], dst[INET_ADDRSTRLEN];
	char ip[1024], proto[1024];
	const char *aux;

	aux = inet_ntop(AF_INET, &(pkt->ip->ip_src), src, INET_ADDRSTRLEN);
	if(!aux) return;
	aux = inet_ntop(AF_INET, &(pkt->ip->ip_dst), dst, INET_ADDRSTRLEN);
	if(!aux) return;
	sprintf(ip, "IP src(%s) dst(%s)\n", src, dst);

	switch(pkt->ip->ip_p) {
	case IPPROTO_ICMP:
		sprintf(proto, "ICMP type(%u) code(%d) sum(%u)\n",
				pkt->icmp->icmp_type, pkt->icmp->icmp_code,
				pkt->icmp->icmp_sum);
		break;
	case IPPROTO_UDP:
		sprintf(proto, "UDP srcport(%u) dstport(%u) sum(%u)\n",
				pkt->udp->uh_sport, pkt->udp->uh_dport,
				pkt->udp->uh_sum);
		break;
	case IPPROTO_TCP:
		sprintf(proto, "TCP\n");
		break;
	}

	logd(verbosity, "PACKET %lu.%09lu\n%s%s", pkt->tstamp.tv_sec,
			pkt->tstamp.tv_nsec, ip, proto);
} /* }}} */

/*****************************************************************************
 * Internal functions.
 ****************************************************************************/
static struct sniffer ** demux_createcaps(const char *ifname, /* {{{ */
		pcap_handler cb)
{
	const int DEMUX_MAX_SNIFFERS = 1024;
	int cnt;
	char errbuf[PCAP_ERRBUF_SIZE];
	struct sniffer *caps[DEMUX_MAX_SNIFFERS];
	struct sniffer **retval;
	pcap_if_t *ifs, *iface;

	if(-1 == pcap_findalldevs(&ifs, errbuf)) goto out_errbuf;
	if(ifs == NULL) goto out_nodev;
	for(iface = ifs, cnt = 0; iface && cnt < DEMUX_MAX_SNIFFERS;
			iface = iface->next) {
		if(demux_check_iface(ifname, iface)) {
			struct sniffer *s = sniffer_create(iface, cb);
			if(!s) logd(LOG_DEBUG, "%s !ok\n", iface->name);
			else caps[cnt++] = s;
		}
	}
	pcap_freealldevs(ifs);

	if(cnt == 0) goto out_nodev;
	retval = malloc((cnt+1)*sizeof(struct sniffer *));
	if(!retval) logea(__FILE__, __LINE__, NULL);
	memcpy(retval, caps, cnt*sizeof(struct sniffer *));
	retval[cnt] = NULL;
	return retval;

	out_nodev:
	logd(LOG_FATAL, "%s:%d: found no device.\n", __FILE__, __LINE__);
	return NULL;
	out_errbuf:
	logd(LOG_FATAL, "%s:%d: %s\n", __FILE__, __LINE__, errbuf);
	return NULL;
} /* }}} */

static void demux_callback(unsigned char *vcap, /* {{{ */
		const struct pcap_pkthdr *pkthdr, const unsigned char *pkt)
{
	assert(pkthdr->caplen == pkthdr->len);

	char *buf = malloc(pkthdr->caplen);
	if(!buf) logea(__FILE__, __LINE__, NULL);
	memcpy(buf, pkt, pkthdr->caplen);

	pthread_mutex_lock(&demux->imut);
	if(demux->usedbuf >= DEMUX_BUFSZ) goto out_buf;

	struct packet *spkt = &demux->packets[demux->writeidx];
	spkt->tstamp.tv_sec = pkthdr->ts.tv_sec;
	spkt->tstamp.tv_nsec = pkthdr->ts.tv_usec * 1000;
	spkt->caplen = pkthdr->caplen;
	spkt->pkt = buf;
	demux->writeidx = (demux->writeidx + 1) % DEMUX_BUFSZ;
	demux->usedbuf += 1;
	pthread_cond_signal(&demux->read);
	pthread_mutex_unlock(&demux->imut);
	return;

	out_buf:
	logd(LOG_DEBUG, "%s:%d: buffer full\n", __FILE__, __LINE__);
	pthread_cond_signal(&demux->read);
	pthread_mutex_unlock(&demux->imut);
	free(buf);
} /* }}} */

static void * demux_thread(void *nothing) /* {{{ */
{
	int i, worksize;
	pthread_mutex_lock(&demux->imut);
	while(1) {
		if(demux->usedbuf == 0) {
			pthread_cleanup_push(demux_mutex_unlock,
					&(demux->imut));
			pthread_cond_wait(&demux->read, &demux->imut);
			pthread_cleanup_pop(0);
		}

		worksize = demux->writeidx - demux->readidx;
		worksize = (worksize + DEMUX_BUFSZ) % DEMUX_BUFSZ;

		pthread_mutex_lock(&demux->listenmut);
		for(i = 0; i < worksize; i++) {
			struct demux_listener *curr;
			int idx;
			idx = (demux->readidx + i) % DEMUX_BUFSZ;
			packet_fillheaders(&(demux->packets[idx]));
			for(curr = demux->listeners; curr; curr = curr->next) {
				curr->cb(&demux->packets[idx], curr->data);
			}
			free(demux->packets[idx].pkt);
		}
		pthread_mutex_unlock(&demux->listenmut);

		demux->readidx = (demux->readidx + worksize) % DEMUX_BUFSZ;
		demux->usedbuf -= worksize;
	}
	pthread_mutex_unlock(&demux->imut);
	pthread_exit(NULL);
} /* }}} */

static int demux_check_iface(const char *iface, pcap_if_t *pcapif) /* {{{ */
{
	pcap_addr_t *paddr;
	if(pcapif->flags & PCAP_IF_LOOPBACK) return 0;
	if(strcmp(pcapif->name, iface) != 0) return 0;
	for(paddr = pcapif->addresses; paddr; paddr = paddr->next) {
		struct sockaddr *saddr = paddr->addr;
		if(saddr->sa_family == AF_INET) return 1;
	}
	return 0;
} /* }}} */

/*****************************************************************************
 * static function implementations
 ****************************************************************************/
static void packet_fillheaders(struct packet *pkt) /* {{{ */
{
	(*pkt).ip = (struct libnet_ipv4_hdr *)((*pkt).pkt + LIBNET_ETH_H);
	switch((*pkt).ip->ip_p) {
	case IPPROTO_ICMP: {
		unsigned int icmplen = 0;
		(*pkt).icmp = (struct libnet_icmpv4_hdr *)
			((*pkt).pkt + LIBNET_ETH_H + (*pkt).ip->ip_hl*4);
		switch((*pkt).icmp->icmp_type) {
		default:
		case ICMP_IREQ:
		case ICMP_IREQREPLY:
		case ICMP_PARAMPROB:
		case ICMP_ROUTERADVERT:
		case ICMP_ROUTERSOLICIT:
		case ICMP_SOURCEQUENCH:
		case ICMP_ECHO:
		case ICMP_ECHOREPLY:
			icmplen = LIBNET_ICMPV4_ECHO_H;
			break;
		case ICMP_UNREACH:
			icmplen = LIBNET_ICMPV4_UNREACH_H;
			break;
		case ICMP_REDIRECT:
			icmplen = LIBNET_ICMPV4_REDIRECT_H;
			break;
		case ICMP_TIMXCEED:
			icmplen = LIBNET_ICMPV4_TIMXCEED_H;
			break;
		case ICMP_TSTAMP:
		case ICMP_TSTAMPREPLY:
			icmplen = LIBNET_ICMPV4_TS_H;
			break;
		case ICMP_MASKREQ:
		case ICMP_MASKREPLY:
			icmplen = LIBNET_ICMPV4_MASK_H;
			break;
		}
		(*pkt).payload = ((char *)(*pkt).udp) + icmplen;
		break;
	}
	case IPPROTO_UDP:
		(*pkt).udp = (struct libnet_udp_hdr *)
			((*pkt).pkt + LIBNET_ETH_H + (*pkt).ip->ip_hl*4);
		(*pkt).payload = ((char *)(*pkt).udp) + LIBNET_UDP_H;
		break;
	case IPPROTO_TCP:
		(*pkt).tcp = (struct libnet_tcp_hdr *)
			((*pkt).pkt + LIBNET_ETH_H + (*pkt).ip->ip_hl*4);
		(*pkt).payload = ((char *)(*pkt).tcp) + LIBNET_TCP_H;
		break;
	default:
		logd(5, "%s unknown ip proto\n", __func__);
		break;
	}
} /* }}} */

static void demux_mutex_unlock(void *vmutex) /* {{{ */
{
	pthread_mutex_unlock((pthread_mutex_t *)vmutex);
} /* }}} */
