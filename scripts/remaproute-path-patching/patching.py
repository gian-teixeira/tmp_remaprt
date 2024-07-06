#!/usr/bin/python
from __future__ import division

import sys
import os
import resource
import argparse
import glob
from collections import defaultdict

from path import Path, Hop, Probe, aton
from loader import Loader


def create_parser(): # {{{
    class _LoadSrc2IP(argparse.Action):
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
    parser.add_argument('--mondir',
        dest='mondir',
        metavar='DIR',
        type=str,
        required=True,
        help='directory containing path and probe files for one monitor')

    parser.add_argument('--timespan',
        dest='timespan',
        metavar='SECS',
        type=float,
        default=600,
        help='time period to consider around current time [%(default)s]')

#   parser.add_argument('-s',
#       dest='src2ip',
#       action=LoadSrc2IP,
#       type=str,
#       required=True,
#       help='file with mapping from PL hostnames to IPs [%(default)s]')

    parser.add_argument('-o',
        dest='outprefix',
        type=str,
        default='out',
        help='output prefix [%(default)s]')

#   parser.add_argument('--ignore-balancers',
#       dest='flags',
#       default=set([pathlib.Path.DIFF_EXTEND, pathlib.Path.DIFF_FIX_STARS]),
#       action='store_const',
#       const=set([pathlib.Path.DIFF_EXTEND, pathlib.Path.DIFF_FIX_STARS,
#               pathlib.Path.DIFF_IGNORE_BALANCERS]),
#       help='ignore load balancers when computing changes [off]')

    return parser
# }}}


def create_file_list(mondir, fileprefix): #{{{
    fnkeys = list()
    for fpath in glob.iglob(os.path.join(mondir, '%s.*.gz' % fileprefix)):
        _mondir, key = os.path.split(fpath)
        key = key.replace('%s.' % fileprefix, '')
        key = key.replace('.gz', '')
        key = aton(key)
        fnkeys.append((fpath, key))
    return fnkeys
# }}}


class ChangeStats(object):# {{{
    def __init__(self, change):
        hops, ips = change.removed()
        self.removed_hops = len(hops)
        self.removed_ips = len(ips)
        hops, ips = change.added()
        self.added_hops = len(hops)
        self.added_ips = len(ips)
        self.changes_length = change.changes_length()
        self.detect_after_join = change.detectable_after_join()
        self.at_end = change.at_end()

    def __str__(self):
        return '%d %d %d %d %d %d %d' % (self.removed_hops, self.added_hops,
                self.removed_ips, self.added_ips,
                self.changes_length, self.detect_after_join, self.at_end)
# }}}


class SharedStats(object):#{{{
    def __init__(self, change, path):
        self.branch = change.p1[change.i1] in path
        self.join = change.p1[change.j1] is not None and \
                change.p1[change.j1] in path
        self.after_join = int()
        self.before_branch = int()
        self.rm_hop_overlap = int()
        self.rm_hops = int()
        self.rm_ip_overlap = int()
        self.rm_ips = int()

        if self.join:
            cnt = 1
            pttl = path.hopttl(change.p1[change.j1], False)
            while change.j1 + cnt < len(change.p1) and \
                    pttl + cnt < len(path) and \
                    Hop.equal(change.p1[change.j1 + cnt], path[pttl + cnt]):
                cnt += 1
            self.after_join = cnt - 1
        if self.branch:
            cnt = 1
            pttl = path.hopttl(change.p1[change.i1], False)
            while change.i1 - cnt >= 0 and pttl - cnt >= 0 and \
                    Hop.equal(change.p1[change.i1 - cnt], path[pttl - cnt]):
                cnt += 1
            self.before_branch = cnt - 1

        pifaces = path.interfaces()
        ip_overlap = set()
        ip_set = set()
        hops, _ips = change.removed()
        for hop in hops:
            self.rm_hops += 1
            if hop in path: self.rm_hop_overlap += 1
            ifs_overlap = pifaces & set(hop.ifaces)
            ip_set.update(iff.ip for iff in hop.ifaces)
            ip_overlap.update(iff.ip for iff in ifs_overlap)
        self.rm_ip_overlap = len(ip_overlap)
        self.rm_ips = len(ip_set)

    def __str__(self):
        return '%d %d %d %d %d %d %d %d' % (self.branch, self.join,
                self.after_join, self.before_branch,
                self.rm_hop_overlap, self.rm_hops,
                self.rm_ips_overlap, self.rm_ips)
#}}}


