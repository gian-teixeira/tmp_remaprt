#ifndef __PROBEDB_H__
#define __PROBEDB_H__

#include <inttypes.h>
#include "path.h"

struct probedb {
	struct pavl_table *ifaces;
	struct pavl_table *hops;
};

struct probedb * probedb_create(void);
void probedb_destroy(struct probedb *db);

struct pathhop * probedb_add_hop(struct probedb *db, const struct pathhop *h);
struct iface * probedb_add_iface(struct probedb *db, const struct iface *i);

/* These functions return NULL if there is no data in the DB. */
struct pathhop * probedb_find_hop(const struct probedb *db, uint8_t ttl);
struct iface * probedb_find_iface(const struct probedb *db, uint8_t ttl,
							uint8_t flowid);

/* the returned string should be freed by the caller */
char * probedb_dump_hops(const struct probedb *db);

#endif
