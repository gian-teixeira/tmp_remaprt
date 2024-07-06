#!/usr/bin/env python

import sys
import unittest

from struct import pack, unpack
from socket import inet_ntoa, inet_aton

STAR = unpack('!I', '\xff\xff\xff\xff')[0]
def aton(string): return unpack('!I', inet_aton(string))[0]
def asip(integer): return inet_ntoa(pack('!I', integer))
def ntoa(integer): return inet_ntoa(pack('!I', integer))


class Interface(object): # {{{
    def __init__(self, ip, ttl, flowids, flags, # {{{
            rttmin=0.0, rttavg=0.0, rttmax=0.0, rttvar=0.0):
        self.ip = int(ip)
        self.ttl = int(ttl)
        self.flowids = set(flowids)
        self.flags = str(flags)
        self.rttmin = float(rttmin)
        self.rttavg = float(rttavg)
        self.rttmax = float(rttmax)
        self.rttvar = float(rttvar)
    # }}}

    def __str__(self): # {{{
        return '%s:%s:%s:%s' % (ntoa(self.ip),
                ','.join(str(i) for i in self.flowids),
                '%.2f,%.2f,%.2f,%.2f' % (self.rttmin, self.rttavg,
                    self.rttmax, self.rttvar),
                self.flags)
    # }}}

    def __cmp__(self, other): # {{{
        return (self.ip > other.ip) - (self.ip < other.ip)
    # }}}

    def __hash__(self): # {{{
        return hash(self.ip)
    # }}}

    def copy(self): # {{{
        return Interface(self.ip, self.ttl, set(self.flowids), str(self.flags),
                self.rttmin, self.rttavg, self.rttmax, self.rttvar)
    # }}}

    @staticmethod
    def create_from_str(string, ttl): # {{{
        ip, flowids, rtts, flags = string.split(':')
        ip = aton(ip)
        flowids = set(int(i) for i in flowids.split(',')) if flowids else set()
        rmin, ravg, rmax, rvar = rtts.split(',')
        return Interface(ip, ttl, flowids, flags, rmin, ravg, rmax, rvar)
    # }}}
# }}}

class Hop(object): # {{{
    def __init__(self, ttl, ifaces): # {{{
        self.ttl = int(ttl)
        self.ifaces = list(ifaces)
        self.ifaces.sort()
    # }}}

    def __contains__(self, ip): # {{{
        for iface in self.ifaces:
            if iface.ip == ip:
                return True
        return False
    # }}}

    def __str__(self): return ';'.join(str(iface) for iface in self.ifaces)
    def __eq__(self, other): return Hop.equal(self, other)
    def __ne__(self, other): return not Hop.equal(self, other)
    def __hash__(self): return hash(tuple(i for i in self.ifaces))

    def copy(self): # {{{
        return Hop(self.ttl, [iface.copy() for iface in self.ifaces])
    # }}}

    def isstar(self): # {{{
        if len(self.ifaces) > 1: return False
        iface = iter(self.ifaces).next()
        if iface.ip != STAR: return False
        return True
    # }}}

    def setfirst(self, first): # {{{
        assert first in self
        i = 0
        while self.ifaces[i].ip != first:
            i += 1
        dstif = self.ifaces[i]
        del self.ifaces[i]
        self.ifaces.insert(0, dstif)
    # }}}
    def getfirst(self): return self.ifaces[0].ip
    def getfirststr(self): return ntoa(self.ifaces[0].ip)

    @staticmethod
    def create_from_str(string, ttl): # {{{
        ifaces = list()
        ifstrings = string.split(';')
        for ifstr in ifstrings:
            iface = Interface.create_from_str(ifstr, ttl)
            ifaces.append(iface)
        return Hop(ttl, ifaces)
    # }}}

    @staticmethod
    def equal(h1, h2, ignore_balancers=False): # {{{
        if ignore_balancers:
            h1iffs = set(iff.ip for iff in h1.ifaces)
            h2iffs = set(iff.ip for iff in h2.ifaces)
            return bool(h1iffs & h2iffs)
        return set([i.ip for i in h1.ifaces]) == set([j.ip for j in h2.ifaces])
    # }}}
# }}}

