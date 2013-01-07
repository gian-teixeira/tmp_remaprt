#ifndef __MAP_H__
#define __MAP_H__

#include "pavl.h"

typedef int map_keycmp_func(const void *k1, const void *k2, void *param);
typedef void map_item_func(void *key, void *data, void *param);

struct pavl_map
{
	struct pavl_table *table;
	struct libavl_allocator *alloc;
	map_keycmp_func *compare;
	map_item_func *itemfunc;
	void *param;
};

struct pavl_map_entry
{
	const void *key;
	void *data;
};

struct pavl_map_trav
{
	struct pavl_traverser trav;
};

struct pavl_map * map_create(map_keycmp_func *, void *,
		struct libavl_allocator *);
void map_destroy(struct pavl_map *, map_item_func *);

void *map_insert(struct pavl_map *, const void *, void *);
void *map_delete(struct pavl_map *, const void *);
void *map_find(const struct pavl_map *, const void *, const void **);
void map_assert_insert(struct pavl_map *, const void *, void *);
void *map_assert_delete(struct pavl_map *, const void *);

#define map_count(map) ((size_t)(map)->table->pavl_count)

void map_t_init(struct pavl_map_trav *, struct pavl_map *);
void *map_t_first(struct pavl_map_trav *, struct pavl_map *, const void **);
void *map_t_last(struct pavl_map_trav *, struct pavl_map *, const void **);
void *map_t_find(struct pavl_map_trav *, struct pavl_map *, const void *);
void *map_t_next(struct pavl_map_trav *, const void **);
void *map_t_prev(struct pavl_map_trav *, const void **);
void *map_t_cur(struct pavl_map_trav *, const void **);

int map_cmp_uint32(const void *v1, const void *v2, void *dummy);
int map_cmp_int(const void *v1, const void *v2, void *dummy);
void map_free(void *key, void *data, void *unused);

#endif /* map.h */
