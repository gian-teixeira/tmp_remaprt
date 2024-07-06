from struct import pack, unpack
from socket import inet_ntoa, inet_aton

STAR = unpack('!I', '\xff\xff\xff\xff')[0]

def aton(string): return unpack('!I', inet_aton(string))[0]
def asip(integer): return inet_ntoa(pack('!I', integer))
def ntoa(integer): return inet_ntoa(pack('!I', integer))
