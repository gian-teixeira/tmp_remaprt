#ifndef __SENDER_H__
#define __SENDER_H__

#include <inttypes.h>

struct sender;

struct sender * sender_create(const char *device);
void sender_destroy(struct sender *sender);
int sender_send_icmp(struct sender *sender, uint32_t dst, uint8_t ttl,
		uint16_t checksum, uint16_t id, uint16_t seq);

#endif
