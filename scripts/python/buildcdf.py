import bisect

def from_array(array):
	cdfdata = list()
	last = 0.0
	sortedarray = sorted(array)
	arraylen = len(array)
	for i, data in enumerate(sortedarray):
		if data != last:
			cdfdata.append((last, float(i)/arraylen))
			last = data
	cdfdata.append((last, 1.0))
	return cdfdata

def from_array_binned(array, bins):
	sortedarray = sorted(array)
	sortedbins = sorted(bins)
	sortedbins.append(1e1000)
	cdfdata = [0.0] * len(sortedbins)
	for data in sortedarray:
		idx = bisect.bisect(sortedbins, data)
		cdfdata[idx] += 1.0/len(sortedarray)
	for i, binxpos in enumerate(sortedbins):
		if i == 0:
			cdfdata[0] = (sortedarray[0], cdfdata[0])
		else:
			cdfdata[i] = (binxpos, cdfdata[i-1][1] + cdfdata[i])
	assert abs(cdfdata[-2][1] - 1) < 1e-6 or max(array) > max(bins)
	if sortedarray[-1] > sortedbins[-2]:
		assert cdfdata[-2][1] < 1
		cdfdata[-1] = (sortedarray[-1], cdfdata[-1][1])
	else:
		assert abs(cdfdata[-2][1] - 1) < 1e-6
		del cdfdata[-1]
	return cdfdata

def dump_to_file(cdfdata, filename):
	outfile = open(filename, 'w')
	for x, y in cdfdata:
		outfile.write('%s %s\n' % (x, y))
	outfile.close()

def from_array_to_file(array, filename):
	cdf = from_array(array)
	dump_to_file(cdf, filename)

