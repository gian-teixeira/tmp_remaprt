import heapq

__heap = []
now = 0.0

LOW = 10000
MED = 1000
HIGH = 100

def push(event):
	if event[0] < now:
		raise ValueError('event in the past')
	heapq.heappush(__heap, event)

def pop():
	return heapq.heappop(__heap)

def create(timeto, priority, execfunc, funcdata):
	evtime = now + timeto
	return (evtime, priority, execfunc, funcdata)

def createabs(time, priority, execfunc, funcdata):
	return (time, priority, execfunc, funcdata)

def run(event):
	global now				# pylint: disable-msg=W0603
	evtime, _prio, execfunc, funcdata = event
	now = evtime
	execfunc(funcdata)

def reset(starttime=0.0):
	global now				# pylint: disable-msg=W0603
	global __heap			# pylint: disable-msg=W0603
	now = starttime
	__heap = []
