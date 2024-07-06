import bisect

def dcreate(dbins):
	return _dcreate(dbins, 0)

def dadd(dmatrix, dbins, coords, value):
	assert len(coords) == len(dbins)
	for d, x in enumerate(coords):
		i = bisect.bisect(dbins[d], x)
		dmatrix = dmatrix[i-1]
	dmatrix.append((value, coords))

def dlist(dmatrix, dbins, dranges):
	retval = list()
	_dlist(dmatrix, dbins, dranges, 0, retval)
	return retval

def _dlist(dmatrix, dbins, dranges, d, retval): # {{{
	if d == len(dbins):
		# for v, coords in dmatrix:
		# for d, minmax in enumerate(dranges):
		# if minmax[0] <= coords[d] <= minmax[1]: retval.append((v, coords))
		retval.extend(dmatrix)
	else:
		rmin, rmax = dranges[d]
		imin = bisect.bisect(dbins[d], rmin)
		imax = bisect.bisect(dbins[d], rmax)
		for i in range(imin, imax+1):
			_dlist(dmatrix[i-1], dbins, dranges, d+1, retval)
# }}}

def _dcreate(dbins, d): # {{{
	dmatrix = list()
	for _ in dbins[d]:
		if d == len(dbins)-1:
			dmatrix.append(list())
		else:
			dmatrix.append(_dcreate(dbins, d+1))
	return dmatrix
# }}}


