#include <stdlib.h>
#include <libnet.h>
#include <assert.h>

#include "sender.h"
#include "log.h"

#define SENDER_TOS 0
#define SENDER_ID 1
#define SENDER_FRAG 0
#define SENDER_AUTO_CHECKSUM 0

/*****************************************************************************
 * static declarations
 ****************************************************************************/
struct sender {
	libnet_t *ln;
	uint32_t ip;
	libnet_ptag_t icmptag;
	libnet_ptag_t iptag;
};

static uint16_t sender_balance_checksum(uint16_t typecode, uint16_t checksum,
		uint16_t id, uint16_t seq);

/*****************************************************************************
 * public implementations
 ****************************************************************************/
struct sender * sender_create(const char *device) /* {{{ */
{
	char errbuf[LIBNET_ERRBUF_SIZE];
	char *dev;
	struct sender *sender;

	dev = strdup(device);
	if(!dev) logea(__FILE__, __LINE__, NULL);
	sender = malloc(sizeof(struct sender));
	if(!sender) logea(__FILE__, __LINE__, NULL);
	sender->ln = libnet_init(LIBNET_RAW4, dev, errbuf);
	if(!sender->ln) goto out_libnet;
	free(dev);
	sender->ip = libnet_get_ipaddr4(sender->ln);
	sender->icmptag = 0;
	sender->iptag = 0;

	logd(LOG_INFO, "%s dev=%s ok\n", __func__, device);

	return sender;

	out_libnet:
	loge(LOG_FATAL, __FILE__, __LINE__);
	logd(LOG_FATAL, "%s: %s", __func__, errbuf);
	free(sender);
	free(dev);
	return NULL;
} /* }}} */

void sender_destroy(struct sender *sender) /* {{{ */
{
	logd(LOG_INFO, "%s ok\n", __func__);
	libnet_destroy(sender->ln);
	free(sender);
} /* }}} */

int sender_send_icmp(struct sender *sender, uint32_t dst, uint8_t ttl, /*{{{*/
		uint16_t checksum, uint16_t id, uint16_t seq)
{
	uint16_t payload;
	libnet_t *ln = sender->ln;

	// icmp type + icmp code
	char buf[2] = {ICMP_ECHO, 0};
	uint16_t *typecodeptr = (uint16_t *)buf;
	uint16_t typecode = *typecodeptr;

	payload = sender_balance_checksum(typecode, checksum, id, seq);
	sender->icmptag = libnet_build_icmpv4_echo(ICMP_ECHO, 0,
			checksum, id, seq, (uint8_t *)&payload, 2,
			ln, sender->icmptag);
	if(sender->icmptag == -1) goto out;

	uint8_t *pbuf = libnet_getpbuf(sender->ln, sender->icmptag);

	assert(*(((uint16_t *)(pbuf))+1) == htons(checksum));

	sender->iptag = libnet_build_ipv4(
			LIBNET_IPV4_H + LIBNET_ICMPV4_ECHO_H + 2,
			SENDER_TOS, SENDER_ID, SENDER_FRAG, ttl,
			IPPROTO_ICMP, SENDER_AUTO_CHECKSUM,
			sender->ip, dst, NULL, 0, ln, sender->iptag);
	if(sender->iptag == -1) goto out;

	libnet_write(ln);
	return 0;

	out:
	loge(LOG_FATAL, __FILE__, __LINE__);
	logd(LOG_DEBUG, "%s %d %d error: %s\n", __func__, ttl, checksum,
			libnet_geterror(ln));
	libnet_clear_packet(ln);
	sender->icmptag = 0;
	sender->iptag = 0;
	return -1;
} /* }}} */

/*****************************************************************************
 * public implementations
 ****************************************************************************/
static uint16_t sender_balance_checksum(uint16_t typecode, /* {{{ */
		uint16_t checksum, uint16_t id, uint16_t seq)
{
	uint32_t acc = 0;

	acc += typecode; /* already in network byte order */
	acc += htons(checksum);
	acc += htons(id);
	acc += htons(seq);

	while(acc >> 16) {
		acc = (acc & 0xffff) + (acc >> 16);
	}

	return ~acc;
} /* }}} */
