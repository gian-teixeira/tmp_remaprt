#ifndef __TQUEUE_H__
#define __TQUEUE_H__

struct tqueue;

struct tqueue * tqueue_create(void);
void tqueue_destroy(struct tqueue *tq);

/* tqsend is nonblocking (locks a mutex, but it's quick) */
void tqsend(struct tqueue *tq, void *ptr);

/* tqrecv blocks until there is something in the queue */
void * tqrecv(struct tqueue *tq);

void tq_setid(struct tqueue *tq, char *str);
char* tq_getid(struct tqueue *tq);

#endif
