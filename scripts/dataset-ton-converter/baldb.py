import os
import bisect
import cPickle
from collections import defaultdict
from socket import inet_ntoa
from struct import unpack, pack

STAR = unpack('!I', '\xff\xff\xff\xff')[0]
def ntoa(integer): return inet_ntoa(pack('!I', integer))


class BalancerDatabase(object): # {{{
	def brice_stats(self): # {{{
		npath = len(self.dst2container)
		nbal2npath = defaultdict(lambda: 0)
		nbal, nsym, nppkt = 0, 0, 0
		for cont in self.dst2container.values():
			c_nbal = len(cont.balancers)
			nbal2npath[c_nbal] += 1
			nbal += c_nbal
			for bal in cont:
				if LoadBalancer.FLAG_ASYMMETRIC not in bal.flags:
					nsym += 1
				if LoadBalancer.FLAG_PER_PACKET in bal.flags:
					nppkt += 1
		npath_3p = npath - nbal2npath[0] - nbal2npath[1] - nbal2npath[2]
		# number_of_paths number_of_paths_with_0 1 2 or_more_than_2_balancers
		# number_of_balancers number_of_symmetric_balancers
		# number_of_per_packet_balancers
		return npath, nbal2npath[0], nbal2npath[1], nbal2npath[2], npath_3p, \
				nbal, nsym, nppkt
	# }}}

	def patch_with_file(self, inputfile): # {{{
		patchdb = BalancerDatabase.read(inputfile)
		for dst, container in patchdb.dst2container.items():
			self.dst2container[dst] = container
	# }}}

	def dump(self, outputfile): # {{{
		outputfile.write(pack('!I', len(self.dst2container)))
		for dst in sorted(self.dst2container.keys()):
			self.dst2container[dst].dump(outputfile)
	# }}}

	def __getitem__(self, dst): # {{{
		try:
			return self.dst2container[dst]
		except KeyError:
			return BalancerSet(dst, None)
	# }}}

	def __init__(self, dst2container=None): # {{{
		self.dst2container = dict() if dst2container is None else dst2container
	# }}}

	def __str__(self): # {{{
		string = str()
		for container in self.dst2container.values():
			string += str(container) if len(container.balancers) > 0 else ''
		return string
	# }}}

	@staticmethod
	def read(inputfile, extrafile=None): # {{{
		dst2container = dict()
		pathcnt = unpack('!I', inputfile.read(4))[0]
		for _ in range(pathcnt):
			container = BalancerSet.read(inputfile, extrafile)
			dst2container[container.dst] = container
		return BalancerDatabase(dst2container)
	# }}}

	@staticmethod
	def read_and_dump_extra(inputfile, outfile): # {{{
		dst2container = dict()
		pathcnt = unpack('!I', inputfile.read(4))[0]
		for _ in range(pathcnt):
			container = BalancerSet.read(inputfile, None)
			dst2container[container.dst] = container
			for bal in container:
				bal.dump_extra_data(outfile)
		return BalancerDatabase(dst2container)
	# }}}
# }}}


