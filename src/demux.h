#ifndef __DEMUX_H__
#define __DEMUX_H__

#include <pcap.h>

#define DEMUX_BUFSZ 8096 /* maximum number of packets pending for processing */

/* the demuxer is a singleton entity that listens on a given interface
 * and calls listener functions for each arriving on that interface. */

struct packet {
	struct timespec tstamp;
	unsigned int caplen;
	char *pkt;
	struct libnet_ipv4_hdr *ip;
	union {
		struct libnet_icmpv4_hdr *icmp;
		struct libnet_udp_hdr *udp;
		struct libnet_tcp_hdr *tcp;
	};
	char *payload;
};
void packet_logd(unsigned verbosity, const struct packet *pkt);

typedef int (*demux_listener_fn)(const struct packet *packet, void *data);

int demux_init(const char *ifname);
void demux_destroy(void);

void demux_listener_add(demux_listener_fn, void *data);
void demux_listener_del(demux_listener_fn, void *data);

#endif
