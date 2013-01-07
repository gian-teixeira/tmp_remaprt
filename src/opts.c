#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <unistd.h>
#include <arpa/inet.h>

#include "log.h"
#include "opts.h"


void opts_usage(int argc, char **argv) /* {{{ */
{
printf("usage: %s -i IFNAME -p HOPSTR -d DST -t TTL\n", argv[0]);
printf("\n");
printf("This program performs a local remap on the path HOPSTR if a probe\n");
printf("to TTL that elicits an answer from IPADDR detects a path change.\n");
printf("Remap will be done through interface IFACE.  This program crafts\n");
printf("packets.  It needs to be run as superuser.\n");
printf("\n");
printf("\t-i IFNAME\tName of the interface to use (e.g., eth0).\n");
printf("\t-p STR\t\tHOPSTR containing the old path (see below).\n");
printf("\t-d DST\t\tIP address of the destionation.\n");
printf("\t-t TTL\t\tTTL where to start the remap (where IPADDR is located).\n");
printf("\n");
printf("HOPSTR := HOP|HOP|...|HOP\n");
printf("HOP := IFACE;IFACE;...;IFACE\n");
printf("IFACE := ip:flowid:rttmin:rttavg:rttmax:rttvar:flags\n");
} /* }}} */


struct opts * opts_parse(int argc, char **argv) /* {{{ */
{
	int opt;
	char *hopstr = NULL;

	struct opts *opts = malloc(sizeof(struct opts));
	if(!opts) logea(__FILE__, __LINE__, NULL);

	opts->iface = NULL;
	opts->path = NULL;
	opts->dst = 0;
	opts->ttl = 0;

	char *optstring = "i:p:d:t:h";

	while((opt = getopt(argc, argv, optstring)) != -1) {
		switch(opt) {
		case 'i':
			if(strlen(optarg) == 0) goto out_eval;
			opts->iface = strdup(optarg);
			break;
		case 'p':
			if(strlen(optarg) == 0) goto out_eval;
			hopstr = strdup(optarg);
			break;
		case 'd':
			if(!inet_pton(AF_INET, optarg, &opts->dst))
				goto out_eval;
			if(opts->dst == 0 || opts->dst == UINT32_MAX)
				goto out_eval;
			break;
		case 't': {
			int ttl = atoi(optarg);
			if(ttl == 0 || ttl > UINT8_MAX) goto out_eval;
			opts->ttl = (uint8_t)ttl;
			break;
		}
		default:
			goto out_eval;
			break;
		}
	}

	if(opts->iface == NULL || hopstr == NULL || opts->dst == 0 ||
			opts->ttl == 0)
		goto out_destroy;

	opts->path = path_create_str_hops(hopstr, opts->dst);
	if(opts->path == NULL) goto out_destroy;
	free(hopstr);

	return opts;

	out_eval:
	loge(LOG_FATAL, __FILE__, __LINE__);
	logd(LOG_FATAL, "invalid value for parameter -%c\n", opt);
	fprintf(stderr, "invalid value for parameter -%c\n", opt);
	out_destroy:
	if(hopstr != NULL) free(hopstr);
	opts_destroy(opts);
	return NULL;
} /* }}} */


void opts_destroy(struct opts *opts) /* {{{ */
{
	if(opts->path) path_destroy(opts->path);
	free(opts->iface);
	free(opts);
} /* }}} */
