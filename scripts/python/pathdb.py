from collections import defaultdict


class PathDatabase(object): # {{{
	def __init__(self, timeout): # {{{
		self.timeout = timeout
		self.dst2paths = defaultdict(list)
	# }}}

	def get(self, path): # {{{
		candidates = list()
		self.dst2paths[path.dst] = [t for t in self.dst2paths[path.dst]
				if path.time - t[0].time <= self.timeout]
		for ppbals in self.dst2paths[path.dst]:
			pp, bals = ppbals
			assert path.time >= pp.time
			if _check_equal(pp, path, bals):
				candidates.append(tuple([pp.time, pp, bals]))
		return max(candidates) if candidates else None
	# }}}

	def add(self, path, balset): # {{{
		self.dst2paths[path.dst] = [t for t in self.dst2paths[path.dst]
				if path.time - t[0].time <= self.timeout]
		for i, ppbals in enumerate(self.dst2paths[path.dst]):
			pp, bals = ppbals
			assert path.time >= pp.time
			if _check_equal(pp, path, bals) and bals == balset:
				self.dst2paths[path.dst][i] = (path, balset)
				break
		else:
			self.dst2paths[path.dst].append((path, balset))
	# }}}
# }}}


def _check_equal(pp, path, balset): # {{{
	events = pp.diff(path, False, False, balset)
	if events: return False
	pp.diff(path, True, True, balset)
	return True
# }}}
