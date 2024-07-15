#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/resource.h>

#include "path.h"
#include "demux.h"
#include "remap.h"

#include "log.h"
#include "opts.h"


int check_permissions(void) { /* {{{ */
	if(getuid() != 0) {
		logd(LOG_FATAL, "you must be root to run this program.\n");
		printf("you must be root to run this program.\n");
		return 0;
	}
	return 1;
} /* }}} */


int main(int argc, char** argv) /* {{{ */
{
	if(!check_permissions()) goto out_usage;
	dup2(STDERR_FILENO, STDIN_FILENO);

	// struct rlimit rl = { 67108864L, 67108864L };
	// if(setrlimit(RLIMIT_AS, &rl)) loge(1, __FILE__, __LINE__);

	struct opts *opts = opts_parse(argc, argv);
	if(!opts) goto out_usage;

	log_init(LOG_EXTRA, opts->logbase, 10, 65535*128);

	char *pstr = path_tostr(opts->old_path);
	logd(LOG_INFO, "path %s\n", pstr);
	free(pstr);

	if(demux_init(opts->iface)) goto out_opts;
	remap(opts);
	
	demux_destroy();
	opts_destroy(opts);
	log_destroy();
	exit(EXIT_SUCCESS);

	out_opts:
	loge(LOG_DEBUG, __FILE__, __LINE__);
	opts_destroy(opts);
	out_usage:
	opts_usage(argc, argv);
	log_destroy();
	exit(EXIT_FAILURE);
} /* }}} */
