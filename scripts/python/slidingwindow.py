from collections import deque

class SlidingWindowIterator(object):
	def __init__(self, slidingwindow):
		self.timeiter = iter(slidingwindow.timelist)
		self.dataiter = iter(slidingwindow.datalist)

	def next(self):
		nexttime = self.timeiter.next()
		nextdata = self.dataiter.next()
		return nexttime, nextdata


class SlidingWindowUniqIterator(object):
	def __init__(self, slidingwindow):
		self.timeiter = iter(slidingwindow.timelist)
		self.dataiter = iter(slidingwindow.datalist)
		self.prevdata = None

	def __iter__(self):
		assert self.prevdata is None
		return self

	def next(self):
		nexttime = self.timeiter.next()
		nextdata = self.dataiter.next()
		while self.prevdata is not None and nextdata == self.prevdata:
			nexttime = self.timeiter.next()
			nextdata = self.dataiter.next()
		self.prevdata = nextdata
		return nexttime, nextdata


class SlidingWindow(object):
	def __init__(self, windowsize, deletecallback=None, deletecbparam=None):
		self.size = windowsize
		self.cbfunc = deletecallback
		self.cbparam = deletecbparam
		self.timelist = deque()
		self.datalist = deque()
		self.total_time = 0
		self.start_ = None

	def __iter__(self): return SlidingWindowIterator(self)
	def __len__(self): return len(self.timelist)
	def __getitem__(self, idx): return self.timelist[idx], self.datalist[idx]
	def uniq(self): return SlidingWindowUniqIterator(self)

	def append(self, newtime, newdata):
		assert not self.timelist or newtime >= self.start_
		if self.start_ is not None:
			self.total_time += newtime - self.start_
		if len(self.datalist) >= 2 and self.datalist[-2] == self.datalist[-1]:
			self.timelist[-1] = newtime
			self.datalist[-1] = newdata
		else:
			self.timelist.append(newtime)
			self.datalist.append(newdata)
		self.start_ = newtime
		while self.start_ - self.timelist[0] - self.size >= -1e-9:
			time = self.timelist.popleft()
			data = self.datalist.popleft()
			if self.cbfunc is not None:
				self.cbfunc(self.cbparam, time, data)

	def start(self):
		return self.start_

	def end(self):
		return self.start_ - min(self.size, self.total_time)

	def first(self):
		return self.start_

	def last(self):
		return self.timelist[0]

	def tail(self):
		assert self.timelist[0] - (self.start_ - self.size) > 0
		return self.timelist[0] - (self.start_ - self.size)