class BalancerSet(object): # {{{
	def check_bad_asymmetric(self): # {{{
		for i, bal in enumerate(self.balancers):
			if LoadBalancer.FLAG_ASYMMETRIC in bal.flags \
					and LoadBalancer.FLAG_NOT_CONVERGED in bal.flags:
				for badbal in self.balancers[i+1:]:
					badbal.flags.add(LoadBalancer.FLAG_BAD_ASYM_UPSTREAM)
				return
	# }}}

	def dump(self, outputfile): # {{{
		outputfile.write(pack('!II', self.dst, len(self.balancers)))
		for balancer in self.balancers:
			balancer.dump(outputfile)
	# }}}

	def __init__(self, dst=None, balancers=None): # {{{
		self.dst = STAR if dst is None else dst
		self.balancers = list() if balancers is None else balancers
		self.check_bad_asymmetric()
	# }}}

	def add_balancers(self, balancers): # {{{
		sentry = LoadBalancer(STAR, 65535, STAR, list(), None)
		balancers.append(sentry)
		self.balancers.append(sentry)
		nbals = list()
		oi, ni = 0, 0
		while oi < len(self.balancers)-1 or ni < len(balancers)-1:
			if self.balancers[oi].bttl <= balancers[ni].bttl:
				nbals.append(self.balancers[oi])
				oi += 1
			else:
				nbals.append(balancers[ni])
				ni += 1
		self.balancers = nbals
	# }}}

	def __contains__(self, ip_or_ip_ttl_pair): # {{{
		for balancer in self.balancers:
			if ip_or_ip_ttl_pair in balancer:
				return True
		return False
	# }}}

	def __getitem__(self, ttl): # {{{
		for balancer in self.balancers:
			if (None, ttl) in balancer:
				return balancer
		return None
	# }}}

	def __iter__(self): return iter(self.balancers)
	def __len__(self): return len(self.balancers)
	def __ne__(self, bals): return not self.__eq__(bals)

	def __eq__(self, bals): # {{{
		if len(self) != len(bals): return False
		for i, bal in enumerate(self.balancers):
			if bal != bals.balancers[i]: return False
		return True
	# }}}

	def __str__(self): # {{{
		balancerstr = '\n'.join([str(b) for b in self.balancers])
		return 'BalancerSet for %s:\n%s' % (ntoa(self.dst), balancerstr)
	# }}}

	@staticmethod
	def read(inputfile, extrafile=None): # {{{
		dst, balancercnt = unpack('!II', inputfile.read(4*2))
		balancers = list()
		for _ in range(balancercnt):
			bal = LoadBalancer.read(inputfile, extrafile)
			balancers.append(bal)
		return BalancerSet(dst, balancers)
	# }}}
# }}}


