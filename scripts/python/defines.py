import sys
from struct import pack, unpack
from socket import inet_ntoa, inet_aton

STAR = unpack('!I', '\xff\xff\xff\xff')[0]
MAXTTL = 32

def aton(string): return unpack('!I', inet_aton(string))[0]
def asip(integer): return inet_ntoa(pack('!I', integer))
def ntoa(integer): return inet_ntoa(pack('!I', integer))

def normalized(iterable):
	summ = sum(iterable)
	return [float(i)/summ for i in iterable]

_verbose_enabled = False
_verbose_fd = sys.stdout
def verbose(string):
	if _verbose_enabled:
		_verbose_fd.write(string)
def verbose_enable(boolean, fd=sys.stdout):
	global _verbose_enabled, _verbose_fd # pylint: disable-msg=W0603
	_verbose_enabled = boolean
	_verbose_fd = fd