class Path(object): # {{{
    FLAG_NO_REACHABILITY = 'no-reachability'
    DIFF_FIX_STARS = 'fix-stars'
    DIFF_EXTEND = 'extend-missing-hops'
    DIFF_IGNORE_BALANCERS = 'ignore-balancers'
    DIFF_NO_FIX_BALANCER = 'diff-no-fix-balancer'

    def __init__(self, src, dst, tstamp, hops, flags=set(), alias=-1): # {{{
        # pylint: disable=W0102
        self.src = int(src)
        self.dst = int(dst)
        self.tstamp = int(tstamp)
        self.hops = list(hops)
        self.flags = set(flags)
        self.alias = int(alias)
        self._check_reachability()
    # }}}

    def __str__(self): # {{{
        hopstr = '|'.join(str(hop) for hop in self.hops)
        pathstr = '%s %s %d' % (ntoa(self.src), ntoa(self.dst), self.tstamp)
        if hopstr:
            pathstr += ' %s' % hopstr
        return pathstr
    # }}}

    def __getitem__(self, ttl): # {{{
        try: return self.hops[ttl]
        except IndexError:
            if Path.FLAG_NO_REACHABILITY in self.flags:
                return None
            return self.hops[-1]
    # }}}

    def __len__(self): return len(self.hops)
    def __ne__(self, other): return bool(Path.diff(self, other))
    def __eq__(self, other): return not self.__ne__(other)
    def __contains__(self, hop): return self.hopttl(hop, False) != -1

    def _check_reachability(self): # {{{
        self._remove_star_tail()
        if len(self.hops) == 0 or self.dst not in self.hops[-1]:
            self.flags.add(Path.FLAG_NO_REACHABILITY)
        else:
            self.flags.discard(Path.FLAG_NO_REACHABILITY)
            self.hops[-1].setfirst(self.dst)
    # }}}

    def _remove_star_tail(self): # {{{
        while self.hops and self.hops[-1].isstar():
            del self.hops[-1]
    # }}}

    def copy(self): # {{{
        hops = [hop.copy() for hop in self.hops]
        return Path(self.src, self.dst, self.tstamp, hops, self.flags,
                self.alias)
    # }}}

    def hopttl(self, hop, ignore_balancers): # {{{
        assert not hop.isstar() # doesn't make much sense.
        for i, selfhop in enumerate(self.hops):
            if Hop.equal(selfhop, hop, ignore_balancers):
                return i
        return -1
    # }}}

    def interfaces(self): # {{{
        ifaces = set()
        for hop in self.hops:
            if hop.isstar(): continue
            ifaces.update(hop.ifaces)
        return ifaces
    # }}}

    def hasloop(self): # {{{
        interfaces = set()
        balancer_ifaces = set()
        for hop in self.hops:
            if hop.isstar():
                continue

            if interfaces.intersection(hop.ifaces):
                return True

            if len(hop.ifaces) == 1:
                interfaces.update(balancer_ifaces)
                balancer_ifaces = set()
                interfaces.update(hop.ifaces)
            else:
                balancer_ifaces.update(hop.ifaces)
    # }}}

    @staticmethod
    def detects_change(p1, p2, ttl, ignore_balancers=False): # {{{
        assert ttl <= len(p1)
        if ttl == len(p1):
            assert Path.FLAG_NO_REACHABILITY in p1.flags
            if ttl >= len(p2) and Path.FLAG_NO_REACHABILITY in p2.flags:
                return False
            elif ttl < len(p2) and p2[ttl].isstar():
                return False
            else:
                return True

        hop1 = p1[ttl]
        if ttl >= len(p2):
            if Path.FLAG_NO_REACHABILITY in p2.flags:
                return True
            elif p2.dst in hop1:
                return False
            else:
                return True

        hop2 = p2[ttl]
        if hop2.isstar():
            return False
        elif hop1.isstar() and not hop2.isstar() and \
                p1.hopttl(hop2, ignore_balancers) != -1:
            return True

        return not Hop.equal(hop1, hop2, ignore_balancers)
    # }}}

    @staticmethod
    def inversion(p1, p2, ignore_balancers): # {{{
        marker = -1
        for hop in p2.hops:
            if hop.isstar():
                continue
            ttl = p1.hopttl(hop, ignore_balancers)
            if ttl == -1:
                continue
            if ttl < marker:
                return True
            marker = ttl
        return False
    # }}}

    @staticmethod
    def create_from_str(string): # {{{
        fields = string.split()
        if len(fields) == 3: fields.append('')
        src, dst, tstamp, hopstrings = fields
        src = aton(src)
        dst = aton(dst)
        tstamp = int(tstamp)
        hops = list()
        if not hopstrings: return Path(src, dst, tstamp, hops)
        for hopstr in hopstrings.split('|'):
            hop = Hop.create_from_str(hopstr, len(hops))
            hops.append(hop)
        return Path(src, dst, tstamp, hops)
    # }}}

    @staticmethod
    def diff(p1, p2, flags=set([DIFF_FIX_STARS, DIFF_EXTEND])): # {{{
        # pylint: disable=W0102
        ignore_balancers = Path.DIFF_IGNORE_BALANCERS in flags
        assert p1.dst == p2.dst
        assert p1.tstamp <= p2.tstamp
        changes = list()
        i1 = 0
        i2 = 0
        while i1 < len(p1) and i2 < len(p2):
            if Hop.equal(p1[i1], p2[i2], ignore_balancers):
                i1 += 1
                i2 += 1
                continue
            j1, j2 = Path._diff_join(p1, p2, i1, i2, ignore_balancers)
            if Path.DIFF_FIX_STARS in flags:
                i1, i2, j1, j2 = Path._diff_fix_stars(p1, p2, i1, i2, j1, j2,
                        flags)
            if j1 > i1 or j2 > i2:
                changes.append(PathChange(p1, p2, i1, i2, j1, j2))
            i1 = j1
            i2 = j2

        if not changes and Path.DIFF_EXTEND in flags:
            assert i1 == i2
            Path._diff_extend(p1, p2, i1)
        elif i1 != len(p1) or i2 != len(p2):
            changes.append(PathChange(p1, p2, i1, i2, len(p1), len(p2)))
        return changes
    # }}}

    @staticmethod
    def _diff_join(p1, p2, i1, i2, ignore_balancers): # {{{
        for j2 in range(i2, len(p2)):
            hop2 = p2[j2]
            if hop2.isstar():
                continue
            for j1 in range(i1, len(p1)):
                hop1 = p1[j1]
                if Hop.equal(hop1, hop2, ignore_balancers):
                    return j1, j2
        assert not ignore_balancers or \
                Path.FLAG_NO_REACHABILITY in p1.flags or \
                Path.FLAG_NO_REACHABILITY in p2.flags
        return len(p1), len(p2)
    # }}}

    @staticmethod
    def _diff_fix_stars(p1, p2, i1, i2, j1, j2, flags): # {{{
        def _fix_1hop(ttl1, ttl2, flags): # {{{
            h1 = p1[ttl1]
            h2 = p2[ttl2]
            if h1.isstar() and h2.isstar(): return True
            if not (h1.isstar() or h2.isstar()): return False

            if h1.isstar():
                starp = p1
                stari = ttl1
                starj = j1
                srch = h2
            else:
                starp = p2
                stari = ttl2
                starj = j2
                srch = h1

            if Path.DIFF_NO_FIX_BALANCER in flags and len(srch.ifaces) > 1:
                return False

            # not fixing if interface is already in another hop:
            if max(srch.ifaces[0].ip in hop for hop in starp.hops):
                return False

            # not fixing dst if it is not the last hop in the path:
            if srch.ifaces[0].ip == starp.dst and stari+1 != starj:
                return False

            newh = srch.copy()
            starp.hops[stari] = newh
            return True
        # }}}

        threshold = j1 - i1 if (j1 - i1 < j2 - i2) else j2 - i2
        i = 0
        while i < threshold:
            if not _fix_1hop(i1+i, i2+i, flags):
                break
            i += 1
        i1 += i
        i2 += i
        threshold -= i
        i = 0
        while i < threshold:
            t1 = j1 - i - 1
            t2 = j2 - i - 1
            if not _fix_1hop(t1, t2, flags):
                break
            i += 1
        j1 -= i
        j2 -= i
        assert i1 <= j1
        assert i2 <= j2
        p1._check_reachability() # pylint: disable=W0212
        p2._check_reachability() # pylint: disable=W0212

        return i1, i2, j1, j2
    # }}}

    @staticmethod
    def _diff_extend(p1, p2, i): # {{{
        assert i == len(p1) or i == len(p2)
        shorter = p1 if len(p1) < len(p2) else p2
        longer = p2 if len(p1) < len(p2) else p1
        for ttl in range(i, len(longer)):
            assert ttl == len(shorter)
            hop = longer[ttl].copy()
            shorter.hops.append(hop)
        shorter._check_reachability() # pylint: disable=W0212
    # }}}
