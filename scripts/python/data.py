import sys
import os
import gzip
import cPickle
import bisect
from collections import defaultdict

from saikko.defines import aton, ntoa
import conf as config


STABLE = 1
UNSTAB = 2


class DatasetData(object): # {{{
	def __init__(self, ds): # {{{
		self.ds = ds
		self.mon2data = dict()
		ifile = config.monlist[ds]
		ifile = open(ifile)
		self.monlist = [mon.strip() for mon in ifile.readlines()]
		ifile.close()
	# }}}

	def __iter__(self): # {{{
		return iter(self.monlist)
	# }}}

	def __getitem__(self, monitor): # {{{
		if monitor not in self.mon2data:
			self.mon2data[monitor] = MonitorData(self.ds, monitor)
		return self.mon2data[monitor]
	# }}}

	def get_period2cluster(self, period_type): # {{{
		'''Get a dictionary mapping periods to their cluster ids.

		Parameter period_type specifies the cidmap_*.txt file read and
		returned. Check in config.outdir[self.dsname] the cidmap files
		available.

		For use in this function, cidmap files should contain four fields per
		line: monitor, destination, starting time, and cluster id.
		'''

		period2cluster = dict()
		infn = 'cidmap_%s.txt' % period_type
		infn = os.path.join(config.outdir[self.ds], infn)
		infd = open(infn, 'r')
		for line in infd:
			mon, dst, start, cid = line.split()
			dst = aton(dst)
			start = int(start)
			cid = int(cid)
			assert start >= 0
			assert cid >= 0
			assert (mon, dst, start) not in period2cluster
			period2cluster[(mon, dst, start)] = cid
		infd.close()
		return period2cluster
	# }}}

	def iter_paths(self): # {{{
		for monitor in self:
			mondata = self[monitor]
			for path in mondata:
				yield path
		raise StopIteration
	# }}}
# }}}


