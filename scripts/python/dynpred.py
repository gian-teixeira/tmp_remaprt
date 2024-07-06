import gzip
import logging

from bisect import bisect


__all__ = ["DynamicsPredictor", "training_set_iterator"]

_defthresholds = [
    [0, 180, 420, 24*60, 75*60, int(6.5*3600)], # route age
    [0, 6.9e-05, 0.02147, 0.083079, 0.186875, 0.347778, 0.598808, 0.953102],
    [0, 1, 2, 3, 5, 8, 16, 34, 55, 76], # path changes
    [0, 1, 2, 4, 9, 16]] # route appearances
_deftset = '/home/cunha/topo/sigmetrics11/knn/tsets/' + \
        'dmap.t1.m1000.d2419200.k604800.c200000.n10.tunc.gz'


def training_set_iterator(fn): # {{{
    '''iterates over a training set pointed to by fd. can be used as a
    parameter to DynamicsPredictor.train(). note that fd should be built
    specifically for the nearest-neighbor predictor, with target metric on
    column 0 and for features in columns 1 to 4.'''

    fd = gzip.open(fn, 'r')
    targetidx = 0
    featidx = [1, 2, 3, 4]
    weightidx = 5
    for line in fd:
        if line.startswith('#'): continue
        fields = line.split()
        target = float(fields[targetidx])
        features = [float(fields[f]) for f in featidx]
        weight = 1
        if len(fields) > weightidx:
            weight = float(fields[weightidx])
        yield target, features, weight
# }}}


class DynamicsPredictor(object): # {{{
    '''A predictor for route dynamics.

    This predictor classifies routes in a multi-feature space. Routes are
    classified according to feature thresholds specified at the time of
    initialization. Prediction for routes in each class is made as the average
    value of routes in that class.'''

    def __init__(self, tset=_deftset, thresholds=None, median=False):
        '''thresholds is a list of lists. first dimension specifies a route
        feature, and the second dimension specifies that feature's thresholds.
        the predictor makes it's own copy of thresholds.'''

        if thresholds is None: thresholds = _defthresholds
        self.dmap = DimensionMapper(thresholds)
        self.mvec = MultiVector([len(ts) for ts in thresholds])
        self.median = median
        self.testmiss = 0
        self.train(training_set_iterator(tset))

    def train(self, training_set):
        '''training_set should iterate over training points. Each training
        point should be a tuple with two elements: the target metric (e.g.,
        route remaining lifetime), and the list of route features. The list of
        route features must be in the same order as the order passed in the the
        thresholds parameter to DynamicsPredictor.__init__'''

        cnt = 0
        for target, features, weight in training_set:
            cnt += 1
            pos = self.dmap.map(features)
            meancalc = self.mvec[pos]
            if meancalc is None:
                meancalc = MedianCalculator() if self.median \
                        else MeanCalculator()
                self.mvec[pos] = meancalc
            meancalc.add(target, weight)
        if self.median:
            for mc in self.mvec.data:
                if mc is None: continue
                mc.close()
        logging.info('trained predictor with %d points', cnt)

    def predict(self, features):
        '''features must be in the same order as the order used in the the
        thresholds parameter to DynamicsPredictor.__init__'''

        pos = self.dmap.map(features)
        meancalc = self.mvec[pos]
        if meancalc is None:
            logging.info('prediction asked for untrained route features:')
            logging.info(' '.join([str(f) for f in features]))
            self.testmiss += 1
            return None
        return meancalc.value

    def dump_bins(self, fd):
        '''dumps information about bins in fd. for each bin, a line is printed
        with "accum count pos1 pos2 ... posN"'''

        def dump_dimension(pos):
            if len(pos) == self.mvec.ndims:
                avg = self.mvec[pos]
                if avg is None: avg = MeanCalculator()
                fd.write('%f %d %s\n' % (avg.accum, avg.count,
                        ' '.join(str(x) for x in pos)))
            else:
                for i in range(0, self.mvec.dsizes[len(pos)]):
                    pos.append(i)
                    dump_dimension(pos)
                    pos.pop()

        dump_dimension([])

# }}}


class MultiVector(object): # {{{
    def __init__(self, dimension_sizes):
        self.ndims = len(dimension_sizes)
        self.dsizes = list(dimension_sizes)
        self.dskip = self.ndims * [1]
        for d in range(self.ndims - 1, 0, -1):
            self.dskip[d-1] = self.dskip[d] * self.dsizes[d]
        length = self.dskip[0] * self.dsizes[0]
        self.data = length * [None]

    def __getitem__(self, pos):
        dskip = self.dskip
        i = 0
        for d, skip in enumerate(dskip):
            i += pos[d] * skip
        return self.data[i]

    def __setitem__(self, pos, value):
        dskip = self.dskip
        i = 0
        for d, skip in enumerate(dskip):
            i += pos[d] * skip
        self.data[i] = value
# }}}


class DimensionMapper(object): # {{{
    def __init__(self, thresholds):
        self.ndims = len(thresholds)
        self.dts = [sorted([float(t) for t in ts]) for ts in thresholds]

    def map(self, dvalues):
        dts = self.dts
        return [bisect(dts[d], v)-1 for d, v in enumerate(dvalues)]
# }}}


class MeanCalculator(object): # {{{
    def __init__(self, accum=0.0, count=0):
        self.accum = 0.0
        self.count = 0
        self.value = 0.0

    def add(self, value, weight=1.0):
        self.accum += float(value)*weight
        self.count += weight
        if self.count == 0: return
        self.value = self.accum / self.count

    def __str__(self):
        return str(self.value())
# }}}


class MedianCalculator(object): # {{{
    def __init__(self):
        self.data = list()
        self.accum = -10e10000
        self.count = 0
        self.value = None

    def add(self, value):
        self.data.append(float(value))
        self.count += 1

    def close(self):
        self.data.sort()
        if len(self.data) == 0:
            self.value = 0.0
            self.data = None
            return
        elif len(self.data) == 1:
            self.value = self.data[0]
            self.data = None
            return
        elif len(self.data) == 2:
            self.value = (self.data[0] + self.data[1])/2.0
            self.data = None
            return
        f = len(self.data)/2.0 - 0.5
        i = int(f)
        a = f - i
        self.value = (1-a)*self.data[i] + a*self.data[i+1]
        self.data = None

    def __str__(self):
        return str(self.value())
# }}}
