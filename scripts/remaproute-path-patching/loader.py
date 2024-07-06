#!/usr/bin/env python

import gzip
import heapq
import unittest
from collections import defaultdict


# The =Loader class processes a list of files in parallel.  It keeps track of
# the 'current' time, and only keeps in memory data from files that are a
# =timespan around the "current" time (the =timespan variable controls how
# much data to keep in memory).  The user must provide a list of files to open
# (=filekeys), each file must come in a tuple together with the key associated
# with entries in that file.  The user must also provide a =line2obj function
# to process lines from input files into objects.  Objects read from files
# must have a =tstamp field (so we know when it happened).

class Loader(object):# {{{
    def __init__(self, timespan, filekeys, line2obj):# {{{
        self.tspan = float(timespan)
        self.line2obj = line2obj
        self.ctime = 0
        self.key2fd = dict()
        self.key2objs = defaultdict(list)
        self.key2next = dict()
        self.key2active = dict()
        self.key2previous = dict()
        self.key2current = dict()
        self.key2idx = dict()
        for fn, key in filekeys:
            self.key2fd[key] = gzip.open(fn, 'r')
            obj = self.line2obj(self.key2fd[key].readline())
            self.ctime = max(self.ctime, obj.tstamp)
            self.key2next[key] = obj
            self.key2idx[key] = 0
            self._fill(key)
        self.evheap = list()
        for key in self.key2idx:
            nextobj = self.get_next(key)
            if nextobj is None: continue
            heapq.heappush(self.evheap, (nextobj.tstamp, key, nextobj))
        starttime = self.ctime # saving thispecause pop_event changes it
        while self.evheap[0][0] < starttime:
            # making sure everyone has at least one measurement
            self.pop_event()
        assert len(self.key2fd) == len(self.key2next)
    # }}}

    def _fill(self, key):# {{{
        while self.key2next[key] is not None and \
                self.key2next[key].tstamp <= self.ctime + self.tspan:
            self.key2objs[key].append(self.key2next[key])
            string = self.key2fd[key].readline()
            if not string: self.key2next[key] = None
            else: self.key2next[key] = self.line2obj(string)
        if key in self.key2current and \
                self.key2current[key].tstamp < self.ctime:
            self.key2active[key] = self.key2current[key]
        while self.key2idx[key] < len(self.key2objs[key]) and \
                self.key2objs[key][self.key2idx[key]].tstamp <= self.ctime:
            self.key2previous[key] = self.key2current.get(key, None)
            self.key2current[key] = self.key2objs[key][self.key2idx[key]]
            self.key2idx[key] += 1
        if self.key2current[key].tstamp < self.ctime:
            self.key2active[key] = self.key2current[key]
        while self.key2objs[key] and \
                self.key2objs[key][0].tstamp <= self.ctime - self.tspan:
            del self.key2objs[key][0]
            self.key2idx[key] -= 1
    # }}}

    def set_time(self, tstamp):#{{{
        assert tstamp >= self.ctime
        self.ctime = tstamp
    #}}}

    def get_current(self, key):# {{{
        # current path points to the object with largest tstamp (latest) that
        # is less or equal than self.ctime
        self._fill(key)
        return self.key2current[key]
    # }}}

    def get_previous(self, key):# {{{
        # this is the path observed before =current
        self._fill(key)
        return self.key2previous.get(key, None)
    # }}}

    def get_active(self, key):# {{{
        # this is just like get_current, except it points to the object with
        # largest tstamp that is less than (but not equal) self.ctime
        self._fill(key)
        return self.key2active.get(key, None)
    # }}}

    def get_next(self, key):# {{{
        self._fill(key)
        if not self.key2objs[key] and self.key2next[key] is None:
            return None
        elif self.key2idx[key] == len(self.key2objs[key]):
            return self.key2next[key]
        else:
            return self.key2objs[key][self.key2idx[key]]
    # }}}

    def get_objects(self, key):# {{{
        self._fill(key)
        return self.key2objs[key]
    # }}}

    def forward(self, key):# {{{
        self._fill(key)
        for obj in self.key2objs[key][self.key2idx[key]:]:
            yield obj
    # }}}

    def backward(self, key):# {{{
        self._fill(key)
        for obj in reversed(self.key2objs[key][:self.key2idx[key]]):
            yield obj
    # }}}

    def pop_event(self):# {{{
        tstamp, key, obj = heapq.heappop(self.evheap)
        assert tstamp == obj.tstamp
        self.ctime = tstamp
        nextobj = self.get_next(key)
        prevobj = self.key2previous[key]
        if nextobj is not None:
            heapq.heappush(self.evheap, (nextobj.tstamp, key, nextobj))
        return tstamp, key, prevobj, obj
    # }}}

    def iterate(self):#{{{
        while True:
            try: yield self.pop_event()
            except IndexError: raise StopIteration('done')
    # }}}
