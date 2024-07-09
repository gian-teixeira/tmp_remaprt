#ifndef __OPTS_H__
#define __OPTS_H__

#include <inttypes.h>
#include "path.h"

struct opts {
	// New members that supports offline remaps (focused on testing)
	struct path *old_path;
	struct path *new_path;

	char *iface;
	char *logbase;
	uint32_t dst;
	uint8_t ttl;
	uint16_t icmpid;
};

/* prints command line parameter information. */
void opts_usage(int argc, char **argv);

/* returns NULL on error, otherwise a complete instance of struct opts. */
struct opts * opts_parse(int argc, char **argv);

/* frees memory used by opts */
void opts_destroy(struct opts *opts);

#endif
