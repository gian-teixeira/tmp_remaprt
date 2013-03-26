#include <stdlib.h>
#include <pthread.h>

#include "dlist.h"
#include "log.h"

struct tqueue {
	struct dlist *queue;
	pthread_mutex_t mutex;
	pthread_cond_t cond;
};
static void tqueue_mutex_unlock(void *vmutex);

struct tqueue * tqueue_create(void) /* {{{ */
{
	struct tqueue *tq = malloc(sizeof(struct tqueue));
	if(!tq) logea(__FILE__, __LINE__, NULL);
	tq->queue = dlist_create();
	if(!tq->queue) logea(__FILE__, __LINE__, NULL);
	pthread_mutex_init(&tq->mutex, NULL);
	if(pthread_cond_init(&tq->cond, NULL)) logea(__FILE__, __LINE__, NULL);
	return tq;
} /* }}} */

void tqueue_destroy(struct tqueue *tq) /* {{{ */
{
	if(!dlist_empty(tq->queue)) logd(LOG_INFO, "destroying nonempty tq\n");
	if(pthread_mutex_destroy(&tq->mutex)) loge(LOG_DEBUG, __FILE__, __LINE__);
	if(pthread_cond_destroy(&tq->cond)) loge(LOG_DEBUG, __FILE__, __LINE__);
	dlist_destroy(tq->queue, NULL);
	free(tq);
} /* }}} */

int tqsize(struct tqueue *tq) /* {{{ */
{
	pthread_mutex_lock(&tq->mutex);
	int sz = dlist_size(tq->queue); 
	pthread_mutex_unlock(&tq->mutex);
	return sz;
} /* }}} */

void tqsend(struct tqueue *tq, void *ptr) /* {{{ */
{
	pthread_mutex_lock(&tq->mutex);
	dlist_push_right(tq->queue, ptr);
	pthread_cond_signal(&tq->cond);
	pthread_mutex_unlock(&tq->mutex);
} /* }}} */

void * tqrecv(struct tqueue *tq) /* {{{ */
{
	pthread_mutex_lock(&tq->mutex);
	pthread_cleanup_push(tqueue_mutex_unlock, &(tq->mutex));
	if(dlist_empty(tq->queue)) pthread_cond_wait(&tq->cond, &tq->mutex);
	pthread_cleanup_pop(0);
	void *ptr = dlist_pop_left(tq->queue);
	pthread_mutex_unlock(&tq->mutex);
	return ptr;
} /* }}} */

static void tqueue_mutex_unlock(void *vmutex) /* {{{ */
{
	pthread_mutex_unlock(vmutex);
} /* }}} */
