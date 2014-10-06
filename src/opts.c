#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <unistd.h>
#include <arpa/inet.h>
#include <assert.h>

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
printf("\t-d DST\t\tIP address of the destination.\n");
printf("\t-t TTL\t\tTTL where to start the remap (where IPADDR is located).\n");
printf("\t-x ICMPID\tThe ICMP ID used to identify probes.\n");
printf("\t-l LOGBASE\tBase name for the log file.\n");
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
	if(!opts) {
		perror(NULL);
		exit(EXIT_FAILURE);
	}

	opts->iface = NULL;
	opts->path = NULL;
	opts->logbase = NULL;
	opts->dst = 0;
	opts->ttl = 0;

	char *optstring = "i:p:d:t:l:x:h";

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
		case 'x': {
			int icmpid = atoi(optarg);
			if(icmpid == 0 || icmpid > UINT16_MAX) goto out_eval;
			opts->icmpid = (uint16_t)icmpid;
			break;
		}
		case 'l': {
			if(strlen(optarg) == 0) goto out_eval;
			opts->logbase = strdup(optarg);
			break;
		}
		default:
			goto out_eval;
			break;
		}
	}

	if(opts->iface == NULL || hopstr == NULL || opts->dst == 0 ||
			opts->ttl == 0 || opts->logbase == NULL)
		goto out_destroy;

	opts->path = path_create_str_hops(hopstr, opts->dst);
	if(opts->path == NULL) goto out_destroy;
	assert(path_length(opts->path) < 33);
	free(hopstr);

	return opts;

	out_eval:
	perror(NULL);
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
	free(opts->logbase);
	free(opts);
} /* }}} */
