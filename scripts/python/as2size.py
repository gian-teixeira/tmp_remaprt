'''This module will read a file containing information about AS sizes and
provide facilities for easy access to its information. This module is
compatible with AS size information available from UCLA's IRL project
(http://irl.cs.ucla.edu/topology/).'''

AS_TIER1 = 'tier1'
AS_LARGE = 'largeISP'
AS_SMALL = 'smallISP'
AS_STUB = 'stub'
AS_TYPES = frozenset([AS_TIER1, AS_LARGE, AS_SMALL, AS_STUB])

class AS2SizeDatabase(object):

	def __init__(self, fn):
		self.asn2size = dict()
		self.size2asns = {AS_TIER1: list(), AS_LARGE: list(), AS_SMALL: list(),
				AS_STUB: list()}
		fd = open(fn)
		for line in fd:
			asn, size, _degree, _provider, _customer = line.split()
			assert size in AS_TYPES
			try:
				asn = int(asn)
			except ValueError:
				continue
			self.asn2size[asn] = size
			self.size2asns[size].append(asn)


	def __getitem__(self, asnum):
		return self.asn2size.get(asnum, AS_STUB)

	def asns_by_size(self, size):
		return self.size2asns[size]