# }}}

class PathChange(object): # {{{
    def __init__(self, p1, p2, i1, i2, j1, j2, nmeasurements=0): # {{{
        self.p1 = p1
        self.p2 = p2
        self.i1 = i1-1
        self.i2 = i2-1
        self.j1 = j1
        self.j2 = j2
        self.nmeasurements = nmeasurements
    # }}}

    def __str__(self): # {{{
        return 'change i1=%d j1=%d i2=%d j2=%d\n%s\n%s' % (self.i1, self.j1,
                self.i2, self.j2, self.p1, self.p2)
    # }}}

    def added(self):#{{{
        hops = set()
        ips = set()
        for hop in self.p2.hops[self.i2+1:self.j2]:
            if hop.isstar(): continue
            ttl = self.p1.hopttl(hop, False)
            if ttl < self.i1 or ttl > self.j1:
                hops.add(hop)
                ips.update(iff.ip for iff in hop.ifaces)
        return hops, ips
    #}}}

    def removed(self):#{{{
        hops = set()
        ips = set()
        for hop in self.p1.hops[self.i1+1:self.j1]:
            if hop.isstar(): continue
            ttl = self.p2.hopttl(hop, False)
            if ttl < self.i2 or ttl > self.j2:
                hops.add(hop)
                ips.update(iff.ip for iff in hop.ifaces)
        return hops, ips
    #}}}

    def detectable_at(self, ttl):
        return ttl > self.i1 and (ttl < self.j1 or self.detectable_after_join())

    def changes_length(self):
        return (self.j1 - self.i1) != (self.j2 - self.i2)

    def detectable_after_join(self):
        return self.j1 != self.j2

    def at_end(self):
        return self.j1 == len(self.p1) or self.j2 == len(self.p2)
# }}}

class PathDB(object): # {{{
    class Entry(list): # {{{
        def __init__(self, dst):
            super(PathDB.Entry, self).__init__()
            self.dst = dst
            self.maxalias = 0
        def findremove(self, obj):
            idx = None
            try: idx = self.index(obj)
            except ValueError: return None
            path = self[idx]
            del self[idx]
            return path
    # }}}

    def __init__(self, maxaliases=sys.maxint): # {{{
        self.maxaliases = maxaliases
        self.dst2entry = dict()
    # }}}

    def alias(self, path): # {{{
        entry = self.dst2entry.setdefault(path.dst, PathDB.Entry(path.dst))
        newp = path.copy()
        oldp = entry.findremove(newp)
        if oldp is None:
            newp.alias = entry.maxalias
            path.alias = entry.maxalias
            entry.append(newp)
            entry.maxalias += 1
            while len(entry) > self.maxaliases:
                del entry[0]
        else:
            assert oldp.alias >= 0
            assert len(entry) <= self.maxaliases
            entry.append(oldp)
            path.alias = oldp.alias
    # }}}
# }}}