class MonitorData(object): # {{{
	def __init__(self, dataset, name): # {{{
		self.ds = dataset
		self.name = name
		self.make_outdir()
		self.dst2path = dict()
		self.snaptimes = None
		self.dst2routes = None
		self.dst2changes = None
		self.winsz2route2act = defaultdict(lambda: None)
		self.key2dst2pp = defaultdict(lambda: None)
		self.name2dst2runlog = defaultdict(lambda: None)
		self.name2dst2periods = defaultdict(lambda: None)
		self.dst2time2hops = None
	# }}}

	def reset(self): # {{{
		self.dst2path = dict()
		self.snaptimes = None
		self.dst2routes = None
		self.dst2changes = None
		self.winsz2route2act = defaultdict(lambda: None)
		self.key2dst2pp = defaultdict(lambda: None)
		self.name2dst2runlog = defaultdict(lambda: None)
		self.name2dst2periods = defaultdict(lambda: None)
		self.dst2time2hops = None
	# }}}

	def __iter__(self): # {{{
		dst2changes = self.get_dst2routes()
		for dst in dst2changes:
			yield Path(dst, self)
		raise StopIteration
	# }}}

	def __getitem__(self, dst): # {{{
		return self.dst2path.setdefault(dst, Path(dst, self))
	# }}}

	def get_hops(self, dst, time): # {{{
		if self.dst2time2hops is None:
			self.dst2time2hops = defaultdict(dict)
			fd = gzip.open(os.path.join(config.changedb[self.ds],
					self.name, 'pathdump.gz'))
			for line in fd:
				if line[0] == '#': continue
				fields = line.split()
				mdst = aton(fields[0])
				mtime = int(fields[1])
				hops = [aton(i) for i in fields[3].split(',')]
				assert mtime not in self.dst2time2hops[mdst]
				self.dst2time2hops[mdst][mtime] = hops
		return list(self.dst2time2hops[dst][time])
	# }}}

	def make_outdir(self): # {{{
		outdir = os.path.join(config.outdir[self.ds], self.name)
		if not os.path.isdir(outdir):
			os.makedirs(outdir)
	# }}}

	def get_snapshot_times(self): # {{{
		if self.snaptimes is not None:
			return self.snaptimes
		ifile = 'snap.gz'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ifile = gzip.open(ifile, 'r')
		self.snaptimes = [int(l.split()[0]) for l in ifile if l[0] != '#']
		ifile.close()
		return self.snaptimes
	# }}}

	def get_dst2changes(self): # {{{
		if self.dst2changes is not None:
			return self.dst2changes
		ifile = 'changes.gz'
		ofile = 'dst2changes.pickle'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		if not os.path.exists(ofile) \
				or os.path.getmtime(ofile) <= os.path.getmtime(ifile):
			self.dst2changes = self.make_dst2changes()
			return self.dst2changes
		fd = open(ofile)
		self.dst2changes = cPickle.load(fd)
		fd.close()
		return self.dst2changes
	# }}}

	def make_dst2changes(self): # {{{
		def check_columns(header): # {{{
			columns = header.split()
			assert columns[IDX_TIME+1] == 'newpath.tstamp'
			assert columns[IDX_DST+1] == 'dst'
			assert columns[IDX_BTTL+1] == 'branchttl'
			assert columns[IDX_NASES+1] == 'num-AS-impacted'
			assert columns[IDX_NHOPS+1] == 'num-hops-impacted'
		# }}}
		def parse(line): # {{{
			fields = line.split()
			time = int(fields[IDX_TIME])
			dst = aton(fields[IDX_DST])
			bttl = int(fields[IDX_BTTL])
			nASes = int(fields[IDX_NASES])
			nhops = int(fields[IDX_NHOPS])
			return time, dst, bttl, nASes, nhops
		# }}}

		IDX_TIME = 1
		IDX_DST = 2
		IDX_BTTL = 6
		IDX_NASES = 13
		IDX_NHOPS = 14
		ifile = 'changes.gz'
		ofile = 'dst2changes.pickle'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		ifile = gzip.open(ifile, 'r')
		check_columns(ifile.readline())
		dst2changes = defaultdict(list)
		for line in ifile:
			if line[0] == '#':
				continue
			time, dst, bttl, nASes, nhops = parse(line)
			if dst2changes[dst] and dst2changes[dst][-1].time == time:
				dst2changes[dst][-1].extend(bttl, nASes, nhops)
			else:
				change = Change(dst, time, [bttl], [nASes], [nhops])
				dst2changes[dst].append(change)
		ifile.close()
		ofile = open(ofile, 'w')
		cPickle.dump(dst2changes, ofile)
		ofile.close()
		return dst2changes
	# }}}

	def get_dst2routes(self): # {{{
		def add_mondata_attribute(routes):
			for r in routes: r.mondata = self
		if self.dst2routes is not None:
			return self.dst2routes
		ifile = 'fpath.gz'
		ofile = 'dst2routes.pickle'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		if not os.path.exists(ofile) \
				or os.path.getmtime(ofile) <= os.path.getmtime(ifile):
			self.dst2routes = self.make_dst2routes()
			[add_mondata_attribute(r) for r in self.dst2routes.values()]
			return self.dst2routes
		fd = open(ofile)
		self.dst2routes = cPickle.load(fd)
		fd.close()
		[add_mondata_attribute(r) for r in self.dst2routes.values()]
		return self.dst2routes
	# }}}

	def make_dst2routes(self): # {{{
		def check_columns(header): # {{{
			columns = header.split()
			assert columns[IDX_START+1] == 'time'
			assert columns[IDX_DST+1] == 'dst'
			assert columns[IDX_DUR+1] == 'TUNC'
			assert columns[IDX_ALIAS+1] == 'alias'
			assert columns[IDX_NMEASURES+1] == 'nmeasurements'
		# }}}
		def parse(line): # {{{
			fields = line.split()
			start = int(fields[IDX_START])
			dst = aton(fields[IDX_DST])
			duration = int(fields[IDX_DUR])
			alias = int(fields[IDX_ALIAS])
			nmeasures = int(fields[IDX_NMEASURES])
			return start, dst, duration, alias, nmeasures
		# }}}

		IDX_START = 2
		IDX_DST = 3
		IDX_DUR = 5
		IDX_ALIAS = 10
		IDX_NMEASURES = 11
		ifile = 'fpath.gz'
		ofile = 'dst2routes.pickle'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		ifile = gzip.open(ifile, 'r')
		check_columns(ifile.readline())
		dst2routes = defaultdict(list)
		for line in ifile:
			if line[0] == '#':
				continue
			start, dst, duration, alias, nmeasures = parse(line)
			assert not dst2routes[dst] or start == dst2routes[dst][-1].end
			route = Route(self.ds, self.name, dst, start, duration, alias,
					nmeasures)
			dst2routes[dst].append(route)
		ifile.close()
		ofile = open(ofile, 'w')
		cPickle.dump(dst2routes, ofile)
		ofile.close()
		return dst2routes
	# }}}

	def get_route2activity(self, window_size): # {{{
		if self.winsz2route2act[window_size] is not None:
			return self.winsz2route2act[window_size]
		ifile = 'dst2routes.pickle'
		ifile = os.path.join(config.outdir[self.ds], self.name, ifile)
		ofile = 'route2activity_w%d.pickle' % window_size
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		if not os.path.exists(ofile) \
				or os.path.getmtime(ofile) <= os.path.getmtime(ifile):
			self.winsz2route2act[window_size] = self.make_route2activity()
			return self.winsz2route2act[window_size]
		fd = open(ofile)
		self.winsz2route2act[window_size] = cPickle.load(fd)
		fd.close()
		return self.winsz2route2act[window_size]
	# }}}

	def make_route2activity(self, window_size): # {{{
		from saikko.prevalence import PathActivityCalculator
		ifile = 'dst2routes.pickle'
		ifile = os.path.join(config.outdir[self.ds], self.name, ifile)
		ofile = 'route2activity_w%d.pickle' % window_size
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		dst2routes = self.get_dst2routes()
		route2activity = dict()
		for _dst, routes in dst2routes.items():
			calc = PathActivityCalculator(window_size)
			for route in routes:
				calc.update(route.start, route.alias)
				route2activity[route] = calc[route.alias]
		ofile = open(ofile)
		cPickle.dump(route2activity, ofile)
		ofile.close()
		return route2activity
	# }}}

	def get_dst2prevperiods(self, threshold, window_size): # {{{
		key = (threshold, window_size)
		if self.key2dst2pp[key] is not None:
			return self.key2dst2pp[key]
		ifile = 'fpath.gz'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ofile = 'dst2prevperiods_t%d_w%d.pickle' % \
				(int(threshold*100), window_size)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		if not os.path.exists(ofile) \
				or os.path.getmtime(ofile) <= os.path.getmtime(ifile):
			self.key2dst2pp[key] = self.make_dst2prevperiods(threshold,
					window_size)
			return self.key2dst2pp[key]
		fd = open(ofile)
		self.key2dst2pp[key] = cPickle.load(fd)
		fd.close()
		return self.key2dst2pp[key]
	# }}}

	def make_dst2prevperiods(self, threshold, window_size): # {{{
		def check_columns(header_line): # {{{
			assert header_line[0] == '#'
			fields = header_line.split()
			assert fields[IDX_DST+1] == 'dst'
			assert fields[IDX_ALIAS+1] == 'alias'
			assert fields[IDX_NOW+1] == 'time'
			assert fields[IDX_DURATION+1] == 'TUNC'
		# }}}
		def parse_line(line): # {{{
			fields = line.split()
			now = int(fields[IDX_NOW])
			dst = aton(fields[IDX_DST])
			alias = int(fields[IDX_ALIAS])
			duration = int(fields[IDX_DURATION])
			return now, dst, alias, duration
		# }}}
		def period_end_cb(dom_period): # {{{
			dst2periods[dst].add(dom_period)
		# }}}

		from saikko.prevalence import DomPeriodBuilder
		IDX_NOW = 2
		IDX_DST = 3
		IDX_DURATION = 5
		IDX_ALIAS = 10
		ifile = 'fpath.gz'
		ifile = os.path.join(config.changedb[self.ds], self.name, ifile)
		ifile = gzip.open(ifile)
		check_columns(ifile.readline())
		dst2periods = dict()
		dst2builder = defaultdict(lambda: \
				DomPeriodBuilder(threshold, window_size, period_end_cb))
		for line in ifile:
			now, dst, alias, duration = parse_line(line)
			dst2builder[dst].update(now, alias, duration)
			if dst not in dst2periods:
				dst2periods[dst] = PathPrevalentPeriods()
		for dst, builder in dst2builder.items():
			builder.close()
		ifile.close()

		ofile = 'dst2prevperiods_t%d_w%d.pickle' % \
				(int(threshold*100), window_size)
		ofile = os.path.join(config.outdir[self.ds], self.name, ofile)
		ofile = open(ofile, 'w')
		cPickle.dump(dst2periods, ofile)
		ofile.close()
		return dst2periods
	# }}}

	def get_dst2runlog(self, name='perc:20-50-20-90'): # {{{
		if self.name2dst2runlog[name] is not None:
			return self.name2dst2runlog[name]
		ifile = 'dst2runlog_%s.pickle' % name
		ifile = os.path.join(config.outdir[self.ds], self.name, ifile)
		if not os.path.exists(ifile):
			sys.stderr.write('input file %s not found.\n' % ifile)
			sys.stderr.write('build it with the insta script.\n')
			sys.exit(-1)
		fd = open(ifile)
		self.name2dst2runlog[name] = cPickle.load(fd)
		fd.close()
		return self.name2dst2runlog[name]
	# }}}

	def get_dst2periods(self, name='hmm'): # {{{
		if self.name2dst2periods[name] is not None:
			return self.name2dst2periods[name]
		ifile = 'dst2periods_%s.pickle' % name
		ifile = os.path.join(config.outdir[self.ds], self.name, ifile)
		if not os.path.exists(ifile):
			sys.stderr.write('input file %s not found.\n' % ifile)
			sys.stderr.write('build it with the insta script.\n')
			sys.exit(-1)
		fd = open(ifile)
		self.name2dst2periods[name] = cPickle.load(fd)
		fd.close()
		return self.name2dst2periods[name]
	# }}}
