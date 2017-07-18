import os

import numpy

class HMM(object): # {{{
	def __init__(self, nstates, nsymbols, name=''): # {{{
		self.pi = [1.0/nstates] * nstates
		self.A = [[1.0/nstates] * nstates] * nstates
		self.B = [[1.0/nsymbols] * nsymbols] * nstates
		self.nstates = nstates
		self.nsymbols = nsymbols
		self.name = name
	# }}}

	def normalize(self): # {{{
		def normvec(v):
			t = sum(v)
			return [p/t for p in v]
		self.pi = normvec(self.pi)
		self.A = [normvec(Ai) for Ai in self.A]
		self.B = [normvec(Bi) for Bi in self.B]
	# }}}

	def train(self, mtk_pexpect_object, observations): # {{{
		def write_float(string, value): # {{{
			mtk_pexpect_object.sendline('%s = %.3f;' % (string, value))
			mtk_pexpect_object.expect(prompt)
		# }}}
		def read_float(string): # {{{
			mtk_pexpect_object.sendline(string)
			mtk_pexpect_object.expect('(\d[.]\d+e[+-]\d+)\r\n')
			# pyling: disable-msg=E1103
			f = float(mtk_pexpect_object.match.group(1))
			mtk_pexpect_object.expect(prompt)
			return f
		# }}}
		prompt = 'MTK:\d+>'
		hmmstr = 'hmm%s' % self.name
		mtk_pexpect_object.sendline('delete %s;' % hmmstr)
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('%s = new hmm(%d, %d);' % (hmmstr,
				self.nstates, self.nsymbols))
		mtk_pexpect_object.expect(prompt)
		for i in range(self.nstates):
			write_float('%s.pi[%d]' % (hmmstr, i), self.pi[i])
			for j, Aij in enumerate(self.A[i]):
				write_float('%s.A[%d][%d]' % (hmmstr, i, j), Aij)
			for j, Bij in enumerate(self.B[i]):
				write_float('%s.B[%d][%d]' % (hmmstr, i, j), Bij)
		mtk_pexpect_object.sendline('delete x;')
		mtk_pexpect_object.expect(prompt)
		HMM.mtk_write_array(observations, 'observations.txt')
		mtk_pexpect_object.sendline('x = new intvalue("observations.txt");')
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('%s.train(100, 0.000001, x);' % hmmstr)
		mtk_pexpect_object.expect(prompt)
		os.remove('observations.txt')
		for i in range(self.nstates):
			self.pi[i] = read_float('%s.pi[%d];' % (hmmstr, i))
			for j in range(self.nstates):
				self.A[i][j] = read_float('%s.A[%d][%d];' % (hmmstr, i, j))
			for j in range(self.nsymbols):
				self.B[i][j] = read_float('%s.B[%d][%d];' % (hmmstr, i, j))
	# }}}

	def viterbi(self, mtk_pexpect_object, return_all=False): # {{{
		prompt = 'MTK:\d+>'
		hmmstr = 'hmm%s' % self.name
		mtk_pexpect_object.sendline('delete r;')
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('r = new intvalue();')
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('%s.viterbi(x, r);' % hmmstr)
		mtk_pexpect_object.expect('.*Last state = (\d+).*\r\n')
		s = int(mtk_pexpect_object.match.group(1)) # pylint: disable-msg=E1103
		mtk_pexpect_object.expect(prompt)
		if return_all:
			mtk_pexpect_object.sendline('r.save("viterbi.txt");')
			mtk_pexpect_object.expect(prompt)
			fd = open('viterbi.txt', 'r')
			fd.readline() # first line contains the number of states
			states = [int(i.strip()) for i in fd]
			fd.close()
			os.remove('viterbi.txt')
			assert states[0] < self.nstates
			return states
		return s
	# }}}

	def steady_state(self): # {{{
		def converged(A, B): # {{{
			diff = A[0] - B[0]
			for i in range(A[0].size):
				if diff[0, i] >= 1e-6:
					return False
			return True
		# }}}
		Aold = numpy.matrix(self.A)
		A = Aold**2
		while not converged(A, Aold):
			Aold = A
			A = Aold**2
		return list(A[0].flat)
	# }}}

	@staticmethod
	def mtk_write_array(array, filename): # {{{
		fd = open(filename, 'w')
		fd.write('%d\n' % len(array))
		fd.write('\n'.join([str(i) for i in array]))
		fd.close()
	# }}}
# }}}

class HMM3(HMM): # {{{
	def __init__(self, name): # {{{
		super(HMM3, self).__init__(3, 2, name)
		self.reset()
	# }}}

	def reset(self): # {{{
		assert self.nstates == 3
		assert self.nsymbols == 2
		self.pi = [0.899, 0.001, 0.1]
		self.A = [[0.95, 0.05, 0], [0.0, 0.0, 1.0], [0.1, 0.0, 0.9]]
		self.B = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.3]]
	# }}}

	def train(self, mtk_pexpect_object, observations): # {{{
		self.reset()
		super(HMM3, self).train(mtk_pexpect_object, observations)
		self.viterbi(mtk_pexpect_object)
	# }}}

	def viterbi(self, mtk_pexpect_object, _return_all=False): # {{{
		s = super(HMM3, self).viterbi(mtk_pexpect_object)
		s = 2 if s == 1 else s
		# need the above otherwise we're limited to outputting a change.
		self.pi = [(1.0 if i == s else 0.0) for i in range(self.nstates)]
		prompt = 'MTK:\d+>'
		hmmstr = 'hmm%s' % self.name
		for i, pii in enumerate(self.pi):
			mtk_pexpect_object.sendline('%s.pi[%d] = %.3f;' % (hmmstr, i, pii))
			mtk_pexpect_object.expect(prompt)
	# }}}

	def likelihood(self, mtk_pexpect_object, trace): # {{{
		prompt = 'MTK:\d+>'
		hmmstr = 'hmm%s' % self.name
		HMM.mtk_write_array(trace, 'trace.txt')
		mtk_pexpect_object.sendline('delete t;')
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('t = new intvalue("trace.txt");')
		mtk_pexpect_object.expect(prompt)
		mtk_pexpect_object.sendline('%s.likelihood(t);' % hmmstr)
		mtk_pexpect_object.expect('.*likelihood = (\d[.]\d+e[+-]\d+).*\r\n')
		# pyling: disable-msg=E1103
		likelihood = float(mtk_pexpect_object.match.group(1))
		mtk_pexpect_object.expect(prompt)
		os.remove('trace.txt')
		return likelihood
	# }}}

	def likelihood_change(self, mtk_pexpect_object, n): # {{{
		trace = [0]*n
		return 1 - self.likelihood(mtk_pexpect_object, trace)
	# }}}
# }}}
