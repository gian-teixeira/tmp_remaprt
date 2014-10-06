#ifndef __DLIST_H__
#define __DLIST_H__

struct dlist {
	struct dnode *head;
	struct dnode *tail;
	int count;
};

struct dnode {
	struct dnode *prev;
	struct dnode *next;
	void *data;
};

typedef void (*dlist_data_func)(void *data);

struct dlist *dlist_create(void);
void dlist_destroy(struct dlist *dl, dlist_data_func);

void *dlist_pop_left(struct dlist *dl);
void *dlist_pop_right(struct dlist *dl);
void *dlist_push_right(struct dlist *dl, void *data);

/* this function calls cmp to compare [data] and each value in the
 * list. if a value is found, a pointer to it is required and the
 * dnode structure containing it is removed from the list. if there is
 * no matching element matches [data], this function returns NULL. */
void *dlist_find_remove(struct dlist *dl, void *data,
		int (*cmp)(void *a, void *b, void *d), void *user_data);

int dlist_empty(const struct dlist *dl);
int dlist_size(const struct dlist *dl);

void * dlist_get_index(const struct dlist *dl, int idx);
void dlist_set_index(struct dlist *dl, int idx, void *data);

#endif