# }}}


class Path(object): # {{{
	def __init__(self, dst, mondata): # {{{
		self.dst = dst
		self.mon = mondata
	# }}}

	def srcdst(self): # {{{
		return (self.mon.name, self.dst)
	# }}}

	def get_route(self, time): # {{{
		routes = self.mon.get_dst2routes()[self.dst]
		k = Route(None, None, None, time, 0, None, None)
		i = bisect.bisect(routes, k)
		return routes[max(0, i-1)]
	# }}}

	def get_routes(self): # {{{
		return self.mon.get_dst2routes()[self.dst]
	# }}}

	def get_change(self, time): # {{{
		changes = self.mon.get_dst2changes()[self.dst]
		k = Change(None, time, None, None, None)
		i = bisect.bisect(changes, k)
		if i == len(changes) and changes[i-1].time != time:
			return None
		assert time == changes[max(0, i-1)].time, '%d %d %d %s' % (
				time, i, len(changes), changes[0])
		return changes[max(0, i-1)]
	# }}}

	def get_period(self, time, insta='hmm'): # {{{
		periods = self.mon.get_dst2periods(insta)[self.dst]
		route = Route(None, None, self.dst, time, 0, None, None)
		key = Period(route, None, STABLE)
		i = bisect.bisect(periods, key)
		assert i > 0
		period = periods[i-1]
		if time == period.end:
			assert i == len(periods)
			return None
		else:
			assert period.start <= time < period.end
			return period
	# }}}

	def slice_routes(self, start, end): # {{{
		self[start:end]
	# }}}

	def __getslice__(self, start, end): # {{{
		'''Return the list of routes that overlap with start and end.'''
		# count_changes is implemented with len(slice_routes())-1
		routes = self.mon.get_dst2routes()[self.dst]
		k = Route(None, None, None, start, 0, None, None)
		i_start = bisect.bisect(routes, k) - 1
		k.start = end
		i_end = bisect.bisect(routes, k)
		assert routes[i_start].start <= start < routes[i_start].end
		assert routes[i_end-1].start <= end < routes[i_end-1].end \
				or (i_end == len(routes) and routes[i_end-1].end == end)
		# if self.routes[i_start].end == end or i_end == len(self.routes) - 1:
		#	i_end += 1
		assert i_end - i_start > 0
		return routes[i_start:i_end]
	# }}}

	def dataset_start(self): # {{{
		return self.mon.get_dst2routes()[self.dst][0].start
	# }}}
	def dataset_end(self): # {{{
		return self.mon.get_dst2routes()[self.dst][-1].end
	# }}}

	# def get_next(self, time): # {{{
	# 	deprecated. use self.get_route(time).end
	#	return self.get_route(time).end
	# }}}
	# def count_changes(self, start_time, end_time): # {{{
	#	routes = self.mondata.get_dst2routes()[self.dst]
	#	k = Route(None, None, None, start_time, 0, None, None)
	#	i_start = bisect.bisect(routes, k)
	#	k.start = end_time
	#	i_end = bisect.bisect(routes, k)
	#	assert i_start == 0 or routes[i_start-1].start <= start_time
	#	assert i_start == len(routes) \
	#			or routes[i_start].start > start_time
	#	assert i_end == 0 or routes[i_end-1].start <= end_time
	#	assert i_end == len(routes) \
	#			or routes[i_end].start > end_time
	#	return i_end - i_start
	# }}}
	# def get_changes(self): # {{{
	# 	if self.changes is None:
	# 		dst2changes = self.mon.get_dst2changes()
	# 		self.changes = dst2changes[self.dst]
	# }}}
	# def get_periods(self, insta='hmm'): # {{{
	# 	self.periods = self.mon.get_dst2periods(insta)[self.dst]
	# }}}