class Probe(object):# {{{
    def __init__(self, tstamp, dst, ttl, flowid, ip, detection=False):# {{{
        self.tstamp = int(tstamp)
        self.dst = int(dst)
        self.ttl = int(ttl)
        self.flowid = int(flowid)
        self.ip = int(ip)
        self.detection = bool(detection)
    # }}}

    def __str__(self):# {{{
        return '%d|%s|%d|%d|%s|%d' % (self.tstamp, ntoa(self.dst), self.ttl,
                                      self.flowid, ntoa(self.ip),
                                      self.detection)
    # }}}

    @staticmethod
    def create_from_str(string):# {{{
        fields = string.split('|')
        tstamp = int(fields[0])
        dst = aton(fields[1])
        ttl = int(fields[2])
        flowid = int(fields[3])
        ip = aton(fields[4])
        detection = bool(fields[5])
        return Probe(tstamp, dst, ttl, flowid, ip, detection)
    # }}}

    @staticmethod
    def create_from_ton_str(string):# {{{
        '''reads TON's dataset format (first DTrack written in Python)'''
        VALID_RESPONSES = set(['change', 'match'])
        if not string.startswith('#'): raise ValueError('unrecognized format')
        fields = string.split()
        assert fields[1] in VALID_RESPONSES
        detection = True if fields[1] == 'change' else False
        tstamp = int(fields[2])
        dst = aton(fields[3])
        ttl = int(fields[4])
        flowid = int(fields[5])
        ip = aton(fields[6])
        return Probe(tstamp, dst, ttl, flowid, ip, detection)
    # }}}
# }}}