# }}}


class LoaderTester(unittest.TestCase):#{{{
    @staticmethod
    def mkobj(string):
        # pylint: disable=W0201
        class container(object): pass
        obj = container()
        obj.tstamp = int(string)
        return obj

    def test_1(self):
        # pylint: disable=W0212,R0915
        flist = [('tests/loader/a.gz', 'a'),
                    ('tests/loader/b.gz', 'b')]
        ldr = Loader(2, flist, LoaderTester.mkobj)
        self.assertEqual(ldr.ctime, 1)
        self.assertEqual(len(ldr.key2objs['a']), 3)
        self.assertEqual(len(ldr.key2objs['b']), 1)
        self.assertEqual(ldr.key2idx['a']-1, 0)
        self.assertEqual(ldr.get_current('a').tstamp, 1)
        self.assertEqual(ldr.get_current('b').tstamp, 1)
        self.assertEqual(ldr.get_active('a'), None)
        self.assertEqual(ldr.get_active('b'), None)
        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 2)
        self.assertEqual(tstamp, ldr.ctime)
        self.assertEqual(key, 'a')
        self.assertEqual(len(ldr.key2objs['a']), 4)
        self.assertEqual(len(ldr.key2objs['b']), 1)
        self.assertEqual(ldr.key2idx['a']-1, 1)
        self.assertEqual(ldr.key2current['a'], obj)
        self.assertEqual(ldr.get_active('a').tstamp, 1)
        self.assertEqual(ldr.get_current('a'), obj)
        self.assertEqual(ldr.get_next('a').tstamp, 3)
        self.assertEqual(ldr.key2current['b'].tstamp, 1)
        self.assertEqual(ldr.get_active('b').tstamp, 1)
        self.assertEqual(ldr.get_current('b').tstamp, 1)
        self.assertEqual(ldr.get_next('b').tstamp, 7)
        tstamp, key, _pobj, obj = ldr.pop_event()
        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 4)
        self.assertEqual(len(ldr.key2objs['a']), 4)
        self.assertEqual(len(ldr.key2objs['b']), 1)
        ldr._fill('b')
        self.assertEqual(len(ldr.key2objs['b']), 0)
        self.assertEqual(ldr.get_next('b').tstamp, 7)

        tstamp, key, _pobj, obj = ldr.pop_event()

        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 6)
        self.assertEqual(ldr.key2current['b'].tstamp, 1)
        ldr._fill('b')
        self.assertEqual(ldr.key2current['b'].tstamp, 1)
        self.assertEqual(ldr.key2idx['b'], 0)
        self.assertEqual(ldr.get_next('b').tstamp, 7)
        self.assertEqual(ldr.key2current['a'].tstamp, 6)

        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 7)
        self.assertEqual(key, 'a')
        self.assertEqual(ldr.key2current['a'].tstamp, 7)
        self.assertEqual(ldr.key2idx['b'], 0)
        self.assertEqual(ldr.key2current['b'].tstamp, 1)
        ldr._fill('b')
        self.assertEqual(ldr.key2current['b'].tstamp, 7)
        self.assertEqual(ldr.get_next('b'), None)
        self.assertEqual(ldr.get_current('a').tstamp, 7)
        self.assertEqual(ldr.get_current('b').tstamp, 7)
        self.assertEqual(ldr.get_active('a').tstamp, 6)
        self.assertEqual(ldr.get_active('b').tstamp, 1)

        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 7)
        self.assertEqual(len(ldr.key2objs['a']), 4)
        self.assertEqual(len(ldr.key2objs['b']), 1)
        self.assertEqual(ldr.get_current('a').tstamp, 7)
        self.assertEqual(ldr.get_previous('a').tstamp, 6)
        self.assertEqual(ldr.get_current('b').tstamp, 7)
        self.assertEqual(ldr.get_previous('b').tstamp, 1)
        self.assertEqual(ldr.get_active('a').tstamp, 6)
        self.assertEqual(ldr.get_active('b').tstamp, 1)

        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.get_current('a').tstamp, 8)
        self.assertEqual(ldr.get_current('b').tstamp, 7)
        self.assertEqual(ldr.get_active('a').tstamp, 7)
        self.assertEqual(ldr.get_active('b').tstamp, 7)
        tstamp, key, _pobj, obj = ldr.pop_event()
        self.assertEqual(ldr.ctime, 9)
        self.assertEqual(ldr.get_next('a'), None)
        self.assertEqual(len(ldr.key2objs['a']), 2)
        ldr._fill('b')
        self.assertEqual(len(ldr.key2objs['b']), 0)

        self.assertRaises(IndexError, ldr.pop_event)
#}}}


if __name__ == '__main__':
    unittest.main()
