#include <time.h>
#include <math.h>
#include "log.h"

int timespec_cmp(struct timespec a, struct timespec b) /* {{{ */
{
	return 2*((a.tv_sec > b.tv_sec) - (a.tv_sec < b.tv_sec)) +
		(a.tv_nsec > b.tv_nsec) - (a.tv_nsec < b.tv_nsec);
} /* }}} */

int timespec_is_zero(struct timespec a) /* {{{ */
{
	return (a.tv_sec == 0) && (a.tv_nsec == 0);
} /* }}} */

void timespec_fromdouble(double interval, struct timespec *ts) /* {{{ */
{
	uint64_t nsec = ((uint64_t)(interval*1000000000)) % 1000000000;
	ts->tv_sec = (time_t)interval;
	ts->tv_nsec = (long)nsec;
} /* }}} */

double timespec_todouble(struct timespec ts) /* {{{ */
{
	return ts.tv_sec + ts.tv_nsec / 1000000000.0;
} /* }}} */

void timespec_add(struct timespec a, struct timespec b, /* {{{ */
		struct timespec *res)
{
	res->tv_nsec = a.tv_nsec + b.tv_nsec;
	res->tv_sec = a.tv_sec + b.tv_sec;
	if(res->tv_nsec >= 1000000000) {
		res->tv_sec++;
		res->tv_nsec = res->tv_nsec % 1000000000;
	}
} /* }}} */

void timespec_mult(struct timespec a, unsigned times, /* {{{ */
		struct timespec *res)
{
	uint64_t nano = a.tv_nsec * times;
	res->tv_sec = a.tv_sec * times;
	res->tv_sec += nano/1000000000;
	res->tv_nsec = nano % 1000000000;
} /* }}} */

void timespec_sub(struct timespec a, struct timespec b, /* {{{ */
		struct timespec *res)
{
	if(timespec_cmp(a, b) < 0) {
		res->tv_sec = 0;
		res->tv_nsec = 0;
		logd(LOG_WARN, "%s:%d error: %lu.%09ld - %lu.%09ld\n",
				__FILE__, __LINE__,
				a.tv_sec, a.tv_nsec, b.tv_sec, b.tv_nsec);
	} else {
		res->tv_nsec = a.tv_nsec - b.tv_nsec;
		res->tv_sec = a.tv_sec - b.tv_sec;
		if(res->tv_nsec < 0) {
			res->tv_nsec += 1000000000;
			res->tv_sec--;
		}
	}
} /* }}} */

double timespec_sub_double(struct timespec a, struct timespec b) /* {{{ */
{
	return a.tv_sec - b.tv_sec +
			(a.tv_nsec - b.tv_nsec)/1000000000.0;
} /* }}} */

void timespec_logd(unsigned verbosity, struct timespec a) /* {{{ */
{
	logd(verbosity, "%lu.%09ld", a.tv_sec, a.tv_nsec);
} /* }}} */

void timespec_logl(unsigned verbosity, struct timespec a) /* {{{ */
{
	logd(verbosity, "%lu.%09ld\n", a.tv_sec, a.tv_nsec);
} /* }}} */

void timespec_shift(struct timespec base, double fraction, /* {{{ */
		struct timespec *target)
{
	struct timespec ts;
	double shift = base.tv_sec * fraction;
	shift += (base.tv_nsec * fraction) / 1000000000.0;
	timespec_fromdouble(fabs(shift), &ts);
	if(fraction >= 0) {
		timespec_add(*target, ts, target);
	} else {
		timespec_sub(*target, ts, target);
	}
} /* }}} */
