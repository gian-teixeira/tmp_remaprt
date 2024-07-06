import math
from collections import defaultdict
from saikko.slidingwindow import SlidingWindow
from saikko.data import PrevalencePeriod


class PathActivityCalculator(object): # {{{
	def __init__(self, winsz): # {{{
		self.winsz = winsz
		self.alias2accum = defaultdict(lambda: 0)
		self.win = SlidingWindow(winsz, None, None)
		self.last_alias_removed = -1
		self.removed_until_win_last = False
		self.watch_data = list()
		# self.most_act = None
		# self.top_accum = None
		# self.dom_change_cb = None
	# }}}

	def get_time_to_prevalence(self, prevlist): # {{{
		if not prevlist: return list()
		alias = self.win[-1][1]
		result = list()
		now = self.win.end()
		aliasiter = self.win.uniq()
		rmalias = self.last_alias_removed
		rminterval = self.win.tail()
		nexttime, nextalias = aliasiter.next()
		assert nexttime - now == rminterval
		prevlist = list(prevlist)
		prev = self[alias]
		togo = int(math.ceil((prevlist[0] - prev) * self.winsz))
		prev += float(togo)/self.winsz
		del prevlist[0]
		while togo is not None:
			while rminterval == 0 or rmalias == alias:
				now += rminterval
				rmalias = nextalias
				nexttime, nextalias = aliasiter.next()
				rminterval = nexttime - now
			while rminterval > 0:
				if rminterval >= togo:
					now += togo
					rminterval -= togo
					if not prevlist:
						togo = None
						result.append(now - self.win.end())
						break
					else:
						togo = int(math.ceil((prevlist[0] - prev) * self.winsz))
						prev += float(togo)/self.winsz
						del prevlist[0]
					result.append(now - self.win.end())
				else:
					now += rminterval
					togo -= rminterval
					rminterval = 0
			assert togo is None or now == nexttime
		return result
	# }}}

	def __getitem__(self, alias): # {{{
		return float(self.alias2accum[alias])/self.winsz
	# }}}

	def most_active(self): # {{{
		data = [(accum, alias) for alias, accum in self.alias2accum.items()]
		data.sort()
		return data[-1][1]
	# }}}

	def update(self, time, alias=None): # {{{
		assert self.win.start() is None or \
                        time >= self.win.start() - 1e-6
		self._bootstrap_window(time)
		alias = self.win[-1][1] if alias is None else alias
		inc_alias = self.win[-1][1]
		dec_alias = self.last_alias_removed
		while self.win.start() < time:
			to_go = time - self.win.start()
			step = self.win.tail()
			update_dec = True
			if to_go < step:
				step = to_go
				update_dec = False
			self._check_watch(inc_alias, dec_alias, step)
			# self._check_most_act(inc_alias, dec_alias, step)
			self.alias2accum[inc_alias] += step
			self.alias2accum[dec_alias] -= step
			if update_dec:
				dec_alias = self.win[0][1]
				self.last_alias_removed = self.win[0][1]
			self.win.append(self.win.start() + step, inc_alias)
		assert abs(time - self.win.start()) < 1e-6
		self.win.datalist[-1] = alias
		self.watch_data = list()
	# }}}

	def watch(self, alias, threshold, cb): # {{{
		self.watch_data.append((alias, threshold, cb))
	# }}}

	# def watch_dom_change(self, cb): # {{{
	#	self.dom_change_cb = cb
	# }}}

	def _bootstrap_window(self, time): # {{{
		if len(self.win) == 0:
			self.win.append(time - self.winsz, -1)
	# }}}

	def _check_watch(self, inc_alias, dec_alias, step): # {{{
		if inc_alias == dec_alias:
			return
		checks = list(self.watch_data)
		for i, (alias, threshold, cb) in enumerate(checks):
			accum_trigger = threshold * self.winsz
			if inc_alias == alias:
				accum = self.alias2accum[alias]
				assert accum <= accum_trigger
				if accum + step >= accum_trigger:
					frac_used = float(accum_trigger - accum) / step
					cb(self.win.start() + step * frac_used)
					self.watch_data[i] = None
			elif dec_alias == alias:
				accum = self.alias2accum[alias]
				assert accum >= accum_trigger
				if accum - step <= accum_trigger:
					frac_used = float(accum - accum_trigger) / step
					cb(self.win.start() + step * frac_used)
					self.watch_data[i] = None
		while None in self.watch_data:
			self.watch_data.remove(None)
	# }}}
# }}}


class DomPeriodBuilder(object): # {{{
	def __init__(self, threshold, winsz, period_end_cb): # {{{
		self.period_end_cb = period_end_cb
		self.winsz = winsz
		self.threshold = threshold
		self.alias = None
		self.last_update = None
		self.last_alias = -1
		self.last_duration = None
		self.accum = 0
		self.period_start = 0
		self.prevman = PathActivityCalculator(winsz)
	# }}}

	def update(self, now, alias, duration): # {{{
		if self.alias is not None:
			assert self.prevman[self.alias] >= self.threshold
			if self.last_alias != self.alias:
				self.prevman.watch(self.alias, self.threshold, self.end_period)
				self.prevman.watch(self.last_alias, self.threshold, self.start_period)
		else:
			assert self.prevman[self.last_alias] <= self.threshold
			self.prevman.watch(self.last_alias, self.threshold,
					self.start_period)
		self.prevman.update(now, alias)
		if self.alias is None:
			assert self.prevman[self.last_alias] <= self.threshold
		else:
			assert self.prevman[self.alias] >= self.threshold
			if self.last_alias == self.alias:
				self.accum += (now - self.last_update)
		self.last_update = now
		self.last_alias = alias
		self.last_duration = duration
	# }}}

	def start_period(self, time): # {{{
		assert self.alias is None
		self.alias = self.last_alias
		self.period_start = time
		self.last_update = time
		self.accum = 0
	# }}}

	def end_period(self, time): # {{{
		assert self.alias is not None
		assert self.last_alias != self.alias
		assert time >= self.period_start
		period_dur = time - self.period_start
		assert 0 <= self.accum <= period_dur
		period_dur = max(1, period_dur)
		act = float(self.accum)/period_dur
		assert act < 1 or abs(time - self.last_update) < 1e-6
		period = PrevalencePeriod(self.period_start, time, self.alias, act)
		self.period_end_cb(period)
		self.alias = None
	# }}}

	def close(self): # {{{
		self.update(self.last_update + self.last_duration, self.last_alias, 0)
		if self.alias is not None:
			self.last_alias = -1 # avoid assertion in end_period()
			self.end_period(self.last_update)
	# }}}
# }}}
