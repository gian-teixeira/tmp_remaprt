#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <pthread.h>
#include <errno.h>
extern int errno;

#include <arpa/inet.h>

#include "cyc.h"
#include "log.h"

/*****************************************************************************
 * static variables
 ****************************************************************************/
static unsigned log_verbosity = 0;
static struct cyclic *cyc = NULL;

static void log_exit(const char *file, int line);

/*****************************************************************************
 * public function implementations
 ****************************************************************************/
void log_init(unsigned verbosity, const char *path,
		unsigned nbackups, unsigned maxsize) 
{
	if(cyc) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	log_verbosity = verbosity;
	cyc = cyc_init_filesize(path, nbackups, maxsize);
	if(!cyc) log_exit(__FILE__, __LINE__);
	pthread_setcancelstate(oldstate, &oldstate);
}

void log_destroy(void) 
{
	if(!cyc) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	log_verbosity = 0;
	cyc_destroy(cyc);
	cyc = NULL;
	pthread_setcancelstate(oldstate, &oldstate);
}

void log_flush(void) 
{
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	cyc_flush(cyc);
	pthread_setcancelstate(oldstate, &oldstate);
}

void logd(unsigned int verbosity, const char *fmt, ...) 
{
	va_list ap;
	if(verbosity > log_verbosity) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	va_start(ap,fmt);
	if(!cyc_vprintf(cyc, fmt, ap)) log_exit(__FILE__, __LINE__);
	va_end(ap);
	pthread_setcancelstate(oldstate, &oldstate);
}

void loge(unsigned verbosity, const char *file, int lineno) 
{
	if(verbosity > log_verbosity) return;
	if(!errno) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	if(!cyc_printf(cyc, "%s:%d: strerror: %s\n", file, lineno,
			strerror(errno))) log_exit(__FILE__, __LINE__);
	errno = 0;
	pthread_setcancelstate(oldstate, &oldstate);
}

void logea(const char *file, int lineno, const char *msg)
{
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	int myerrno = errno;
	if(!cyc_printf(cyc, "%s:%d: aborting\n", file, lineno)) {
		log_exit(__FILE__, __LINE__);
	}
	if(msg) {
		if(!cyc_printf(cyc, "%s:%d: %s\n", file, lineno, msg)) {
			log_exit(__FILE__, __LINE__);
		}
	}
	errno = myerrno;
	loge(0, file, lineno);
	pthread_setcancelstate(oldstate, &oldstate);
	abort();
}

void logip(unsigned verbosity, uint32_t ip)
{
	char addr[INET_ADDRSTRLEN];
	if(verbosity > log_verbosity) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	if(!inet_ntop(AF_INET, &ip, addr, INET_ADDRSTRLEN)) {
		if(!cyc_printf(cyc, "[%s error: %s]", __func__,
				strerror(errno))) log_exit(__FILE__, __LINE__);
	} else {	
		if(!cyc_printf(cyc, "%s", addr)) log_exit(__FILE__, __LINE__);
	}
	pthread_setcancelstate(oldstate, &oldstate);
}

int log_true(unsigned verbosity)
{
	return verbosity <= log_verbosity;
}

static void log_exit(const char *file, int line)
{
	if(errno) perror("log_exit");
	fprintf(stderr, "%s:%d: unrecoverable error. exiting.\n", file, line);
	exit(EXIT_FAILURE);
}