class PathTester(unittest.TestCase): # {{{
    def test_1(self): # {{{
        # pylint: disable=C0301
        p1str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|7.7.7.7:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        p2str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|12.12.12.12:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|7.7.7.7:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        p3str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|12.12.12.12:0:0.00,0.00,0.00,0.00:;13.13.13.13:1:0.00,0.00,0.00,0.00:;14.14.14.14:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|7.7.7.7:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        p4str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|12.12.12.12:1:0.00,0.00,0.00,0.00:;13.13.13.13:2:0.00,0.00,0.00,0.00:;5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|7.7.7.7:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)
        p3 = Path.create_from_str(p3str)
        p4 = Path.create_from_str(p4str)

        r = Path.diff(p1, p1, set())
        self.assertEqual(len(r), 0)
        r = Path.diff(p1, p2, set())
        self.assertEqual(len(r), 1)
        r = Path.diff(p1, p3, set())
        self.assertEqual(len(r), 1)
        r = Path.diff(p1, p4, set())
        self.assertEqual(len(r), 1)
    # }}}

    def test_2(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:0:0.0,0.0,0.0,0.0:;4.4.4.4:1:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:;8.8.8.8:1:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'
        pstr2 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:0:0.0,0.0,0.0,0.0:;4.4.4.4:1:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:;8.8.8.8:1:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'
        pstr3 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:1:0.0,0.0,0.0,0.0:;4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:;8.8.8.8:1:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'
        pstr4 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:1:0.0,0.0,0.0,0.0:;4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:1:0.0,0.0,0.0,0.0:;8.8.8.8:0:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'
        pstr5 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|13.13.13.13:0:0.0,0.0,0.0,0.0:;14.14.14.14:1:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:1:0.0,0.0,0.0,0.0:;8.8.8.8:0:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'
        pstr6 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.0,0.0,0.0,0.0:|4.4.4.4:1:0.0,0.0,0.0,0.0:;3.3.3.3:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:;6.6.6.6:1:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:;8.8.8.8:1:0.0,0.0,0.0,0.0:|11.11.11.11:0:0.0,0.0,0.0,0.0:'

        p1 = Path.create_from_str(pstr1)
        p2 = Path.create_from_str(pstr2)
        p3 = Path.create_from_str(pstr3)
        p4 = Path.create_from_str(pstr4)
        p5 = Path.create_from_str(pstr5)
        p6 = Path.create_from_str(pstr6)

        r = Path.diff(p1, p1, set())
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p2, set())
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p3, set())
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p4, set())
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p5, set())
        self.assertEqual(len(r), 1)

        r = Path.diff(p1, p6, set())
        self.assertEqual(len(r), 0)
    # }}}

    def test_3(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr2 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr3 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|13.13.13.13:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr4 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|15.15.15.15:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr5 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(pstr1)
        p2 = Path.create_from_str(pstr2)
        p3 = Path.create_from_str(pstr3)
        p4 = Path.create_from_str(pstr4)
        p5 = Path.create_from_str(pstr5)

        r = Path.diff(p1, p1, set())
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p2, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)
        self.assertEqual(str(p1), str(p2))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p3, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p1), str(p2))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p4, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p1), str(p2))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p5, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)
        self.assertEqual(str(p1), str(p2))
        self.assertEqual(str(p5), str(p2))
    # }}}

    def test_4(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr2 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr3 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr4 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|16.16.16.16:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr5 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr6 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|14.14.14.14:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr7 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(pstr1)
        p2 = Path.create_from_str(pstr2)
        p3 = Path.create_from_str(pstr3)
        p4 = Path.create_from_str(pstr4)
        p5 = Path.create_from_str(pstr5)
        p6 = Path.create_from_str(pstr6)
        p7 = Path.create_from_str(pstr7)

        r = Path.diff(p1, p1, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)

        r = Path.diff(p1, p2, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)
        self.assertEqual(str(p1), str(p2))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p3, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)
        self.assertEqual(str(p1), str(p3))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p4, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p1), str(p2))
        p1 = Path.create_from_str(pstr1)

        r = Path.diff(p1, p5, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 0)
        self.assertEqual(str(p1), str(p5))

        r = Path.diff(p6, p7, set([Path.DIFF_FIX_STARS]))
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p7), str(p2))
    # }}}

    def test_5(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr2 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:'
        pstr3 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:'
        pstr4 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:'
        pstr5 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|13.13.13.13:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(pstr1)
        p2 = Path.create_from_str(pstr2)
        p3 = Path.create_from_str(pstr3)
        p4 = Path.create_from_str(pstr4)
        p5 = Path.create_from_str(pstr5)

        flags = set([Path.DIFF_FIX_STARS, Path.DIFF_EXTEND])

        r = Path.diff(p1, p2, flags)
        self.assertEqual(len(r), 0)
        self.assertEqual(pstr1, str(p2))

        r = Path.diff(p1, p3, flags)
        self.assertEqual(len(r), 0)
        self.assertEqual(pstr1, str(p3))

        r = Path.diff(p1, p4, flags)
        self.assertEqual(len(r), 0)
        self.assertEqual(pstr1, str(p4))

        r = Path.diff(p1, p5, flags)
        self.assertEqual(len(r), 2)
        self.assertEqual(pstr5, str(p5))
    # }}}

    def test_6(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 255.255.255.255:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:0|255.255.255.255:0:0.00,0.00,0.00,0.00:'
        pstr2 = '1.1.1.1 11.11.11.11 1'

        p1 = Path.create_from_str(pstr1)

        self.assertEqual(str(p1), pstr2)
    # }}}

    def test_7(self): # {{{
        # pylint: disable=C0301
        p1str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:;11.11.11.11:1:0.00,0.00,0.00,0.00:'
        p2str = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:;11.11.11.11:1:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)

        r = Path.diff(p1, p2, set())
        self.assertEqual(len(r), 1)

        r = Path.diff(p1, p2, set([Path.DIFF_IGNORE_BALANCERS]))
        self.assertEqual(len(r), 0)
    # }}}

    def test_8(self): # {{{
        # pylint: disable=C0301
        p1str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:0:0.0,0.0,0.0,0.0:|4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'
        p2str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'
        p3str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|2.2.2.2:0:0.0,0.0,0.0,0.0:|4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'
        p4str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|12.12.12.12:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'
        p5str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|12.12.12.12:0:0.0,0.0,0.0,0.0:|4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)
        p3 = Path.create_from_str(p3str)
        p4 = Path.create_from_str(p4str)
        p5 = Path.create_from_str(p5str)

        r = Path.diff(p1, p2)
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p3), str(p2))

        r = Path.diff(p1, p4)
        self.assertEqual(len(r), 1)
        self.assertEqual(str(p5), str(p4))
    # }}}

    def test_9(self): # {{{
        # pylint: disable=C0301
        p1str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|2.2.2.2:0:0.0,0.0,0.0,0.0:|3.3.3.3:0:0.0,0.0,0.0,0.0:|4.4.4.4:0:0.0,0.0,0.0,0.0:|5.5.5.5:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|7.7.7.7:0:0.0,0.0,0.0,0.0:|8.8.8.8:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'
        p2str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|12.12.12.12:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|14.14.14.14:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|17.17.17.17:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|18.18.18.18:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)
        p3 = Path.create_from_str(p2str)

        r = Path.diff(p1, p2)
        self.assertEqual(2, len(r))
        self.assertEqual(str(p2), str(p3))

        self.assertFalse(Path.detects_change(p1, p2, 2))
        self.assertTrue(Path.detects_change(p1, p2, 1))
    # }}}

    def test_A(self): # {{{
        # pylint: disable=C0301
        p1str = '134.34.246.5 202.158.202.162 1283576900 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|129.143.1.149:0:0.00,0.00,0.00,0.00:|188.1.233.229:0:0.00,0.00,0.00,0.00:|188.1.145.81:0:0.00,0.00,0.00,0.00:|188.1.145.49:0:0.00,0.00,0.00,0.00:|62.40.124.33:0:0.00,0.00,0.00,0.00:|62.40.112.50:0:0.00,0.00,0.00,0.00:|202.179.241.41:0:0.00,0.00,0.00,0.00:|202.179.241.26:0:0.00,0.00,0.00,0.00:|202.179.241.62:0:0.00,0.00,0.00,0.00:|203.181.248.250:0:0.00,0.00,0.00,0.00:|117.103.111.134:0:0.00,0.00,0.00,0.00:|202.158.194.6::0.00,0.00,0.00,0.00:;202.179.241.73::0.00,0.00,0.00,0.00:;202.179.249.62::0.00,0.00,0.00,0.00:|117.103.111.201:0:0.00,0.00,0.00,0.00:|117.103.111.189:0:0.00,0.00,0.00,0.00:|202.158.194.145:0:0.00,0.00,0.00,0.00:|202.158.194.6:0:0.00,0.00,0.00,0.00:|202.158.194.18:0:0.00,0.00,0.00,0.00:|202.158.194.34:0:0.00,0.00,0.00,0.00:|202.158.202.162:0:0.00,0.00,0.00,0.00:'
        p2str = '1.1.1.1 9.9.9.9 0 1.1.1.1:0:0.0,0.0,0.0,0.0:|12.12.12.12:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|14.14.14.14:0:0.0,0.0,0.0,0.0:|6.6.6.6:0:0.0,0.0,0.0,0.0:|17.17.17.17:0:0.0,0.0,0.0,0.0:|255.255.255.255:0:0.0,0.0,0.0,0.0:|18.18.18.18:0:0.0,0.0,0.0,0.0:|9.9.9.9:0:0.0,0.0,0.0,0.0:'

        p1 = Path.create_from_str(p1str)
        self.assertTrue(p1.hasloop())

        p2 = Path.create_from_str(p2str)
        self.assertFalse(p2.hasloop())
    # }}}

    def test_B(self): # {{{
        # pylint: disable=C0301

        p1str = '134.34.246.5 202.75.208.1 1283737758 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|129.143.1.149:0:0.00,0.00,0.00,0.00:|188.1.233.229:0:0.00,0.00,0.00,0.00:|188.1.145.77:0:0.00,0.00,0.00,0.00:|188.1.146.50:0:0.00,0.00,0.00,0.00:|188.1.145.73:0:0.00,0.00,0.00,0.00:|188.1.145.69:0:0.00,0.00,0.00,0.00:|80.156.160.141:0:0.00,0.00,0.00,0.00:|194.25.6.50:0:0.00,0.00,0.00,0.00:|212.184.26.234:0,10,3,5,13:0.00,0.00,0.00,0.00:;217.6.49.174:1,6,7:0.00,0.00,0.00,0.00:;217.6.49.178:2,4,8,11,12,15:0.00,0.00,0.00,0.00:|219.158.30.41:0:0.00,0.00,0.00,0.00:|219.158.11.25:0:0.00,0.00,0.00,0.00:|219.158.20.26:0:0.00,0.00,0.00,0.00:|221.12.1.150:0:0.00,0.00,0.00,0.00:|124.160.58.190:8,1,5,7:0.00,0.00,0.00,0.00:;124.160.58.194:0,2,3,4,6,9,10:0.00,0.00,0.00,0.00:|202.75.208.1:0:0.00,0.00,0.00,0.00:'
        p2str = '134.34.246.5 202.75.208.1 1283738138 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|129.143.1.149:0:0.00,0.00,0.00,0.00:|188.1.233.229:0:0.00,0.00,0.00,0.00:|188.1.145.77:0:0.00,0.00,0.00,0.00:|188.1.146.50:0:0.00,0.00,0.00,0.00:|188.1.145.73:0:0.00,0.00,0.00,0.00:|188.1.145.69:0:0.00,0.00,0.00,0.00:|80.156.160.141:0:0.00,0.00,0.00,0.00:|194.25.6.50:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|219.158.30.41:0:0.00,0.00,0.00,0.00:|219.158.11.25:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)
        changes = Path.diff(p1, p2)
        self.assertEqual(len(changes), 0)

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)
        changes = Path.diff(p1, p2, set([Path.DIFF_EXTEND,
                Path.DIFF_FIX_STARS, Path.DIFF_IGNORE_BALANCERS]))
        self.assertEqual(len(changes), 0)
    # }}}

    def test_C(self): # {{{
        # pylint: disable=C0301

        p1str = '134.34.246.5 210.77.139.166 1283847628 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|129.143.1.149:0:0.00,0.00,0.00,0.00:|188.1.233.229:0:0.00,0.00,0.00,0.00:|188.1.145.77:0:0.00,0.00,0.00,0.00:|188.1.146.50:0:0.00,0.00,0.00,0.00:|188.1.145.73:0:0.00,0.00,0.00,0.00:|188.1.145.69:0:0.00,0.00,0.00,0.00:|80.156.160.141:0:0.00,0.00,0.00,0.00:|194.25.6.50:0:0.00,0.00,0.00,0.00:|212.184.26.234:10:0.00,0.00,0.00,0.00:;217.6.49.174:0,1:0.00,0.00,0.00,0.00:;217.6.49.178:2,5:0.00,0.00,0.00,0.00:|219.158.25.13:0:0.00,0.00,0.00,0.00:|219.158.3.61:0:0.00,0.00,0.00,0.00:|219.158.4.37:0:0.00,0.00,0.00,0.00:|202.96.12.30:0:0.00,0.00,0.00,0.00:|61.148.146.242:0:0.00,0.00,0.00,0.00:|61.148.154.98:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|210.77.139.177:0:0.00,0.00,0.00,0.00:|210.77.139.166:0:0.00,0.00,0.00,0.00:'

        p2str = '134.34.246.5 210.77.139.166 1283848003 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|129.143.1.149:0:0.00,0.00,0.00,0.00:|188.1.233.229:0:0.00,0.00,0.00,0.00:|188.1.145.77:0:0.00,0.00,0.00,0.00:|188.1.146.50:0:0.00,0.00,0.00,0.00:|188.1.145.73:0:0.00,0.00,0.00,0.00:|188.1.145.69:0:0.00,0.00,0.00,0.00:|80.156.160.141:0:0.00,0.00,0.00,0.00:|194.25.6.50:0:0.00,0.00,0.00,0.00:|212.184.26.234:3,4,8,9,10,11,13:0.00,0.00,0.00,0.00:;217.6.49.174:0,1,15,14,7:0.00,0.00,0.00,0.00:;217.6.49.178:2,12,5,6:0.00,0.00,0.00,0.00:|219.158.25.13:0:0.00,0.00,0.00,0.00:|219.158.3.61:0:0.00,0.00,0.00,0.00:|219.158.4.37:0:0.00,0.00,0.00,0.00:|202.96.12.30:0:0.00,0.00,0.00,0.00:|61.148.146.242:0:0.00,0.00,0.00,0.00:|61.148.154.98:0:0.00,0.00,0.00,0.00:|202.106.42.102:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)

        changes = Path.diff(p1, p2, set([Path.DIFF_FIX_STARS, Path.DIFF_EXTEND,
                Path.DIFF_IGNORE_BALANCERS]))
        self.assertEqual(len(changes), 1)
        self.assertTrue(Path.detects_change(p1, p2, 18))
    # }}}

    def test_D(self): # {{{
        # pylint: disable=C0301

        p1str = '149.43.80.20 202.144.46.40 1283507137 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|72.43.89.1:0:0.00,0.00,0.00,0.00:|24.24.21.37:0:0.00,0.00,0.00,0.00:|24.24.21.33:0:0.00,0.00,0.00,0.00:|24.24.21.154:0:0.00,0.00,0.00,0.00:|24.24.21.221:0:0.00,0.00,0.00,0.00:|66.109.6.72:0:0.00,0.00,0.00,0.00:|66.109.6.153:0:0.00,0.00,0.00,0.00:|213.248.76.97:0:0.00,0.00,0.00,0.00:|80.91.246.19:34,36,38,40,43,14,18,21,24,28:0.00,0.00,0.00,0.00:;80.91.246.163:3,35,10,19:0.00,0.00,0.00,0.00:;80.91.246.165:0,37,39,31,30,15:0.00,0.00,0.00,0.00:;80.91.246.167:42,5:0.00,0.00,0.00,0.00:;80.91.248.193:23,1,27,29,41:0.00,0.00,0.00,0.00:;80.91.248.197:9,20,22:0.00,0.00,0.00,0.00:;80.91.249.109:32,33,17,7,8,26,11:0.00,0.00,0.00,0.00:;80.91.249.111:16,2,4,6,25,12,13:0.00,0.00,0.00,0.00:|80.91.248.202:0:0.00,0.00,0.00,0.00:|80.91.249.170:1,3,5,7,8,10,11,17,19,23,26,27,29,32,33,35,41,42:0.00,0.00,0.00,0.00:;80.91.249.176:0,14,15,18,21,24,28,30,31,34,36,37,38,39,40,43:0.00,0.00,0.00,0.00:;80.91.251.237:2,4,6,9,12,13,16,20,22,25:0.00,0.00,0.00,0.00:|213.248.71.18:0:0.00,0.00,0.00,0.00:|203.101.95.94:0:0.00,0.00,0.00,0.00:|125.20.4.122:0:0.00,0.00,0.00,0.00:|210.18.8.71:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|202.144.46.40:0:0.00,0.00,0.00,0.00:'

        p2str = '149.43.80.20 202.144.46.40 1283507519 0.0.0.1:0:0.00,0.00,0.00,0.00:|0.0.0.2:0:0.00,0.00,0.00,0.00:|72.43.89.1:0:0.00,0.00,0.00,0.00:|24.24.21.37:0:0.00,0.00,0.00,0.00:|24.24.21.33:0:0.00,0.00,0.00,0.00:|24.24.21.154:0:0.00,0.00,0.00,0.00:|24.24.21.221:0:0.00,0.00,0.00,0.00:|66.109.6.72:0:0.00,0.00,0.00,0.00:|66.109.6.153:0:0.00,0.00,0.00,0.00:|213.248.76.97:0:0.00,0.00,0.00,0.00:|80.91.246.19:34,36,38,40,43,14,18,21,24,28:0.00,0.00,0.00,0.00:;80.91.246.163:3,35,10,19:0.00,0.00,0.00,0.00:;80.91.246.165:0,37,39,31,30,15:0.00,0.00,0.00,0.00:;80.91.246.167:42,5:0.00,0.00,0.00,0.00:;80.91.248.193:23,1,27,29,41:0.00,0.00,0.00,0.00:;80.91.248.197:9,20,22:0.00,0.00,0.00,0.00:;80.91.249.109:32,33,17,7,8,26,11:0.00,0.00,0.00,0.00:;80.91.249.111:16,2,4,6,25,12,13:0.00,0.00,0.00,0.00:|80.91.248.202:32,33,17,7,8,26,11:0.00,0.00,0.00,0.00:;80.91.248.253:0,14,15,18,21,24,28,30,31,34,36,37,38,39,40,43:0.00,0.00,0.00,0.00:;80.91.253.117:2,4,6,9,12,13,16,20,22,25:0.00,0.00,0.00,0.00:;213.248.65.89:19,1,3,5,41,42,29,35,23,27,10:0.00,0.00,0.00,0.00:|80.91.249.170:1,3,5,7,8,10,11,17,19,23,26,27,29,32,33,35,41,42:0.00,0.00,0.00,0.00:;80.91.249.176:0,14,15,18,21,24,28,30,31,34,36,37,38,39,40,43:0.00,0.00,0.00,0.00:;80.91.251.237:2,4,6,9,12,13,16,20,22,25:0.00,0.00,0.00,0.00:|213.248.71.18:0:0.00,0.00,0.00,0.00:|203.101.95.94:0:0.00,0.00,0.00,0.00:|125.20.4.122:0:0.00,0.00,0.00,0.00:|210.18.8.71:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|202.144.46.40:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(p1str)
        p2 = Path.create_from_str(p2str)

        changes = Path.diff(p1, p2)
        self.assertEqual(len(changes), 1)
    # }}}
