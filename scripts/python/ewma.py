class EWMA(object):
	def __init__(self, alpha):
		self.alpha = alpha
		self.value = 0

	def __iadd__(self, value):
		self.value = self.alpha * value + (1 - self.alpha) * self.value
		return self

	def __add__(self, value):
		ewma = EWMA(self.alpha)
		ewma.value = self.value
		ewma += value
		return ewma

	def add(self, value):
		self.value = self.alpha * value + (1 - self.alpha) * self.value