class LoadBalancer(object): # {{{
	# flags # {{{
	FLAG_PER_PACKET = 'per_packet'
	FLAG_PER_FLOW = 'per_flow'
	FLAG_PER_DST = 'per_dst'
	FLAG_ASYMMETRIC = 'asymmetric'
	FLAG_NOT_CONVERGED = 'not_converged'
	FLAG_LOOP = 'loop'
	FLAG_MULTI_HOP_LOOP = 'multi_hop_loop'
	FLAG_BRANCH_WO_CONVERGENCE_IP = 'branch_wo_convergence_ip'
	FLAG_BAD_ASYM_UPSTREAM = 'bad_asym_upstream'
	FLAG_FLOWS_UP_DIAMOND = 'flows_up_diamond'
	FLAG_SINGLE_PARENT_LOOP = 'single_parent_loop'
	# }}}

	def flags_update_type(self): # {{{
		self.flags -= set([LoadBalancer.FLAG_PER_PACKET,
				LoadBalancer.FLAG_PER_FLOW])
		for nn in self.nexthops:
			if nn.type == LoadBalancer.FLAG_PER_PACKET:
				self.flags.add(LoadBalancer.FLAG_PER_PACKET)
				break
		else:
			self.flags.add(LoadBalancer.FLAG_PER_FLOW)
	# }}}

	def calc_parents(self): # {{{
		# pylint: disable-msg=R0912
		self.ip2parents = defaultdict(set)
		self.ip2child = defaultdict(set)
		if not self.nexthops: return
		for ip in self.nexthops[0].ip2flows:
			if ip == self.branch: continue
			self.ip2parents[ip].add(self.branch)
			self.ip2child[self.branch].add(ip)
		for ttl, nn in enumerate(self.nexthops):
			if ttl == 0: continue
			pnn = self.nexthops[ttl - 1]
			for ip, flows in nn.ip2flows.items():
				parents = set()
				for pip, pflows in pnn.ip2flows.items():
					if pflows.intersection(flows):
						parents.add(pip)
				if ip in parents:
					self.flags.add(LoadBalancer.FLAG_LOOP)
					parents.remove(ip)
				for pip in parents:
					if pip in self.ip2child[ip]:
						self.flags.add(LoadBalancer.FLAG_FLOWS_UP_DIAMOND)
					self.ip2parents[ip].add(pip)
					self.ip2child[pip].add(ip)
		for ip in self.nexthops[-1].ip2flows:
			if ip == self.join: continue
			self.ip2child[ip].add(self.join)
			self.ip2parents[self.join].add(ip)
	# }}}

	def branches_to_divergence(self, ip, ancestors_): # {{{
		if ip == self.branch or self.multi_link_loop:
			return set([len(ancestors_)])
		# branches = set()
		# ips = set()
		lengths = set()
		ancestors = set(ancestors_)
		ancestors.add(ip)
		for p in self.ip2parents[ip]:
			if p in ancestors:
				self.flags.add(LoadBalancer.FLAG_MULTI_HOP_LOOP)
				self.multi_link_loop = True
			if p in self.ip2branches:
				up_lengths = self.ip2branches[p]
			else:
				up_lengths = self.branches_to_divergence(p, ancestors)
				self.ip2branches[p] = up_lengths
			lengths.update(up_lengths)
			# branches.update(up_branches)
			# ips.update(up_ips)
			# ips.add(p)
		return lengths
	# }}}

	def find_convergence(self): # {{{
		candidate = self.join
		downstream = set()
		while len(self.ip2parents[candidate]) == 1 \
				and candidate not in downstream:
			downstream.add(candidate)
			candidate = iter(self.ip2parents[candidate]).next()
		if candidate in downstream:
			self.flags.add(LoadBalancer.FLAG_SINGLE_PARENT_LOOP)
			candidate = self.join
		lengths = self.branches_to_divergence(candidate, set())
		if len(lengths) > 1:
			self.flags.add(LoadBalancer.FLAG_ASYMMETRIC)
			if candidate == self.join:
				self.flags.add(LoadBalancer.FLAG_NOT_CONVERGED)
				# TODO check why it's not converged when candidate == self.join
				# and the LB is asymmetric.
		self.convergence_ip = candidate if candidate != 'join' else STAR
		all_ips = sum([list(nn.ip2flows.keys()) for nn in self.nexthops], [])
		self.convergence_upstream = set(all_ips) - downstream
	# }}}

	def max_flow_unbalance(self): # {{{
		return max(n.max_flow_unbalance() for n in self.nexthops)
	# }}}

	def dump(self, outputfile): # {{{
		d = pack('!IIII', self.branch, self.bttl, self.join, self.hopcnt)
		outputfile.write(d)
		for nexthop in self.nexthops:
			nexthop.dump(outputfile)
	# }}}

	def dump_extra_data(self, outfile): # {{{
		extra = (self.ip2parents, self.ip2child, self.flags,
				self.multi_link_loop, self.convergence_ip,
				self.convergence_upstream)
		cPickle.dump(extra, outfile, -1)
	# }}}

	def __init__(self, branch, branch_ttl, join, nexthops, extra=None): # {{{
		# we make branch and join different from STAR to avoid colisions in
		# ip2parents and ip2child
		self.branch = branch if branch != STAR else 'branch'
		self.bttl = branch_ttl
		self.join = join if join != STAR else 'join'
		self.jttl = branch_ttl + len(nexthops) + 1

		self.hopcnt = len(nexthops)
		self.nexthops = nexthops
		self.flags = set()

		if extra is None:
			self.ip2parents = defaultdict(set)
			self.ip2child = defaultdict(set)
			self.ip2branches = dict()
			self.calc_parents()
			self.flags_update_type()

			self.convergence_ip = STAR
			self.convergence_upstream = set()
			self.multi_link_loop = False
			self.find_convergence()
		else:
			self.ip2parents = extra[0]
			self.ip2child = extra[1]
			self.flags = extra[2]
			self.multi_link_loop = extra[3]
			self.convergence_ip = extra[4]
			self.convergence_upstream = extra[5]

		self.branch = branch
		self.join = join
	# }}}

	def flowid_equal(self, othr):
		def diff_and_not_star(a, b):
			return a != b and a != STAR and b != STAR
		if diff_and_not_star(self.branch, othr.branch):
			return False
		if self.convergence_upstream != othr.convergence_upstream:
			return False
		for i, nhop in enumerate(self.nexthops):
			if not nhop.flowid_equal(othr.nexthops[i]):
				return False
		return True

	def __eq__(self, othr): # {{{
		def diff_and_not_star(a, b):
			return a != b and a != STAR and b != STAR
		if diff_and_not_star(self.branch, othr.branch):
			return False
		return self.convergence_upstream == othr.convergence_upstream
	# }}}
	def __ne__(self, other): return not self == other

	def __contains__(self, ip_or_ip_ttl_pair): # {{{
		try:
			ip, ttl = ip_or_ip_ttl_pair
			assert ip != STAR
			if ttl > self.bttl and ttl < self.jttl:
				if ip is None or ip in self.nexthops[ttl - self.bttl - 1]:
					return True
			return False
		except TypeError:
			ip = ip_or_ip_ttl_pair
			for nexthop in self.nexthops:
				if ip in nexthop:
					return True
			return False
	# }}}

	def __getitem__(self, ttl): # {{{
		return self.nexthops[ttl - self.bttl - 1]
	# }}}

	def __str__(self): # {{{
		branch = self.branch if self.branch != 'branch' else STAR
		join = self.join if self.join != 'join' else STAR
		string = 'LoadBalancer\n'
		string += 'flags: %s\n' % ','.join(self.flags)
		string += 'branch=%s,%d join=%s,%d conv=%s\n' % (
				ntoa(branch), self.bttl,
				ntoa(join), self.jttl,
				ntoa(self.convergence_ip))
		string += '\n'.join(['\t' + str(h) for h in self.nexthops])
		string += '\n'
		return string
		# if 'asymmetrical' in self.flags:
		# 	branches = self.get_branches_to_divergence(self.convergeip)
		# 	for branch in branches:
		# 		string += '%s\n' % ' '.join([ntoa(ip) for ip in branch])
	# }}}

	def width(self):
		return max([len(nn) for nn in self.nexthops])

	@staticmethod
	def read(inputfile, extrafile=None): # {{{
		(branch, bttl, join, hopcnt) = unpack('!IIII', inputfile.read(4*4))
		join = None if join == 0 else join
		nexthops = [BalancedHop.read(inputfile) for _ in range(hopcnt)]
		extras = None
		if extrafile is not None:
			extras = cPickle.load(extrafile)
		return LoadBalancer(branch, bttl, join, nexthops, extras)
	# }}}
