#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "log.h"
#include "pavl.h"
#include "probedb.h"

/*****************************************************************************
 * static declarations
 ****************************************************************************/
static int probedb_cmp_iface(const void *a, const void *b, void *dummy);
static int probedb_cmp_hop(const void *a, const void *b, void *dummy);

/*****************************************************************************
 * public functions
 ****************************************************************************/
struct probedb * probedb_create(void) /* {{{ */
{
	struct probedb *db = malloc(sizeof(struct probedb));
	if(!db) goto out;

	db->ifaces = pavl_create(probedb_cmp_iface, NULL, NULL);
	if(!db->ifaces) goto out_db;

	db->hops = pavl_create(probedb_cmp_hop, NULL, NULL);
	if(!db->hops) goto out_ifaces;
	return db;

	out_ifaces:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	pavl_destroy(db->ifaces, NULL);
	out_db:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	free(db);
	out:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	return NULL;
} /* }}} */

void probedb_destroy(struct probedb *db) /* {{{ */
{
	pavl_destroy(db->hops, pathhop_destroy_void);
	pavl_destroy(db->ifaces, iface_destroy_void);
	free(db);
} /* }}} */

struct iface * probedb_add_iface(struct probedb *db,  /* {{{ */
		const struct iface *iff)
{
	struct iface *dbiff = iface_create_copy(iff);
	pavl_assert_insert(db->ifaces, dbiff);
	return dbiff;
} /* }}} */

struct pathhop * probedb_add_hop(struct probedb *db, /* {{{ */
		const struct pathhop *hop)
{
	struct pathhop *dbhop = pathhop_create_copy(hop);
	pavl_assert_insert(db->hops, dbhop);
	return dbhop;
} /* }}} */

struct iface * probedb_find_iface(const struct probedb *db, uint8_t ttl,/*{{{*/
		uint8_t flowid)
{
	char buf[80];
	struct timespec tstamp = {0, 0};
	snprintf(buf, 80, "255.255.255.255:%d:0.0,0.0,0.0,0.0:", flowid);
	struct iface *k = iface_create_str(buf, tstamp, ttl);
	struct iface *f = pavl_find(db->ifaces, k);
	iface_destroy(k);
	return f;
} /* }}} */

struct pathhop * probedb_find_hop(const struct probedb *db, uint8_t ttl)/*{{{*/
{
	char *hopstr = "255.255.255.255:0:0.0,0.0,0.0,0.0:";
	struct timespec tstamp = {0, 0};
	struct pathhop *k = pathhop_create_str(hopstr, tstamp, ttl);
	struct pathhop *h = pavl_find(db->hops, k);
	pathhop_destroy(k);
	return h;
} /* }}} */

char * probedb_dump_hops(const struct probedb *db) /* {{{ */
{
	char buf[1024*16]; buf[0] = '\0';
	struct pavl_traverser trav;
	struct pathhop *hop;
	for(hop = pavl_t_first(&trav, db->hops); hop; hop = pavl_t_next(&trav)) {
		int i = strlen(buf);
		if(i) { buf[i] = '\n'; buf[i+1] = '\0'; }
		char *hopstr = pathhop_tostr(hop);
		strncat(buf, hopstr, 4096);
		free(hopstr);
	}
	char *str = strdup(buf);
	return str;
} /* }}} */

/*****************************************************************************
 * cmp functions
 ****************************************************************************/
static int probedb_cmp_iface(const void *a, const void *b, void *dummy) /* {{{ */
{
	struct iface *i1 = (struct iface *)a;
	struct iface *i2 = (struct iface *)b;
	int i1d = iface_ttl(i1);
	int i2d = iface_ttl(i2);
	int r = (i1d < i2d) - (i1d > i2d);
	if(r != 0) { return r; }
	i1d = iface_first_flowid(i1);	
	i2d = iface_first_flowid(i2);	
	return (i1d < i2d) - (i1d > i2d);
} /* }}} */
static int probedb_cmp_hop(const void *a, const void *b, void *dummy) /* {{{ */
{
	struct pathhop *h1 = (struct pathhop *)a;
	struct pathhop *h2 = (struct pathhop *)b;
	int h1d = pathhop_ttl(h1);
	int h2d = pathhop_ttl(h2);
	return (h1d > h2d) - (h1d < h2d);
} /* }}} */
