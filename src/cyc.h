#ifndef __CYC_HEADER__
#define __CYC_HEADER__

#include <stdarg.h>

/* this names files "prefix.%Y%m%d%H%M%S". new files are created every |period|
 * seconds. */
struct cyclic * cyc_init_periodic(const char *prefix, unsigned period);

/* this names files "prefix.N". N ranges between 0 and |nbackups| and is
 * incremented whenever the (current) prefix.0 file reaches |maxsize|. */
struct cyclic * cyc_init_filesize(const char *prefix, unsigned nbackups,
		unsigned maxsize);

void cyc_destroy(struct cyclic *cyc);

/* these function return 1 on success and 0 on failure. */
int cyc_printf(struct cyclic *cyc, const char *fmt, ...);
int cyc_vprintf(struct cyclic *cyc, const char *fmt, va_list ap);

void cyc_flush(struct cyclic *cyc);

/* these prevent the current file from changing. this is not
 * protected by any mutexes. */
void cyc_lock_file(struct cyclic *cyc);
void cyc_unlock_file(struct cyclic *cyc);

#endif