# }}}


class BalancedHop(object): # {{{
	def max_flow_unbalance(self): # {{{
		if self.type == LoadBalancer.FLAG_PER_PACKET:
			return 0
		lengths = [len(flows) for flows in self.ip2flows.values()]
		expected = float(sum(lengths)) / len(self.ip2flows)
		return max(abs(l - expected)/expected for l in lengths)
	# }}}

	def dump(self, outputfile): # {{{
		outputfile.write(pack('!I', len(self.ip2flows)))
		for ip, flows in sorted(self.ip2flows.items()):
			outputfile.write(pack('!II', ip, len(flows)))
			for flowid in sorted(flows):
				outputfile.write(pack('!I', flowid))
	# }}}

	def flowid_equal(self, othr):
		ips = set(self.ip2flows.keys())
		othrips = set(othr.ip2flows.keys())
		if ips != othrips:
			return False
		for ip in ips:
			myids = set(self.ip2flows[ip])
			for op in ips - set([ip]):
				otherids = set(othr.ip2flows[op])
				if myids.intersection(otherids):
					return False
		return True

	def __hash__(self): return hash(tuple(self.ip2flows.keys()))
	def __contains__(self, ip): return ip in self.ip2flows
	def __ne__(self, other): return not self == other
	def __eq__(self, other): # {{{
		assert STAR not in self.ips
		assert STAR not in other.ips
		return self.ips == other.ips
	# }}}
	def __len__(self): return len(self.ips)

	def __init__(self, ip2flows=None): # {{{
		self.ip2flows = dict() if ip2flows is None else ip2flows
		self.ifacecnt = len(self.ip2flows)
		self.ips = set(ip2flows.keys())
		self.flows = set()
		self.type = LoadBalancer.FLAG_PER_FLOW
		try:
			self.flow2ip = [STAR] * (max([max(f) for f in ip2flows.values()])+1)
		except ValueError:
			self.flow2ip = list()
			for flows in ip2flows.values():
				if not flows:
					self.type = LoadBalancer.FLAG_PER_PACKET
					break
			else:
				assert False
		else:
			for ip, flows in ip2flows.items():
				for flowid in flows:
					self.flow2ip[flowid] = ip
					self.flows.add(flowid)
	# }}}

	def __str__(self): # {{{
		ipstrings = list()
		for ip, flows in self.ip2flows.items():
			ipstr = '%s:%s' % (ntoa(ip), ','.join([str(f) for f in flows]))
			ipstrings.append(ipstr)
		return ' '.join(ipstrings)
	# }}}

	@staticmethod
	def read(inputfile): # {{{
		ip2flows = dict()
		nips = unpack('!I', inputfile.read(4))[0]
		for _ in range(nips):
			ip, nflows = unpack('!II', inputfile.read(4*2))
			flows = unpack('!' + 'I' * nflows, inputfile.read(4*nflows))
			ip2flows[ip] = frozenset(flows)
		return BalancedHop(ip2flows)
	# }}}
