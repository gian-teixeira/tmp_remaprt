from struct import pack, unpack
from collections import defaultdict

from path import Path
from defines import STAR

class Snapshot(object): # {{{
    def __init__(self, dst2path, baldb=None): # {{{
        self.dst2path = dst2path
        self.baldb = baldb
        self.begin = min([p.time for p in dst2path.values()])
        self.remove_empty_paths()
    # }}}
    def __eq__(self, snapshot): # {{{
        for dst, path in self.dst2path.items():
            if dst not in snapshot.dst2path:
                continue
            if path != snapshot[dst]:
                return False
        return True
    # }}}

    def copy(self): # {{{
        dst2path = dict()
        for dst, path in self.dst2path.items():
            dst2path[dst] = path.copy()
        return Snapshot(dst2path, self.baldb)
    # }}}

    def include_missing_paths(self, oldsnap): # {{{
        for dst, path in oldsnap.dst2path.items():
            if dst not in self.dst2path or len(self.dst2path[dst]) == 0:
                self.dst2path[dst] = path.copy()
    # }}}

    def remove_empty_paths(self): # {{{
        for dst, path in self.dst2path.items():
            if len(path) == 0:
                del self.dst2path[dst]
    # }}}

    def ip2dsts(self):
        ip2dsts = defaultdict(set)
        for dst, path in self.dst2path.items():
            for ttl, ip in enumerate(path.hops):
                if ip == STAR: continue
                ip2dsts[ip].add(dst)
        return ip2dsts

    def diff(self, newsnap, fixstars=True, fillmissing=True, baldb=None):#{{{
        assert False
        dst2events = dict()
        for dst, path in self.dst2path.items():
            newpath = newsnap[dst]
            balset = None
            if baldb is not None: balset = baldb[dst]
            elif self.baldb is not None: balset = self.baldb[dst]
            dstevents = path.diff(newpath, fixstars, fillmissing, balset)
            dst2events[dst] = dstevents
        return dst2events
    # }}}

    def dump(self, outfd): # {{{
        outfd.write(pack('!I', len(self.dst2path)))
        for dst in sorted(self.dst2path.keys()):
            self.dst2path[dst].dump(outfd)
    # }}}

    def get_path(self, dst): return self.dst2path[dst]
    def get_ip_ttl(self, dst, ttl): return self.dst2path[dst][ttl]

    @staticmethod
    def read(infd): # {{{
        dst2path = dict()
        pathcnt = infd.read(4)
        if pathcnt == '': raise EOFError
        pathcnt = unpack('!I', pathcnt)[0]
        for _ in range(pathcnt):
            path = Path.read(infd)
            dst2path[path.dst] = path
        return Snapshot(dst2path)
    # }}}
# }}}
