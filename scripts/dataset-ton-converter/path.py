from struct import unpack, pack
from socket import inet_ntoa
from collections import defaultdict

STAR = unpack('!I', '\xff\xff\xff\xff')[0]
def ntoa(integer): return inet_ntoa(pack('!I', integer))


class Path(object): # {{{
    FLAG_LOOP = 'loop'
    FLAG_NO_REACH = 'no_reach_dst'

    def __init__(self, dst, time, hops): # {{{
        self.baldb = None
        self.snapshot = None
        self.dst = dst
        self.time = time
        self.hops = list(hops)
        self.flags = set()
        self.check_remove_loop()
        self.check_reachability()
    # }}}

    def check_remove_loop(self): # {{{
        self.flags -= set([Path.FLAG_LOOP])
        hops_set = set()
        for i, ip in enumerate(self.hops):
            if ip in hops_set:
                self.hops = self.hops[0:i]
                self.flags.add(Path.FLAG_LOOP)
                break
            hops_set.add(ip)
        while self.hops and self.hops[-1] == STAR:
            del self.hops[-1]
    # }}}

    def check_reachability(self): # {{{
        self.flags -= set([Path.FLAG_NO_REACH])
        try:
            i = self.hops.index(self.dst)
            self.hops = self.hops[:i+1]
        except ValueError:
            self.flags.add(Path.FLAG_NO_REACH)
            return False
    # }}}

    def copy(self): return Path(self.dst, self.time, self.hops)
    def __len__(self): return len(self.hops)
    def __ne__(self, other): return bool(self.diff(other, True, True, None))
    def __eq__(self, other): return not self != other

    def __str__(self): # {{{
        return '%s %d %d %s' % (ntoa(self.dst), self.time, len(self),
                                ','.join(ntoa(ip) for ip in self.hops))
    # }}}

    def __getitem__(self, ttl): # {{{
        try: return (self.hops[ttl], ttl)
        except IndexError:
            if Path.FLAG_NO_REACH not in self.flags:
                return (self.dst, len(self)-1)
            return None
    # }}}

    def simulator_matches(self, ip, ttl, balset=None): # {{{
        ans = self[ttl]

        if ans is None and ip == STAR:
            # probed after end of path, nothing detected
            return True
        if ans is None and ip != STAR:
            # path has grown
            return False

        if ans is not None and ans == (ip, ttl):
            return True
        if ans is not None and ip == STAR:
            # path has shrinked
            return False

        if balset is not None and (ip, ttl) in balset:
            # change is explained by load balancing
            return True

        return False
    # }}}

    def matches(self, ip, ttl, balset=None): # {{{
        # this does not care if the path has shrinked, i.e., if a probe is not
        # answered at a given hop, we do not consider the case that the path
        # might have shrinked.

        ans = self[ttl]

        if ans is None and ip == STAR:
            # probed after end of path, nothing detected
            return True
        if ans is None and ip != STAR:
            # path has grown
            return False

        if ans is not None and ip == STAR:
            # no information in answer
            return True
        if ans is not None and ans == (ip, ttl):
            # exact match
            return True
        if ans is not None and ans == (STAR, ttl) and ip not in self.hops:
            # STAR in place of ip
            return True
        if balset is not None and (ip, ttl) in balset:
            # change is explained by load balancing
            return True

        return False
    # }}}

    def diff(self, newpath, fix_stars, fill_missing, balset): # {{{
        # returned list of events it sorted by ttl.
        assert self.dst == newpath.dst
        # assert self.time <= newpath.time
        events = list()
        oi = 0
        ni = 0
        olen = len(self)
        nlen = len(newpath)
        while True:
            if oi == olen and ni == nlen:
                break
            elif oi < olen and ni < nlen:
                # we do not check if hop is balanced because the input trace
                # already has a fixed IP for load-balanced interfaces. if hops
                # are different after a load balancer, it's likely that
                # something changed. we check if the change is due to load
                # balancers outside.
                if self.hops[oi] == newpath.hops[ni]:
                    oi += 1
                    ni += 1
                    continue
                ojoin, njoin = self.diff_join(newpath, oi, ni, olen, nlen)
                oi_fixed, ni_fixed, ojoin_fixed, njoin_fixed = \
                        oi, ni, ojoin, njoin
                if fix_stars:
                    oi_fixed, ni_fixed, ojoin_fixed, njoin_fixed = \
                            self.diff_fix_stars(newpath, oi, ni, ojoin, njoin)
                ev = self.diff_gen_event(newpath, oi_fixed, ni_fixed,
                                         ojoin_fixed, njoin_fixed)
                if ev and not ev.caused_by_balset(balset):
                    events.append(ev)
                oi, ni = ojoin, njoin
            elif fill_missing and oi == ni and not events:
                olen, nlen = \
                        self.diff_fill_missing_hops(newpath, oi, olen, nlen)
            else:
                assert Path.FLAG_NO_REACH in self.flags or \
                        Path.FLAG_NO_REACH in newpath.flags
                # here: ojoin, njoin = olen, nlen
                if fix_stars:
                    self.diff_fix_stars(newpath, oi, ni, olen, nlen)
                ev = self.diff_gen_event(newpath, oi, ni, olen, nlen)
                if ev and not ev.caused_by_balset(balset): events.append(ev)
                break
        return events
    # }}}

    def diff_join(self, newpath, oi, ni, olen, nlen): # {{{
        for nni in range(ni, nlen):
            nip = newpath.hops[nni]
            if nip == STAR:
                continue
            for noi in range(oi, olen):
                oip = self.hops[noi]
                if oip == nip:
                    return noi, nni
        assert Path.FLAG_NO_REACH in self.flags or \
                Path.FLAG_NO_REACH in newpath.flags
        return olen, nlen
    # }}}

    def diff_fix_stars(self, newpath, oi, ni, ojoin, njoin): # {{{
        # pylint: disable=R0912
        def check_fix(star, ip, knownips, h, jointtl):
            if star != STAR: return False
            if ip == STAR: return False
            if ip in knownips: return False
            if ip == self.dst and h+1 != jointtl: return False
            return True

        fixes = 0
        for i in range(min(ojoin - oi, njoin - ni)):
            oldip = self.hops[oi+i]
            newip = newpath.hops[ni+i]
            if check_fix(oldip, newip, self.hops, oi+i, ojoin):
                self.hops[oi+i] = newip
                fixes += 1
            elif check_fix(newip, oldip, newpath.hops, ni+i, njoin):
                newpath.hops[ni+i] = oldip
                fixes += 1
            else:
                break
        oi_fixed = oi + fixes
        ni_fixed = ni + fixes

        fixes = 0
        for i in range(min(ojoin - oi_fixed, njoin - ni_fixed)):
            oldip = self.hops[ojoin - 1 - i]
            newip = newpath.hops[njoin - 1 - i]
            if check_fix(oldip, newip, self.hops, ojoin-1-i, ojoin):
                self.hops[ojoin-1-i] = newip
                fixes += 1
            elif check_fix(newip, oldip, newpath.hops, njoin-1-i, njoin):
                newpath.hops[njoin-1-i] = oldip
                fixes += 1
            else:
                break
        ojoin_fixed = ojoin - fixes
        njoin_fixed = njoin - fixes

        assert oi_fixed <= ojoin_fixed and ni_fixed <= njoin_fixed
        self.check_reachability()
        newpath.check_reachability()
        return oi_fixed, ni_fixed, ojoin_fixed, njoin_fixed
    # }}}

    def diff_gen_event(self, newpath, oi, ni, ojoin, njoin): # {{{
        branch = 'src' if oi == 0 else self.hops[oi-1]
        joinip = None if ojoin >= len(self.hops) else self.hops[ojoin]
        ev = PathChange(self.dst, oi, ni, self.hops[oi:ojoin],
                        newpath.hops[ni:njoin], branch, joinip)
        return ev
    # }}}

    def diff_fill_missing_hops(self, newpath, i, olen, nlen): # {{{
        for ttl in range(i, max(olen, nlen)):
            if len(self) == ttl:
                self.hops.append(STAR)
                assert len(newpath) >= ttl
            elif len(newpath) == ttl:
                newpath.hops.append(STAR)
                assert len(self) >= ttl
            else:
                raise RuntimeError
        assert len(self.hops) == len(newpath.hops)
        return len(self.hops), len(newpath.hops)
    # }}}

    def dump(self, outfd): # {{{
        outfd.write(pack('!III', self.dst, self.time, len(self)))
        for ip in self.hops:
            outfd.write(pack('!I', ip))
    # }}}

    def asnlist(self, ip2as): # {{{
        assert ip2as is not None
        asnlist = list()
        asn = 0
        for ip in self.hops:
            if ip != STAR:
                asn = ip2as[ip]
            asnlist.append(asn)
        return asnlist
    # }}}

    def asn2ips(self, ip2as): # {{{
        assert ip2as is not None
        asn2ips = defaultdict(list)
        asn = 0
        for ip in self.hops:
            if ip != STAR:
                asn = ip2as[ip]
            asn2ips[asn].append(ip)
        return asn2ips
    # }}}

    @staticmethod
    def read(infd): # {{{
        dst, time, hopcnt = unpack('!III', infd.read(4*3))
        hops = list(unpack('!'+'I'*hopcnt, infd.read(4*hopcnt)))
        return Path(dst, time, hops)
    # }}}