# }}}

class PathDBTester(unittest.TestCase): # {{{
    def test_1(self): # {{{
        # pylint: disable=C0301
        pstr1 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr2 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr3 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|13.13.13.13:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr4 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|14.14.14.14:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|6.6.6.6:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'
        pstr5 = '1.1.1.1 11.11.11.11 1 2.2.2.2:0:0.00,0.00,0.00,0.00:|3.3.3.3:0:0.00,0.00,0.00,0.00:|4.4.4.4:0:0.00,0.00,0.00,0.00:|5.5.5.5:0:0.00,0.00,0.00,0.00:|255.255.255.255:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:'

        p1 = Path.create_from_str(pstr1)
        p2 = Path.create_from_str(pstr2)
        p3 = Path.create_from_str(pstr3)
        p4 = Path.create_from_str(pstr4)
        p5 = Path.create_from_str(pstr5)

        db = PathDB()

        db.alias(p1)
        self.assertEqual(p1.alias, 0)

        db.alias(p2)
        self.assertEqual(p2.alias, 0)
        self.assertEqual(str(p2), pstr2)

        db.alias(p3)
        self.assertEqual(p3.alias, 1)
        self.assertEqual(str(p1), pstr1)

        db.alias(p5)
        self.assertEqual(p5.alias, 0)
        self.assertEqual(str(p1), pstr1)
        self.assertEqual(str(p5), pstr5)

        db.alias(p4)
        self.assertEqual(p4.alias, 2)
    # }}}

    def test_2(self): # {{{
        # pylint: disable=C0301
        NALIASES = 10
        db = PathDB(NALIASES)
        for i in range(NALIASES*100):
            template = '1.1.1.1 11.11.11.11 1 %s:0:0.00,0.00,0.00,0.00:|11.11.11.11:0:0.00,0.00,0.00,0.00:' % ntoa(i)
            pX = Path.create_from_str(template)
            db.alias(pX)
            self.assertEqual(pX.alias, i)
            self.assertEqual(len(db.dst2entry[pX.dst]), min(NALIASES, i+1))
    # }}}
