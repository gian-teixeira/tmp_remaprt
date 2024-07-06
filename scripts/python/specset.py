import os
import glob
from collections import defaultdict


class spec(object): # {{{
    ANY = 'ANY'
    NONE = 'NONE'

    def __init__(self):
        self.fields = list()
        self.field2prefix = dict()
        self.v = dict()

    def __iter__(self): return iter(self.v.items())
    def __hash__(self): return hash(tuple(self.v.items()))

    def __contains__(self, other):
        for f in self.field2prefix:
            v1 = self.v[f]
            v2 = other.v[f]
            if v1 != spec.ANY and v2 != spec.NONE and v1 != v2:
                return False
        return True

    def __str__(self):
        specs = list()
        for f in self.fields:
            specs.append('%s%s' % (self.field2prefix[f], self.v[f]))
        return '-'.join(specs)

    def name_different_fields(self, key):
        specs = list()
        for f in self.fields:
            if key.v[f] == spec.ANY and self.v[f] != spec.NONE:
                specs.append('%s%s' % (self.field2prefix[f], self.v[f]))
        return '-'.join(specs)

    def name_with_fields(self, fields):
        if not isinstance(fields, list): fields = list([fields])
        specs = list()
        for f in self.fields:
            if f not in fields: continue
            specs.append('%s%s' % (self.field2prefix[f], self.v[f]))
        return '-'.join(specs)

    def name_without_fields(self, fields):
        if not isinstance(fields, list): fields = list([fields])
        specs = list()
        for f in self.fields:
            if f in fields: continue
            specs.append('%s%s' % (self.field2prefix[f], self.v[f]))
        return '-'.join(specs)

# }}}


class container(object): pass
# pylint: disable-msg=W0201


def create(specs):
    ss = container()
    ss.specs = set(specs)
    ss.fld2values = defaultdict(set)
    for s in specs:
        for field, value in s:
            ss.fld2values[field].add(value)
    return ss

def filter(ss, key):
    return set([s for s in ss.specs if s in key])

def fieldvalues(ss, field):
    return ss.fld2values[field]

def readall(datadir, spec_create_func):
    specs = set()
    for exp in glob.iglob(os.path.join(datadir, '*')):
        if not os.path.exists(os.path.join(exp, 'ok')): continue
        s = spec_create_func(exp)
        if s is None: continue
        specs.add(s)
    return create(specs)