# }}}


class PathChange(object): # {{{
    def __init__(self, dst, ottl, nttl, oips, nips, branch, join): # {{{
        self.dst = dst
        self.ottl = ottl
        self.nttl = nttl
        self.oips = tuple(oips)
        self.nips = tuple(nips)
        self.branch = branch
        self.join = join
        self.flags = set()
        self.changes, self.inserts, self.count = self._compute_changes()
    # }}}

    def _compute_changes(self): # {{{
        olen = len(self.oips)
        nlen = len(self.nips)
        # we do not take into consideration the number of hops inserted:
        inserts = [] if olen == nlen else [self.ottl + min(olen, nlen)]
        changes = [self.ottl+i for i in range(min(olen, nlen)) if
                   self.oips[i] != STAR or self.nips[i] != STAR]
        if changes:
            changes = [self.ottl + i for i in range(min(olen, nlen))]
        if self.join is None \
                and not inserts \
                and not changes \
                and (
                        (self.oips and self.oips[-1] == self.dst) or
                        (self.nips and self.nips[-1] == self.dst)):
            # a change in the end of the path, without inserts or changes.
            assert False
            changes.append(self.ottl + olen - 1)
        count = len(changes) + (1 if inserts else 0)
        return changes, inserts, count
    # }}}

    def __len__(self): return self.count

    def __cmp__(self, other): # {{{
        # pylint: disable=R0912
        if self.dst < other.dst: return -1
        elif self.dst > other.dst: return +1
        elif self.ottl < other.ottl: return -1
        elif self.ottl > other.ottl: return +1
        elif self.nttl < other.nttl: return -1
        elif self.nttl > other.nttl: return +1
        elif self.branch < other.branch: return -1
        elif self.branch > other.branch: return +1
        elif self.oips < other.oips: return -1
        elif self.oips > other.oips: return +1
        elif self.nips < other.nips: return -1
        elif self.nips > other.nips: return +1
        else: return 0
    # }}}

    def __str__(self): # {{{
        ostr = ','.join([ntoa(i) for i in self.oips])
        nstr = ','.join([ntoa(i) for i in self.nips])
        text = '%d:%s %d:%s' % (self.ottl, ostr, self.nttl, nstr)
        return ntoa(self.dst) + ' ' + text
    # }}}

    def __hash__(self): # {{{
        data = (self.dst, self.ottl, self.nttl, self.oips, self.nips)
        return data.__hash__()
    # }}}

    def overlaps(self, change):
        myips = set([self.branch] + list(self.oips))
        otherips = set([change.branch] + list(change.oips))
        return bool(myips.intersection(otherips))


    def copy(self): # {{{
        return PathChange(self.dst, self.ottl, self.nttl, self.oips, self.nips,
                          self.branch[0], self.branch[1], self.join)
    # }}}

    def caused_by_balancer(self, baldb): # {{{
        try:
            container = baldb[self.dst]
        except KeyError:
            return False
        for ip in self.oips + self.nips:
            if ip != STAR and ip not in container:
                return False
        return True
    # }}}

    def caused_by_balset(self, balset): # {{{
        if balset is None: return False
        for ip in self.oips + self.nips:
            if ip != STAR and ip not in balset:
                return False
        return True
    # }}}

    def is_at_path_end(self): # {{{
        return len(self.nips + self.oips) == 1 and \
                (self.join is None or self.dst == self.join)
    # }}}
# }}}


# NOTE: Paths with asterisks may match multiple aliases in an AliasDatabase.
# When this happens, we return the first match.
class AliasDatabase(object): # {{{
    def __init__(self):
        self.db = dict()

    def __getitem__(self, path):
        return self.db[path.dst].index(path)

    def add(self, path):
        new = path.copy()
        new.time = 0
        if new.dst not in self.db:
            self.db[new.dst] = [new]
            return 0
        try:
            index = self.db[new.dst].index(new)
            old = self.db[new.dst][index]
            for i, ip in enumerate(old.hops):
                assert ip == new.hops[i]
            return index
        except ValueError:
            self.db[new.dst].append(new)
            return len(self.db[new.dst]) - 1
# }}}
