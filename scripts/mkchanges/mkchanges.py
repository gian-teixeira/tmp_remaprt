#!/usr/bin/python
import sys
import os
import resource
import argparse
import glob
import gzip
import cPickle
from collections import defaultdict

import dlib
import path as pathlib
from iputils import aton


def create_parser(): # {{{
	class LoadSrc2IP(argparse.Action):
		def __call__(self, _parser, namespace, values, _optionstr=None):
			src2ip = dict()
			fd = open(values, 'r')
			for line in fd:
				src, ip = line.split()
				src2ip[src] = aton(ip)
			fd.close()
			setattr(namespace, self.dest, src2ip)

	desc = '''Computes distinct paths and path changes from a monitor's trace
	(as stored in the FastMapping dataset).  The output files contain a
	sequence of dictionaries (one per snapshot): dst2path contains the new
	distinct path to a destination and dst2change contains information about
	the path change.  A destination will be missing from the outputted
	dictionaries if there is no change.'''

	parser = argparse.ArgumentParser(description=desc)
	parser.add_argument('-m',
		dest='mondir',
		metavar='DIR',
		type=str,
		required=True,
		help='directory containing snapshot files for one monitor')

	parser.add_argument('-s',
		dest='src2ip',
		action=LoadSrc2IP,
		type=str,
		required=True,
		help='file with mapping from PL hostnames to IPs [%(default)s]')

	parser.add_argument('-o',
		dest='outprefix',
		type=str,
		default='out',
		help='output prefix [%(default)s]')

	parser.add_argument('--ignore-balancers',
		dest='flags',
		default=set([pathlib.Path.DIFF_EXTEND, pathlib.Path.DIFF_FIX_STARS]),
		action='store_const',
		const=set([pathlib.Path.DIFF_EXTEND, pathlib.Path.DIFF_FIX_STARS,
				pathlib.Path.DIFF_IGNORE_BALANCERS]),
		help='ignore load balancers when computing changes [off]')

	return parser
# }}}


def load_snapshot(tstamp, opts): # {{{
	fd = gzip.open('%s/%d.gz' % (opts.mondir, tstamp), 'r')
	snapshot = dlib.Snapshot.read(fd)
	fd.close()
	src = opts.src2ip[os.path.basename(opts.mondir)]
	return convert_dlib_snapshot(snapshot, src)
# }}}


def convert_dlib_snapshot(snapshot, src): # {{{
	for dst, path in snapshot.dst2path.items():
		snapshot.dst2path[dst] = convert_dlib_path(path, src)
	return snapshot
# }}}
def convert_dlib_path(path, src): # {{{
	hops = list()
	for ttl, hop in enumerate(path.hops):
		hops.append(convert_dlib_hop(hop, ttl))
	return pathlib.Path(src, path.dst, path.tstamp, hops)
# }}}
def convert_dlib_hop(dhop, ttl): # {{{
	ifaces = list()
	for ip, flows in dhop.ip2flows.items():
		if flows is None:
			flows = set([0])
		iface = pathlib.Interface(ip, ttl, flows, '')
		ifaces.append(iface)
	return pathlib.Hop(ttl, ifaces)
# }}}


def main(): # {{{
	parser = create_parser()
	opts = parser.parse_args()
	resource.setrlimit(resource.RLIMIT_AS, (2147483648L, 2147483648L))

# 	logger = logging.getLogger()
# 	logger.setLevel(logging.DEBUG)
# 	formatter = logging.Formatter('%(message)s')
# 	loghandler = logging.handlers.RotatingFileHandler(opts.logfn,
# 			maxBytes=64*1024*1024, backupCount=5)
# 	loghandler.setFormatter(formatter)
# 	logger.addHandler(loghandler)

	timestamps = sorted(int(os.path.basename(fn).split('.')[0])
			for fn in glob.glob('%s/*.gz' % opts.mondir))

	osnap = load_snapshot(timestamps[0], opts)

	dst2measurements = defaultdict(lambda: 0)

	fd_dst2paths = gzip.open(opts.outprefix + '.dst2path.gz', 'w')
	fd_dst2changes = gzip.open(opts.outprefix + '.dst2change.gz', 'w')

	for i in range(1, len(timestamps)):
		sys.stdout.write('processing timestamp %d/%d\n' % (i, len(timestamps)))
		try: nsnap = load_snapshot(timestamps[i], opts)
		except IOError: continue
		dst2path = dict()
		dst2change = dict()
		for dst, opath in osnap.dst2path.items():
			if dst not in nsnap.dst2path:
				continue
			npath = nsnap.dst2path[dst]
			changes = pathlib.Path.diff(opath, npath, opts.flags)

			if not changes:
				dst2measurements[dst] += 1
				continue
			else:
				for change in changes:
					change.nmeasurements = dst2measurements[dst]
				dst2path[dst] = opath
				dst2change[dst] = changes
				dst2measurements[dst] = 0

		cPickle.dump(dst2path, fd_dst2paths)
		cPickle.dump(dst2change, fd_dst2changes)
		osnap = nsnap

	fd_dst2paths.close()
	fd_dst2changes.close()
# }}}


if __name__ == '__main__':
	sys.exit(main())
