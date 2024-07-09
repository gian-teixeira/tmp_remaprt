#ifndef __TIMESPEC_H__
#define __TIMESPEC_H__

#include <time.h>

int timespec_cmp(struct timespec a, struct timespec b);
int timespec_is_zero(struct timespec a);

void timespec_fromdouble(double interval, struct timespec *ts);
double timespec_todouble(struct timespec ts);

void timespec_add(struct timespec a, struct timespec b, struct timespec *res);
void timespec_mult(struct timespec a, unsigned times, struct timespec *res);
void timespec_sub(struct timespec a, struct timespec b, struct timespec *res);
double timespec_sub_double(struct timespec a, struct timespec b);
void timespec_logd(unsigned verbosity, struct timespec a);
void timespec_logl(unsigned verbosity, struct timespec a);
void timespec_shift(struct timespec base, double frac, struct timespec *target);

#endif
