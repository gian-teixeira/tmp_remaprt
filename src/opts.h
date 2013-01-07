#ifndef __OPTS_H__
#define __OPTS_H__

#include <inttypes.h>
#include "path.h"

struct opts {
	struct path *path;
	char *iface;
	uint32_t dst;
	uint8_t ttl;
};

/* prints command line parameter information. */
void opts_usage(int argc, char **argv);

/* returns NULL on error, otherwise a complete instance of struct opts. */
struct opts * opts_parse(int argc, char **argv);

/* frees memory used by opts */
void opts_destroy(struct opts *opts);

#endif