# }}}


class Change(object): # {{{
	def __init__(self, dst, time, bttls, nASes, nhops): # {{{
		self.dst = dst
		self.time = time
		self.bttls = bttls
		self.nASes = nASes
		self.nhops = nhops
	# }}}

	def __cmp__(self, other): # {{{
		return cmp(self.time, other.time)
	# }}}

	def extend(self, bttl, nASes, nhops): # {{{
		self.bttls.append(bttl)
		self.nASes.append(nASes)
		self.nhops.append(nhops)
	# }}}

	def __str__(self): # {{{
		return 'change time=%d dst=%s branches=%s nhops=%s' % (
				self.time, ntoa(self.dst), str(self.bttls), str(self.nhops))
	# }}}
# }}}


class Route(object): # {{{
	def __init__(self, ds, mon, dst, start, duration, alias, nmeasures): # {{{
		self.ds = ds
		self.mon = mon
		self.dst = dst
		self.start = start
		self.end = start + duration
		self.duration = duration
		self.alias = alias
		self.nmeasures = nmeasures
	# }}}

	def __hash__(self): # {{{
		return hash((self.mon, self.dst, self.start))
	# }}}

	def __cmp__(self, other): # {{{
		if self.start < other.start: return -1
		if self.start > other.start: return +1
		return 0
	# }}}

	def __eq__(self, other): # {{{
		return self.start == other.start
	# }}}

	def get_hops(self): # {{{
		# pylint: disable-msg=E1101
		# mondata added outside __init__
		return self.mondata.get_hops(self.dst, self.start)
	# }}}

	def copy(self): # {{{
		return Route(self.ds, self.mon, self.dst, self.start, self.duration,
				self.alias, self.nmeasures)
	# }}}
