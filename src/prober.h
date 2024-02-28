#ifndef __PROBER_H__
#define __PROBER_H__

#include <inttypes.h>
#include "opts.h"
#include "path.h"

struct prober;

typedef void (*prober_cb_hop)(uint8_t ttl, int nprobes, struct pathhop *hop,
		void *data);
typedef void (*prober_cb_iface)(uint8_t ttl, uint8_t flowid, struct iface *i,
		void *data);

struct prober * prober_create(const struct opts *opts,
		prober_cb_hop hop_cb, prober_cb_iface iface_cb, void *cb_data);
void prober_destroy(struct prober *p);

void prober_remap_hop(struct prober *p, struct path *new_path, uint8_t ttl);

void prober_remap_iface(struct prober *p, uint8_t ttl, uint8_t flowid);

int prober_iface2probes(int ips);

#endif