class ProbeStats(object):# {{{
    def __init__(self, change, cpath, tstamp, probeldr):
        if tstamp > probeldr.ctime: probeldr.set_time(tstamp)
        probes = probeldr.get_objects(cpath.dst)
        probed_ttls = set(p.ttl for p in probes)
        _adhops, added_ips = change.added()
        _rmhops, removed_ips = change.removed()

        self.nprobes = len(probes)
        self.nttls = len(probed_ttls)
        self.ttls_w_impacted = 0
        self.ttls_w_impacted_probed = 0
        self.ttls_w_added = 0
        self.ttls_w_added_probed = 0
        self.ttls_w_removed = 0
        self.ttls_w_removed_probed = 0
        for hop in cpath.hops:
            hop_ips = set(iff.ip for iff in hop.ifaces)
            if hop_ips & (added_ips | removed_ips):
                self.ttls_w_impacted += 1
                if hop.ttl in probed_ttls: self.ttls_w_impacted_probed += 1
            if hop_ips & added_ips:
                self.ttls_w_added += 1
                if hop.ttl in probed_ttls: self.ttls_w_added_probed += 1
            if hop_ips & removed_ips:
                self.ttls_w_removed += 1
                if hop.ttl in probed_ttls: self.ttls_w_removed_probed += 1

        self.probed_after_join = False
        if probed_ttls:
            self.probed_after_join = max(probed_ttls) >= change.j1

    def __str__(self):
        return '%d %d %d %d %d %d %d %d %d' % (self.nprobes, self.nttls,
                self.ttls_w_impacted, self.ttls_w_impacted_probed,
                self.ttls_w_added, self.ttls_w_added_probed,
                self.ttls_w_removed, self.ttls_w_removed_probed,
                self.probed_after_join)
# }}}


class SimilarityStats(object):# {{{
    def __init__(self, c1, c2):
        def jackart_index(s1, s2): # {{{
            if not bool(s1 | s2): return 1
            else: return len(s1 & s2) / len(s1 | s2)
        # }}}
        self.same_branch = c1.p1[c1.i1] == c2.p1[c2.i1]
        self.same_join = (c1.j1 >= len(c1.p1) and c2.j1 >= len(c2.p1)) or \
                         (c1.p1[c1.j1] is not None and
                            c2.p1[c2.j1] is not None and
                            c1.p1[c1.j1] == c2.p1[c2.j1])
        rmhops1, rmips1 = c1.removed()
        rmhops2, rmips2 = c2.removed()
        adhops1, adips1 = c1.added()
        adhops2, adips2 = c2.added()
        imhops1 = rmhops1 | adhops1 # im = impacted
        imhops2 = rmhops2 | adhops2
        imips1 = rmips1 | adips1
        imips2 = rmips2 | adips2
        self.rmhops_j = jackart_index(rmhops1, rmhops2)
        self.adhops_j = jackart_index(adhops1, adhops2)
        self.rmips_j = jackart_index(rmips1, rmips2)
        self.adips_j = jackart_index(adips1, adips2)
        self.imhops_j = jackart_index(imhops1, imhops2)
        self.imips_j = jackart_index(imips1, imips2)
        imhops1.add(c1.p1[c1.i1])
        imhops1.add(c1.p1[c1.j1])
        imhops2.add(c2.p1[c2.i1])
        imhops2.add(c2.p1[c2.j1])
        self.glhops_j = jackart_index(imhops1, imhops2)
        imips1.update(i.ip for i in c1.p1[c1.i1].ifaces)
        if c1.p1[c1.j1] is not None:
            imips1.update(i.ip for i in c1.p1[c1.j1].ifaces)
        imips2.update(i.ip for i in c2.p1[c2.i1].ifaces)
        if c2.p1[c2.j1] is not None:
            # TODO CHECK maybe we should account for both join points being
            # on the end of the path
            imips2.update(i.ip for i in c2.p1[c2.j1].ifaces)
        self.glips_j = jackart_index(imips1, imips2)
    def __str__(self):
        return '%d %d %f %f %f %f %f %f %f %f' % (self.same_branch,
                    self.same_join,
                    self.rmhops_j, self.adhops_j, self.imhops_j, self.glhops_j,
                    self.rmips_j, self.adips_j, self.imips_j, self.glips_j)
# }}}


def broken_change(change):#{{{
    # TODO FIXME XXX check cases when change.p1[change.i1] is None:
    if change.p1[change.i1] is None or \
            change.p1[change.i1].isstar():
        return True
    if change.p1[change.j1] is None or \
            change.p1[change.j1].isstar():
        return True
    return False
#}}}

def most_similar_change(change, ochanges):#{{{
    sim_score = 0
    sim_stats = None
    best_change = None
    for ochange in ochanges:
        if broken_change(ochange): continue
        new_stats = SimilarityStats(change, ochange)
        if new_stats.glips_j > sim_score:
            sim_score = new_stats.glips_j
            sim_stats = new_stats
            best_change = ochange
    return best_change, sim_stats
#}}}


class Stats(object): # {{{
    def __init__(self):
        self.outside_timespan = False
        self.lcz = None
        self.simstats = None
# }}}
class LCZDB(dict): # {{{
    def __lshift__(self, lcz):
        key = (lcz.p2.dst, lcz.p2.tstamp, lcz.i2)
        if key not in self: self[key] = len(self)
    def __rshift__(self, lcz):
        key = (lcz.p2.dst, lcz.p2.tstamp, lcz.i2)
        return self[key]
