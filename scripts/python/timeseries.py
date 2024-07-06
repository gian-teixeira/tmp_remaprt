from collections import deque

class TimeSeries(object):
	def __init__(self, windowsize, timeshift, timeseries, process):
		self.shift = timeshift
		self.ts2data = dict()
		ts2pastdata, times = self.__processdata(windowsize, timeseries, process)
		self.__shift(ts2pastdata, times)

	def __processdata(self, windowsize, timeseries, process):
		# pylint: disable-msg=R0201
		ts2tmpdata = dict()
		times = list()
		windowstart = 0
		windowidx = 0
		windowdata = deque()
		for time, data in timeseries:
			assert len(times) == 0 or time > times[-1]
			windowdata.append((time, data))
			times.append(time)
			while time - windowstart > windowsize:
				windowdata.popleft()
				windowidx += 1
				windowstart = times[windowidx]
			ts2tmpdata[time] = process(windowdata)
		return ts2tmpdata, times

	def __shift(self, ts2pastdata, times):
		idx = 0
		for time in times:
			while times[idx] < time + self.shift:
				idx += 1
				if idx >= len(times):
					return
			self.ts2data[time] = ts2pastdata[times[idx]]

	def __getitem__(self, time):
		return self.ts2data[time]

class LazyTimeSeries(object):
	def __init__(self, windowsize, timeshift, timeseries, cbadd, cbdel):
		self.winsz = windowsize
		self.shift = timeshift
		self.cbadd = cbadd
		self.cbdel = cbdel
		self.backidx = 0
		self.frontidx = 0
		self.timeseries = timeseries
		self.data = cbadd(timeseries[0][0], timeseries[0][1], None)

	def __getitem__(self, time):
		assert time >= self.timeseries[self.frontidx][0]
		while self.timeseries[self.frontidx+1] <= time + self.shift:
			tstime, tsdata = self.timeseries[self.frontidx+1]
			self.data = self.cbadd(tstime, tsdata, self.data)
			self.frontidx += 1
		while self.timeseries[self.frontidx][0] - self.winsz \
				> self.timeseries[self.backidx][0]:
			tstime, tsdata = self.timeseries[self.backidx]
			self.data = self.cbdel(tstime, tsdata, self.data)
			self.backidx += 1
		return self.data

