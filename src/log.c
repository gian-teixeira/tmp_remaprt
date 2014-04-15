#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <pthread.h>
#include <errno.h>
extern int errno;

#include "cyc.h"
#include "log.h"

/*****************************************************************************
 * static variables
 ****************************************************************************/
static unsigned log_verbosity = 0;
static struct cyclic *cyc = NULL;

static void log_error(const char *file, int line);

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
	if(!cyc) log_error(__FILE__, __LINE__);
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
	if(!cyc) return;
	cyc_flush(cyc);
	pthread_setcancelstate(oldstate, &oldstate);
}

void logd(unsigned int verbosity, const char *fmt, ...)
{
	if(!cyc) return;
	va_list ap;
	if(verbosity > log_verbosity) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	va_start(ap,fmt);
	if(!cyc_vprintf(cyc, fmt, ap)) log_error(__FILE__, __LINE__);
	va_end(ap);
	pthread_setcancelstate(oldstate, &oldstate);
}

void loge(unsigned verbosity, const char *file, int lineno)
{
	if(!cyc) return;
	if(verbosity > log_verbosity) return;
	if(!errno) return;
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	if(!cyc_printf(cyc, "%s:%d: strerror: %s\n", file, lineno,
			strerror(errno))) log_error(__FILE__, __LINE__);
	errno = 0;
	pthread_setcancelstate(oldstate, &oldstate);
}

void logea(const char *file, int lineno, const char *msg)
{
	if(!cyc) exit(EXIT_FAILURE);
	int oldstate;
	pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
	int myerrno = errno;
	if(!cyc_printf(cyc, "%s:%d: aborting\n", file, lineno)) {
		log_error(__FILE__, __LINE__);
	}
	if(msg) {
		if(!cyc_printf(cyc, "%s:%d: %s\n", file, lineno, msg)) {
			log_error(__FILE__, __LINE__);
		}
	}
	errno = myerrno;
	loge(0, file, lineno);
	pthread_setcancelstate(oldstate, &oldstate);
	exit(EXIT_FAILURE);
}

int log_true(unsigned verbosity)
{
	return verbosity <= log_verbosity;
}

/*****************************************************************************
 * static function implementations
 ****************************************************************************/
static void log_error(const char *file, int line)
{
	if(errno) perror("log_error");
	fprintf(stderr, "%s:%d: logging not working.\n", file, line);
}
