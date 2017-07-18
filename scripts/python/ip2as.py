import fcntl
import logging

import radix

from defines import ntoa

# input file line format:
# ip/prefix|asn|trash

class IP2ASDatabase(object):
	def __getitem__(self, ip):
		node = self.db.search_best(ntoa(ip))
		self.querycnt += 1
		try:
			return node.data['asn']
		except AttributeError:
			self.misscnt += 1
			logging.info('ip2as fn=%s queries=%d misses=%d', self.dbfn,
					self.querycnt, self.misscnt)
			return 0

	def __init__(self, dbfn='/home/cunha/topo/data/ip2as/fernando.txt'):
		self.db = radix.Radix()
		self.dbfn = dbfn
		self.querycnt, self.misscnt = 0, 0
		infile = open(self.dbfn, 'r')
		fcntl.flock(infile, fcntl.LOCK_SH)
		linecnt = 0
		for line in infile:
			if line[0] == '#':
				continue
			linecnt += 1
			fields = line.split('|')
			addr = fields[0]
			try: asn = int(fields[1])
			except ValueError: asn = 0
			node = self.db.add(addr)
			node.data['asn'] = asn
			node.data['info'] = '|'.join(fields[2:])
		fcntl.flock(infile, fcntl.LOCK_UN)
		infile.close()
		logging.info('ip2as database created. read %d prefixes', linecnt)