# }}}


class PrevalencePeriod(object): # {{{
	def __init__(self, start, end, alias, activity): # {{{
		self.start = start
		self.end = end
		self.alias = alias
		self.activity = activity
	# }}}

	def __str__(self): # {{{
		return '%d,%d,%d,%.3f' % (self.start, self.end, self.alias,
				self.activity)
	# }}}

	def __eq__(self, pp): # {{{
		return pp is not None and self.start == pp.start \
				and self.end == pp.end \
				and self.alias == pp.alias and self.activity == pp.activity
	# }}}

	def __ne__(self, pp): # {{{
		return not self == pp
	# }}}

	def __cmp__(self, pp):  #{{{
		return cmp(self.start, pp.start)
	# }}}
# }}}


class PathPrevalentPeriods(object): # {{{
	def __init__(self): # {{{
		self.pps = list()
	# }}}

	def __getitem__(self, time): # {{{
		if not self.pps:
			return None
		auxpp = PrevalencePeriod(time, 0, 0, 0)
		closestidx = bisect.bisect(self.pps, auxpp) - 1
		if closestidx == -1:
			return None
		closestpp = self.pps[closestidx]
		assert closestpp.start <= time
		if closestpp.end >= time:
			return closestpp
		else:
			return None
	# }}}

	def __iter__(self): # {{{
		return iter(self.pps)
	# }}}

	def add(self, pp): # {{{
		bisect.insort(self.pps, pp)
	# }}}

	def nextpp(self, time): # {{{
		if not self.pps:
			return None
		auxpp = PrevalencePeriod(time, 0, 0, 0)
		closestidx = bisect.bisect(self.pps, auxpp)
		if closestidx == len(self.pps):
			return None
		closestpp = self.pps[closestidx]
		assert closestpp.start >= time
		return closestpp
	# }}}

	def get_relevant_pp(self, route): # {{{
		'''Return route's prevalence period if it starts before route.end.
		Otherwise return self[route.start].'''
		c1 = self[route.start]
		if c1 is not None and c1.alias == route.alias:
			return c1
		c2 = self[route.end]
		if c2 is not None and c2.alias == route.alias:
			return c2
		return c1
	# }}}
# }}}


