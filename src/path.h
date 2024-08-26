#ifndef __PATH_H__
#define __PATH_H__

#include <inttypes.h>

#define PATH_FLAG_NO_REACHABILITY (1<<0)

#define PATH_DIFF_FLAG_FIX_STARS (1<<1)
#define PATH_DIFF_FLAG_FILL_MISSING (1<<2)
#define PATH_DIFF_FLAG_IGNORE_BALANCERS (1<<3)

struct path;
struct pathhop;
struct iface;
struct pathdb;

/*****************************************************************************
 * struct path *
 ****************************************************************************/
struct path * path_create_copy(const struct path *path);
struct path * path_create_str(const char *buf);
struct path * path_create_str_hops(const char *str, uint32_t dst);
/* create_str_safe returns an empty path if str is malformed: */
struct path * path_create_str_safe(const char *str, uint32_t dst);

void path_destroy(struct path *path);

/* the returned string is owned and should be freed by the caller: */
char * path_tostr(const struct path *p);

/* computes the number of disjoint changes in a path: */
int path_diff(struct path *p1, struct path *p2, uint32_t diff_flags);

/* checks whether [p] agrees with [ip] at [ttl] with [flowid]. */
int path_change(const struct path *p, uint8_t ttl, uint8_t flowid, uint32_t ip);

/* returns -1 if hop is not in path, or the ttl where it is */
int path_search_hop(const struct path *p, const struct pathhop *hop,
		uint32_t diff_flags);

uint32_t path_dst(const struct path *p);
int path_length(const struct path *p);
const uint32_t * path_dstptr(const struct path *p);
const uint32_t * path_srcptr(const struct path *p);
struct timespec path_tstamp(const struct path *p);
struct pavl_table * path_interfaces(const struct path *p);
int path_alias(const struct path *p);
void path_alias_set(struct path *p, int alias);
void path_set_hop(struct path *p, int ttl, struct pathhop *h);

/*****************************************************************************
 * struct pathhop *
 ****************************************************************************/
struct pathhop * pathhop_create_copy(const struct pathhop *hop);
struct pathhop * pathhop_create_str(const char *s, struct timespec t, int ttl);

void pathhop_destroy(struct pathhop *h);
void pathhop_destroy_void(void *pathhop, void *dummy);

int pathhop_contains_ip(const struct pathhop *h, uint32_t ip);
char * pathhop_tostr(const struct pathhop *h);
int pathhop_is_star(const struct pathhop *h);
int pathhop_ttl(const struct pathhop *hop);
int * pathhop_ttlptr(struct pathhop *hop);
struct pathhop * pathhop_get_hop(struct path *path, int ttl);
int pathhop_nifaces(struct pathhop *h);
double pathhop_rttavg_sample(const struct pathhop *hop);

/*****************************************************************************
 * struct iface *
 ****************************************************************************/
struct iface * iface_create_copy(const struct iface *origin);
struct iface * iface_create_str(const char *buf, struct timespec t, int ttl);
void iface_destroy(struct iface *iface);
void iface_destroy_void(void *vi, void *dummy);

char * iface_tostr(const struct iface *iface);
void iface_logd(unsigned verbosity, const struct iface *iface);
void iface_logl(unsigned verbosity, const struct iface *iface);

int iface_is_star(const struct iface *iface);
uint32_t iface_ip(const struct iface *iface);
int iface_ttl(const struct iface *iface);
int iface_first_flowid(const struct iface *iface);
int iface_random_flowid(const struct iface *iface);
double iface_rttavg(const struct iface *iface);

int iface_cmp_ip(const void *v1, const void *v2);
int iface_cmp_ip_data(const void *v1, const void *v2, void *dummy);
int iface_cmp_ip_ttl_data(const void *v1, const void *v2, void *dummy);

/*****************************************************************************
 * struct pathdb *
 ****************************************************************************/
struct pathdb * pathdb_create(int max_aliases);
void pathdb_destroy(struct pathdb *db);

/* copy [p] if it is not in the database and set the [p]'s identifier: */
void pathdb_alias(struct pathdb *db, struct path *p);

/* return how many aliases we've seen to a dst: */
int pathdb_naliases(struct pathdb *db, uint32_t dst);

#endif
