#!/usr/bin/python

import sys
import os
import gzip
import resource
import socket
import shutil
from collections import defaultdict
from optparse import OptionParser

from baldb import BalancerSet
from path import Path
import newpath as npathlib

# Cunha 20140726.224959 After IMC rejections, pre INFOCOM submission:
#
# This program works for a single monitor; call it multiple times to process
# multiple monitors.  For one monitor, it will look into a subdirectory
# dtrack/TSTAMP/track.gz for path measurements.  The script will convert path
# measurements from DTrack's first version (written in Python, see path.py and
# baldb.py) to our current Path structures (see newpath.py).  This script will
# also look at dtrack/TSTAMP/probes.gz and convert them to a new format.
#
# Note that the new information is stored on separate files, one file per
# destination.  The reason for this is that probe data is very large and we
# cannot load everything at once.  At the moment of this writing, the plan is
# to process all files in parallel and keep only a few minutes of each file in
# memory.

MIN_SEC_DURATION = 4*24*3600



def create_parser(): # {{{
#     def open_output_file(option, _optstr, value, parser): # {{{
#         if value.endswith('.gz'): fd = gzip.open(value, 'w')
#         else: fd = open(value, 'w')
#         setattr(parser.values, option.dest, fd)
#     # }}}

    parser = OptionParser()

    parser.add_option('--data-dir',
            dest='mondir',
            metavar='DIR',
            action='store',
            type='str',
            help='monitor directory (with dtrack/ subdir)')

    parser.add_option('--base-outdir',
            dest='outdir',
            metavar='DIR',
            action='store',
            type='str',
            help='base output dir')

#     parser.add_option('--o2',
#             dest='fmout',
#             metavar='OUTFILE',
#             action='callback',
#             callback=open_output_file,
#             nargs=1, type='str',
#             help='fastmapping output file')

    return parser
# }}}


def rmfiles_exit(opts, msg): # {{{
    sys.stdout.write(msg + '\n')
    shutil.rmtree(opts.outdir)
    sys.exit(1)
# }}}


def read_dtrack_data(opts): # {{{
    def open_dtrack_data(opts): # {{{
        head, mon = os.path.split(opts.mondir)
        if mon == '': head, mon = os.path.split(head)
        datapath = os.path.join(opts.mondir, 'dtrack')
        starttime = max(int(e) for e in os.listdir(datapath)
                if os.path.isdir(os.path.join(datapath, e)))
        datapath = os.path.join(opts.mondir, 'dtrack', str(starttime))
        pathsfd = gzip.open(os.path.join(datapath, 'track.gz'), 'r')
        probesfd = gzip.open(os.path.join(datapath, 'probes.gz'), 'r')
        return starttime, pathsfd, probesfd, mon
    # }}}
    def convert_path_balset(path, balset, mon):#{{{
        def make_simple_hop(path, jttl):#{{{
            ip, flowids, flags = path.hops[jttl], [0], ''
            iface = npathlib.Interface(ip, jttl, flowids, flags)
            return npathlib.Hop(jttl, [iface])
        #}}}
        def make_bal_hop(balhop, jttl):#{{{
            ifaces = list()
            for ip, flows in balhop.ip2flows.items():
                iface = npathlib.Interface(ip, jttl, list(flows), '')
                ifaces.append(iface)
            return npathlib.Hop(jttl, ifaces)
        #}}}
        src = socket.gethostbyname(mon)
        src = npathlib.aton(src)
        hops = list()
        jttl = 0
        for balancer in balset:
            while jttl < balancer.bttl and jttl < len(path.hops):
#                 if jttl >= len(path.hops):
#                     print balancer
#                     print path
#                     assert False
                hops.append(make_simple_hop(path, jttl))
                jttl += 1
            if jttl >= len(path.hops):
                # path is truncated because of a loop
                break
            assert (balancer.branch == 'branch' or
                    balancer.branch == path.hops[jttl])
            hops.append(make_simple_hop(path, jttl))
            jttl += 1
            for balhop in balancer.nexthops:
                hops.append(make_bal_hop(balhop, jttl))
                jttl += 1
            assert jttl == balancer.jttl
            assert (balancer.join == 'join' or
                    balancer.join == npathlib.STAR or
                    balancer.jttl >= len(path.hops) or
                    balancer.join == path.hops[jttl])
        while jttl < len(path.hops):
            hops.append(make_simple_hop(path, jttl))
            jttl += 1
        assert len(hops) >= len(path.hops)
        # hops may be longer because path truncates at loops, which can happen
        # because we pick the lowest IP in load balancers.
        return npathlib.Path(src, path.dst, path.time, hops)
    #}}}
    def getfd(dst2fd, dst, opts, prefix):#{{{
        if dst in dst2fd: return dst2fd[dst]
        fn = '%s.%s.gz' % (prefix, npathlib.ntoa(dst))
        fd = gzip.open(os.path.join(opts.outdir, fn), 'w')
        dst2fd[dst] = fd
        return fd
    #}}}

    starttime, pathfd, probesfd, mon = open_dtrack_data(opts)
    endtime = starttime

    cnt = 0
    dst2fd = dict()
    while True:
        try:
            path = Path.read(pathfd)
            balset = BalancerSet.read(pathfd)
        except IOError:
            break
        endtime = path.time
        np = convert_path_balset(path, balset, mon)
        fd = getfd(dst2fd, np.dst, opts, 'paths')
        fd.write('%s\n' % np)
        cnt += 1
        if (cnt % 1000) == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
    for fd in dst2fd.values():
        fd.close()

    if endtime - starttime < MIN_SEC_DURATION:
        rmfiles_exit(opts, 'dtrack trace too short')

    cnt = 0
    dst2fd = dict()
    while True:
        try:
            line = probesfd.readline()
        except IOError:
            break
        if not line: break
        if not line.startswith('#'): continue
        probe = npathlib.Probe.create_from_ton_str(line)
        fd = getfd(dst2fd, probe.dst, opts, 'probes')
        fd.write('%s\n' % probe)
        cnt += 1
        if (cnt % 100000) == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
    for fd in dst2fd.values():
        fd.close()
    sys.stdout.write('\n')

    pathfd.close()
    probesfd.close()
    return starttime, endtime
# }}}


def main(): # {{{
    parser = create_parser()
    opts, _args = parser.parse_args()
    if opts.mondir is None or opts.outdir is None:
        parser.parse_args(['-h'])

    resource.setrlimit(resource.RLIMIT_AS, (2147483648L, 2147483648L))

    try:
        dtrack_start, dtrack_end = read_dtrack_data(opts)
    except IOError as e:
        rmfiles_exit(opts, 'error opening dtrack logs: %s' % str(e))

    if dtrack_end - dtrack_start < MIN_SEC_DURATION:
        rmfiles_exit(opts, 'dtrack trace too short')
# }}}



if __name__ == '__main__':
    sys.exit(main())
