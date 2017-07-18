from socket import inet_ntoa
from struct import unpack, pack
import time

# Unresponsive hops are stored as 0xffff in the dataset and printed as
# 255.255.255.255 by the __str__ functions below. Useful definition:
STAR = unpack('!I', '\xff\xff\xff\xff')[0]

def ip2a(ip): return inet_ntoa(pack('!I', ip))

class Snapshot(object):
	'''A Snapshot contains a dst2path dictionary that stores a mapping between
	a destination and it's path during this measurement round.'''

	def __init__(self, dst2path):
		self.dst2path = dst2path

	def __str__(self):
		return '\n'.join(str(p) for p in self.dst2path.values())

	@staticmethod
	def read(fd):
		dst2path = dict()
		npaths = unpack('!I', fd.read(4))[0]
		for _ in range(npaths):
			path = Path.read(fd)
			dst2path[path.dst] = path
		return Snapshot(dst2path)


class Path(object):
	'''A Path contains a dst field that stores its destination (in integer
	form), a tstamp field that stores when the path was measured, and a hops
	field that stores its list of hops.'''

	def __init__(self, dst, timestamp, hops):
		self.dst = dst
		self.tstamp = timestamp
		self.hops = list(hops)

	def __str__(self):
		sstr = '%s, %d\n' % (ip2a(self.dst), time.time())
		return sstr + '\n'.join(str(h) for h in self.hops) + '\n'

	@staticmethod
	def read(fd):
		dst, tstamp, hopcnt = unpack('!III', fd.read(4*3))
		hops = list()
		for _ in range(hopcnt):
			hop = Hop.read(fd)
			hops.append(hop)
		return Path(dst, tstamp, hops)


class Hop(object):
	'''A Hop contains an ip2flows dictionary that maps a set of IPs in a hop to
	the set of flow ids that traverse each IP. For hops that are not under load
	balancing, ip2flows will have a single key associated to the value None.
	For hops under load balancing, ip2flows will have many keys associated to a
	set of integers.'''

	def __init__(self, ip2flows):
		self.ip2flows = ip2flows

	def __str__(self):
		if len(self.ip2flows) == 1:
			ip, _none = self.ip2flows.popitem()
			return '%s' % ip2a(ip)
		ipflows = lambda ip: ','.join(str(f) for f in self.ip2flows[ip])
		return ' '.join('%s:%s' % (ip2a(ip), ipflows(ip)) for
				ip in self.ip2flows)

	@staticmethod
	def read(fd):
		ip2flows = dict()
		nips = unpack('!I', fd.read(4))[0]
		if nips == 1:
			ip = unpack('!I', fd.read(4))[0]
			ip2flows[ip] = None
		else:
			for _ in range(nips):
				ip, nflows = unpack('!II', fd.read(4*2))
				flows = unpack('!' + 'I'*nflows, fd.read(4*nflows))
				ip2flows[ip] = frozenset(flows)
		return Hop(ip2flows)