class Period(object): # {{{
	def __init__(self, curr_route, prev_route, type_): # {{{
		self.start = curr_route.start
		self.end = None
		self.duration = None
		self.prev_route = None if prev_route is None else prev_route.copy()
		self.next_route = None
		self.routes = [curr_route.copy()]
		self.distinct_aliases = set([curr_route.alias])
		assert type_ == STABLE or type_ == UNSTAB
		self.type = type_

		# Routes with duration between perc_stable and perc_unstable:
		self.ambiguous_route_durations = 0
	# }}}

	def __cmp__(self, o): # {{{
		assert self.routes[0].dst == o.routes[0].dst
		return cmp(self.start, o.start)
	# }}}

	def add(self, route): # {{{
		assert abs(self.routes[-1].end - route.start) < 1e-6
		self.routes.append(route.copy())
		self.distinct_aliases.add(route.alias)
	# }}}

	def close(self, next_route): # {{{
		self.end = self.routes[-1].end
		self.duration = self.end - self.start
		self.next_route = None if next_route is None else next_route.copy()
	# }}}

	def classify(self, start_pp, end_pp, next_pp, prevp): # {{{
		OLD_DOM = '+'
		NEW_DOM = '*'
		assert self.end is not None
		prev_type = '.' if self.prev_route is None else '-'
		next_type = '.' if self.next_route is None else '-'
		if next_pp is not None and self.next_route is not None \
				and self.next_route.alias == next_pp.alias:
			next_type = NEW_DOM
		elif start_pp is not None and self.next_route is not None \
				and self.next_route.alias == start_pp.alias \
				and start_pp.end >= self.next_route.start:
			next_type = OLD_DOM
		elif end_pp is not None and self.next_route is not None \
				and end_pp.end >= self.next_route.start:
			next_type = OLD_DOM
		if start_pp is not None and self.prev_route is not None \
				and self.prev_route.alias == start_pp.alias:
			prev_type = OLD_DOM
		elif (next_type == NEW_DOM or next_type == OLD_DOM) \
				and self.prev_route is not None \
				and self.prev_route.alias == self.next_route.alias:
			prev_type = next_type
		next_pp_status = 'y' if next_pp is not None or end_pp is not None \
				else 'n'
		prev_pp_status = 'y' if start_pp is not None else 'n'
		prev_inside = False
		for route in self.routes:
			pp = prevp[route.start]
			if pp is not None and pp.alias == route.alias:
				prev_inside = True
				break
		clas = prev_pp_status + next_pp_status + prev_type + next_type
		return clas, prev_inside
	# }}}
# }}}


class ClusterVizData(object): # {{{
	def __init__(self): # {{{
		self.route2state = dict()
		self.route2extra = dict()
		self.data = list()
	# }}}

	def add(self, route, state, extra=None): # {{{
		mroute = route.copy()
		assert state == STABLE or state == UNSTAB
		self.route2state[mroute] = state
		self.route2extra[mroute] = extra
		self.data.append((mroute, state, extra))
	# }}}
# }}}


def time_sequence_iterator(mondata, dst, kwargs): # {{{
	routes = mondata.get_dst2routes()[dst]
	ctime = routes[0].start
	interval = kwargs['interval']
	seq = list()
	for route in routes:
		while route.start > ctime + interval:
			yield seq
			seq = list()
			ctime += interval
		seq.append(route)
	yield seq
	raise StopIteration
# }}}
def prevalence_period_iterator(mondata, dst, _kwargs): # {{{
	path = mondata[dst]
	pps = mondata.get_dst2prevperiods(0.9, 259200)[dst]
	for prev in pps:
		routes = path.slice_routes(prev.start, prev.end)
		assert routes[0].alias == prev.alias
		yield routes
	raise StopIteration
# }}}
def instability_period_iterator(mondata, dst, kwargs): # {{{
	instatype = kwargs.get('insta', 'hmm')
	periods = mondata.get_dst2periods(instatype)[dst]
	for p in periods:
		if p.type == UNSTAB:
			yield list(p.routes)
	raise StopIteration
# }}}
class Sequencer(object): # {{{
	'''Iterates over routes in a path to build smaller sequences.

	Possible values for seqtype are:
	'time' -- accepts an 'interval' parameter in kwargs (in seconds)
	'prevperiods' -- parameters currently fixed to 90% activity and 3d window
	'instaperiods' -- accepts a name from the insta/ script'''

	type2iter = {'time': time_sequence_iterator,
			'prevperiods': prevalence_period_iterator,
			'instaperiods': instability_period_iterator}

	def __init__(self, seqtype, mondata, dst, **kwargs):
		self.seqtype = seqtype
		self.mondata = mondata
		self.dst = dst
		self.kwargs = kwargs

	def __iter__(self):
		cls = Sequencer.type2iter[self.seqtype]
		return cls(self.mondata, self.dst, self.kwargs)

# }}}