# }}}



if __name__ == '__main__':
    unittest.main()



#   def simulator_matches(self, ip, ttl, balset=None): # {{{
#       ans = self[ttl]
#
#       if ans is None and ip == STAR:
#           # probed after end of path, nothing detected
#           return True
#       if ans is None and ip != STAR:
#           # path has grown
#           return False
#
#       if ans is not None and ans == (ip, ttl):
#           return True
#       if ans is not None and ip == STAR:
#           # path has shrinked
#           return False
#
#       if balset is not None and (ip, ttl) in balset:
#           # change is explained by load balancing
#           return True
#
#       return False
#   # }}}
#   def matches(self, ip, ttl, balset=None): # {{{
#       # this does not care if the path has shrinked, i.e., if a probe is not
#       # answered at a given hop, we do not consider the case that the path
#       # might have shrinked.
#
#       ans = self[ttl]
#
#       if ans is None and ip == STAR:
#           # probed after end of path, nothing detected
#           return True
#       if ans is None and ip != STAR:
#           # path has grown
#           return False
#
#       if ans is not None and ip == STAR:
#           # no information in answer
#           return True
#       if ans is not None and ans == (ip, ttl):
#           # exact match
#           return True
#       if ans is not None and ans == (STAR, ttl) and ip not in self.hops:
#           # STAR in place of ip
#           return True
#       if balset is not None and (ip, ttl) in balset:
#           # change is explained by load balancing
#           return True
#
#       return False
#   # }}}

