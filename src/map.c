#include <assert.h>
#include <inttypes.h>
#include <stdlib.h>

#include "map.h"

/* declarations **************************************************************/

static struct pavl_map_entry * map_entry_create(struct pavl_map *,
		const void *, void *);
static void map_entry_destroy(void *, void *);
static int map_entry_cmp(const void *, const void *, void *);

/* public functions **********************************************************/

struct pavl_map *
map_create(map_keycmp_func *cmp, void *param, struct libavl_allocator *alloc)
{
	struct pavl_map *map;
	assert(cmp != NULL);
	if(alloc == NULL) alloc = &pavl_allocator_default;
	map = alloc->libavl_malloc(alloc, sizeof(struct pavl_map));
	if(map == NULL) return NULL;
	map->compare = cmp;
	map->alloc = alloc;
	map->param = param;
	map->table = pavl_create(map_entry_cmp, map, alloc);
	map->itemfunc = NULL;
	return map;
}

void map_destroy(struct pavl_map *map, map_item_func *destroy) 
{
	map->itemfunc = destroy;
	pavl_destroy(map->table, map_entry_destroy);
	map->alloc->libavl_free(map->alloc, map);	
}

void *map_insert(struct pavl_map *map, const void *key, void *data) {
	struct pavl_map_entry *entry, **ret;
	entry = map_entry_create(map, key, data);
	ret = (struct pavl_map_entry **)pavl_probe(map->table, entry);
	if(ret == NULL || *ret == entry) return NULL;
	else {
		map_entry_destroy(entry, map);
		return (*ret)->data;
	}
}

void *map_replace(struct pavl_map *map, void *key, void *data)
{
	struct pavl_map_entry *entry, **ret;
	entry = map_entry_create(map, key, data);
	ret = (struct pavl_map_entry **)pavl_probe(map->table, entry);
	if(ret == NULL || *ret == entry) {
		return NULL;
	} else {
		void *old;
		old = (*ret)->data;
		(*ret)->data = data;
		map_entry_destroy(entry, map);
		return old;
	}
}

void *map_delete(struct pavl_map *map, const void *key)
{
	struct pavl_map_entry entry, *ret;
	entry.key = key;
	ret = pavl_delete(map->table, &entry);
	if(ret == NULL) return NULL;
	else {
		void *data = ret->data;
		map_entry_destroy(ret, map);
		return data;
	}
}

void *map_find(const struct pavl_map *map, const void *key, const void **oldk)
{
	struct pavl_map_entry entry, *ret;
	entry.key = key;
	ret = pavl_find(map->table, &entry);
	if(ret == NULL) return NULL;
	else {
		if(oldk) *oldk = (void *)ret->key;
		return ret->data;
	}
}

void map_assert_insert(struct pavl_map *map, const void *key, void *data)
{
	struct pavl_map_entry *entry;
	entry = map_entry_create(map, key, data);
	pavl_assert_insert(map->table, entry);
}

void *map_assert_delete(struct pavl_map *map, const void *key)
{
	struct pavl_map_entry entry, *ret;
	entry.key = key;
	ret = pavl_assert_delete(map->table, &entry);
	void *data = ret->data;
	map_entry_destroy(ret, map);
	return data;
}

/* traverser functions *******************************************************/
void map_t_init(struct pavl_map_trav *trav, struct pavl_map *map)
{
	pavl_t_init(&((*trav).trav), map->table);
}

void * 
map_t_first(struct pavl_map_trav *trav, struct pavl_map *map, const void **key)
{
	struct pavl_map_entry *entry;
	entry = pavl_t_first(&((*trav).trav), map->table);
	if(!entry) {
		if(key != NULL) *key = NULL;
		return NULL;
	} else {
		if(key != NULL) *key = entry->key;
		return entry->data;
	}
}

void *
map_t_last(struct pavl_map_trav *trav, struct pavl_map *map, const void **key)
{
	struct pavl_map_entry *entry;
	entry = pavl_t_last(&((*trav).trav), map->table);
	if(!entry) {
		if(key != NULL) *key = NULL;
		return NULL;
	} else {
		if(key != NULL) *key = entry->key;
		return entry->data;
	}
}

void *
map_t_find(struct pavl_map_trav *trav, struct pavl_map *map, const void *key)
{
	struct pavl_map_entry ekey, *entry;
	ekey.key = key;
	entry = pavl_t_find(&((*trav).trav), map->table, &ekey);
	if(entry == NULL) return NULL;
	else return entry->data;
}

void *map_t_next(struct pavl_map_trav *trav, const void **key)
{
	struct pavl_map_entry *entry;
	entry = pavl_t_next(&((*trav).trav));
	if(!entry) {
		if(key != NULL) *key = NULL;
		return NULL;
	} else {
		if(key != NULL) *key = entry->key;
		return entry->data;
	}
}

void *map_t_prev(struct pavl_map_trav *trav, const void **key) 
{
	struct pavl_map_entry *entry;
	entry = pavl_t_next(&((*trav).trav));
	if(!entry) {
		if(key != NULL) *key = NULL;
		return NULL;
	} else {
		if(key != NULL) *key = entry->key;
		return entry->data;
	}
}

void *map_t_cur(struct pavl_map_trav *trav, const void **key)
{
	struct pavl_map_entry *entry;
	entry = pavl_t_cur(&((*trav).trav));
	if(!entry) {
		if(key != NULL) *key = NULL;
		return NULL;
	} else {
		if(key != NULL) *key = entry->key;
		return entry->data;
	}
}

/* struct pavl_map_entry *****************************************************/

static struct pavl_map_entry *
map_entry_create(struct pavl_map *map, const void *key, void *data)
{
	struct pavl_map_entry *entry;
	entry = map->alloc->libavl_malloc(map->alloc,
			sizeof(struct pavl_map_entry));
	if(entry == NULL) return NULL;
	entry->key = key;
	entry->data = data;
	return entry;
}

static int map_entry_cmp(const void *ve1, const void *ve2, void *vmap)
{
	struct pavl_map *map = (struct pavl_map *)vmap;
	const struct pavl_map_entry *e1 = (const struct pavl_map_entry *)ve1;
	const struct pavl_map_entry *e2 = (const struct pavl_map_entry *)ve2;
	return map->compare(e1->key, e2->key, map->param);
}

static void map_entry_destroy(void *ventry, void *vmap)
{
	struct pavl_map *map = (struct pavl_map *)vmap;
	struct pavl_map_entry *entry = (struct pavl_map_entry *)ventry;
	if(map->itemfunc) {
		map->itemfunc((void *)entry->key, entry->data, map->param);
	}
	map->alloc->libavl_free(map->alloc, entry);
}

/* map_cmp functions *********************************************************/

int map_cmp_uint32(const void *v1, const void *v2, void *dummy)
{
	uint32_t *i1 = (uint32_t *)v1;
	uint32_t *i2 = (uint32_t *)v2;
	return (*i1 > *i2) - (*i1 < *i2);
}

int map_cmp_int(const void *v1, const void *v2, void *dummy)
{
	int *i1 = (int *)v1;
	int *i2 = (int *)v2;
	return (*i1 > *i2) - (*i1 < *i2);
}

void map_free(void *key, void *data, void *unused)
{
	if(key) free(key);
	if(data) free(data);
}