# }}}


def main(): # {{{
    parser = create_parser()
    opts = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2147483648L, 2147483648L))

    pathfnkeys = create_file_list(opts.mondir, 'paths')
    probefnkeys = create_file_list(opts.mondir, 'probes')
    pathldr = Loader(opts.timespan, pathfnkeys, Path.create_from_str)
    probeldr = Loader(opts.timespan, probefnkeys, Probe.create_from_str)

    ip2dsts = defaultdict(set)
    for dst, path in pathldr.key2current.items():
        for iface in path.interfaces():
            ip2dsts[iface.ip].add(dst)

    lcz2id = LCZDB()

    for tstamp, dst, cpath, npath in pathldr.iterate():
        changes = Path.diff(cpath, npath)
        # sys.stdout.write('ctime %d dst %s\n' % (tstamp, ntoa(dst)))
        # sys.stdout.write('cpath %s\n' % cpath)
        # sys.stdout.write('npath %s\n' % npath)

        for lcz in changes:
            _addhops, addips = lcz.added()
            _rmhops, rmips = lcz.removed()
            for ip in rmips: ip2dsts[ip].discard(dst) # these before we
            for ip in addips: ip2dsts[ip].add(dst)       # check brokenness
            if broken_change(lcz): continue
            lcz2id << lcz

            involved_ips = addips | rmips
            overlap_dsts = set()
            for ip in involved_ips: overlap_dsts.update(ip2dsts[ip])
            overlap_dsts.discard(dst)

            for dst in overlap_dsts:
                s = Stats()
                onpath = pathldr.get_next(dst) # surrounding measurements
                ocpath = pathldr.get_current(dst)
                if onpath is None or (abs(ocpath.tstamp - tstamp) <
                                      abs(onpath.tstamp - tstamp)):
                    # current route (ocpath) is closer, go backwards:
                    onpath = ocpath
                    ocpath = pathldr.get_previous(dst)
                    if ocpath is None: continue # dataset warmup or no changes
                assert abs(onpath.tstamp - tstamp) <= abs(ocpath.tstamp - tstamp)

                ochanges = Path.diff(ocpath, onpath)

                if abs(onpath.tstamp - tstamp) > opts.timespan:
                    # compare against current route regardless of time distance
                    s.outside_timespan = True

                s.lcz, s.simstats = most_similar_change(lcz, ochanges)
                if s.lcz is not None: lcz2id << s.lcz

                chstats = ChangeStats(lcz)
                shstats = SharedStats(lcz, ocpath)
                prstats = ProbeStats(lcz, ocpath, tstamp, probeldr)

                sys.stdout.write('%d %d %d %d %d %d %d %d %d | ' % (
                                 tstamp,
                                 lcz2id >> lcz,
                                 chstats.removed_hops,
                                 chstats.added_hops,
                                 chstats.removed_ips,
                                 chstats.added_ips,
                                 lcz.changes_length(),
                                 lcz.detectable_after_join(),
                                 lcz.at_end()))
                sys.stdout.write('%d %d %d %d %d %d | ' % (
                                 shstats.branch,
                                 shstats.before_branch,
                                 shstats.join,
                                 shstats.after_join,
                                 shstats.rm_hop_overlap,
                                 shstats.rm_ip_overlap))
                sys.stdout.write('%d %d %d %d %f %d %d | ' % (
                                 prstats.nprobes,
                                 prstats.nttls,
                                 prstats.ttls_w_removed_probed,
                                 prstats.ttls_w_removed,
                                 (prstats.ttls_w_removed_probed / prstats.ttls_w_removed) if prstats.ttls_w_removed > 0 else 0,
                                 prstats.probed_after_join,
                                 prstats.probed_after_join and lcz.detectable_after_join()))
                if s.lcz is None:
                    sys.stdout.write('0 0 0 0 0.0 0.0 0.0 0.0 0\n')
                    continue
                sys.stdout.write('%d %d %d %d %f %f %f %d\n' % (
                                 s.outside_timespan,
                                 lcz2id >> s.lcz,
                                 s.simstats.same_branch,
                                 s.simstats.same_join,
                                 s.simstats.rmips_j,
                                 s.simstats.imips_j,
                                 s.simstats.glips_j,
                                 s.lcz.detectable_at(lcz.j1 - 1)))
# }}}


FORMAT = '# tstamp lczid nrm nadd nrmips naddips chlen detctafter end\n' \
         '# travbranch nbefore travjoin nafter rmhopoverlap rmipsoverlap\n' \
         '# nprobes nttls ttlsrmprob ttlsrm rmcov probafter detafter\n' \
         '# intimespan lcz2 samebranch samejoin rmipsJ adipsJ imipsJ glipsJ\n'




if __name__ == '__main__':
    sys.exit(main())