#   def _compute_changes(self): # {{{
#       olen = len(self.oips)
#       nlen = len(self.nips)
#       # we do not take into consideration the number of hops inserted:
#       inserts = [] if olen == nlen else [self.ottl + min(olen, nlen)]
#       changes = [self.ottl+i for i in range(min(olen, nlen)) if
#               self.oips[i] != STAR or self.nips[i] != STAR]
#       if changes:
#           changes = [self.ottl + i for i in range(min(olen, nlen))]
#       if self.join is None \
#               and not inserts \
#               and not changes \
#               and (
#                       (self.oips and self.oips[-1] == self.dst) or
#                       (self.nips and self.nips[-1] == self.dst)):
#           # a change in the end of the path, without inserts or changes.
#           assert False
#           changes.append(self.ottl + olen - 1)
#       count = len(changes) + (1 if inserts else 0)
#       return changes, inserts, count
#   # }}}
#   def __cmp__(self, other): # {{{
#       # pylint: disable=R0912
#       if self.dst < other.dst: return -1
#       elif self.dst > other.dst: return +1
#       elif self.ottl < other.ottl: return -1
#       elif self.ottl > other.ottl: return +1
#       elif self.nttl < other.nttl: return -1
#       elif self.nttl > other.nttl: return +1
#       elif self.branch < other.branch: return -1
#       elif self.branch > other.branch: return +1
#       elif self.oips < other.oips: return -1
#       elif self.oips > other.oips: return +1
#       elif self.nips < other.nips: return -1
#       elif self.nips > other.nips: return +1
#       else: return 0
#   # }}}
#   def __str__(self): # {{{
#       ostr = ','.join([ntoa(i) for i in self.oips])
#       nstr = ','.join([ntoa(i) for i in self.nips])
#       text = '%d:%s %d:%s' % (self.ottl, ostr, self.nttl, nstr)
#       return ntoa(self.dst) + ' ' + text
#   # }}}
#   def __hash__(self): # {{{
#       data = (self.dst, self.ottl, self.nttl, self.oips, self.nips)
#       return data.__hash__()
#   # }}}
#   def overlaps(self, change): # {{{
#       myips = set([self.branch] + list(self.oips))
#       otherips = set([change.branch] + list(change.oips))
#       return bool(myips.intersection(otherips))
#   # }}}
#   def copy(self): # {{{
#       return PathChange(self.dst, self.ottl, self.nttl, self.oips, self.nips,
#               self.branch[0], self.branch[1], self.join)
#   # }}}
#   def caused_by_balancer(self, baldb): # {{{
#       try:
#           container = baldb[self.dst]
#       except KeyError:
#           return False
#       for ip in self.oips + self.nips:
#           if ip != STAR and ip not in container:
#               return False
#       return True
#   # }}}
#   def caused_by_balset(self, balset): # {{{
#       if balset is None: return False
#       for ip in self.oips + self.nips:
#           if ip != STAR and ip not in balset:
#               return False
#       return True
#   # }}}
#   def is_at_path_end(self): # {{{
#       return len(self.nips + self.oips) == 1 and \
#               (self.join is None or self.dst == self.join)
#   # }}}