# }}}


class BalancerDirectory(object): # {{{
	def __init__(self, dirpath): # {{{
		self.dirpath = dirpath
		self.tstamps = list()
		entries = os.listdir(dirpath)
		for fn in entries:
			if fn.endswith('.baldb'):
				tstamp = int(fn.split('.')[0])
				self.tstamps.append(tstamp)
		self.tstamps.sort()
		self.fn2db = {None: None}
	# }}}

	def get_latest_before(self, tstamp): # {{{
		i = bisect.bisect(self.tstamps, tstamp)
		i = 1 if i == 0 else i
		fn = str(self.tstamps[i-1]) + '.baldb'
		fn = os.path.join(self.dirpath, fn)
		if os.path.exists(fn):
			return fn
		fn = str(self.tstamps[i-1]) + '.e.baldb'
		fn = os.path.join(self.dirpath, fn)
		if os.path.exists(fn):
			return fn
		return None
	# }}}

	def get_db(self, time): # {{{
		fn = self.get_latest_before(time)
		if fn in self.fn2db:
			return self.fn2db[fn]
		self.fn2db = dict()
		dbfd = open(fn)
		extrafd = None
		if os.path.exists(fn + '.extra'):
			extrafd = open(fn + '.extra')
		baldb = BalancerDatabase.read(dbfd, extrafd)
		self.fn2db[fn] = baldb
		return baldb
	# }}}

	def make_extra_files(self): # {{{
		for tstamp in self.tstamps:
			balfn = self.get_latest_before(tstamp)
			balfd = open(balfn, 'r')
			extrafd = open(balfn + '.extra', 'w')
			baldb = BalancerDatabase.read_and_dump_extra(balfd, extrafd)
			extrafd.close()
			extrafd = open(balfn + '.extra', 'r')
			balfd.close()
			balfd = open(balfn, 'r')
			baldb2 = BalancerDatabase.read(balfd, extrafd)
			for dst, container in baldb.dst2container.items():
				container2 = baldb2.dst2container[dst]
				assert len(container.balancers) == len(container2.balancers)
				balancers = list(container)
				balancers2 = list(container2)
				for i, bal in enumerate(balancers):
					assert bal.flags == balancers2[i].flags
					assert bal.convergence_upstream == \
							balancers2[i].convergence_upstream
	# }}}

	def get_ips(self): # {{{
		ips = set()
		for tstamp in self.tstamps:
			balfn = self.get_latest_before(tstamp)
			balfd = open(balfn, 'r')
			extrafd = open(balfn + '.extra', 'r')
			baldb = BalancerDatabase.read(balfd, extrafd)
			for container in baldb.dst2container.values():
				for balancer in container.balancers:
					for nexthop in balancer.nexthops:
						ips.update(nexthop.ips)
			extrafd.close()
			balfd.close()
		return ips
	# }}}
# }}}
