#!/usr/bin/env python

import sys
import gzip


class stats(object):# {{{
    def __init__(self):
        self.lcz = -1
        self.joincnt = 0
        self.rm1cnt = 0
        self.branchcnt = 0
        self.joinchanges = 0
        self.rm1changes = 0
        self.branchchanges = 0
        self.njoins = list()
        self.nrm1s = list()
        self.nbranches = list()
        self.fracjoin = list()
        self.fracrm1 = list()
        self.fracbranch = list()

    def __lshift__(self, lcz):
        if self.lcz != -1:
            self._commit()
        self.lcz = lcz
        self.joincnt = 0
        self.rm1cnt = 0
        self.branchcnt = 0
        self.joinchanges = 0
        self.rm1changes = 0
        self.branchchanges = 0

    def _commit(self):
        self.njoins.append(self.joincnt)
        self.nrm1s.append(self.joincnt + self.rm1cnt)
        self.nbranches.append(self.joincnt + self.rm1cnt + self.branchcnt)
        d = self.joincnt
        if d == 0: self.fracjoin.append(1)
        self.fracjoin.append(self.joinchanges / d)
        d = self.joincnt + self.rm1cnt
        if d == 0: self.fracrm1.append(1)
        self.fracrm1.append((self.joinchanges + self.rm1changes) / d)
        d = self.joincnt + self.rm1cnt + self.branchcnt
        if d == 0: self.fracbranch.append(1)
        self.fracbranch.append((self.joinchanges + self.rm1changes +
                                self.branchchanges) / d)
# }}}

def main():
    fd = gzip.open(sys.argv[1], 'r')
    s = stats()

    for line in fd:
        fields = line()
        lcz = int(fields[1])
        s << lcz

        if float(fields[21]) < 0.9 and not bool(fields[23]): continue # unprobed

        if int(fields[25]) == 1:
            if bool(fields[12]):
                s.joincnt += 1
            elif int(fields[14]) > 0:
                s.rm1cnt += 1
            elif bool(fields[10]):
                s.branchcnt += 1
        else:
            if bool(fields[12]):
                s.joincnt += 1
                s.joinchanges += 1
            elif int(fields[14]) > 0:
                s.rm1cnt += 1
                s.rm1changes += 1
            elif bool(fields[10]):
                s.branchcnt += 1
                s.branchchanges += 1

    fd.close()
