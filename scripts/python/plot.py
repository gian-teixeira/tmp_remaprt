import subprocess

def linespoints(files, xlabel, ylabel, outfile, extra=''): # {{{
	cmds = 'set term postscript eps enhanced "Helvetica, 28" color;'
	cmds += 'set output "%s";' % outfile
	cmds += 'set xlabel "%s";' % xlabel
	cmds += 'set ylabel "%s";' % ylabel
	cmds += extra
	cmds += 'plot '
	plots = list()
	for fn, label in files:
		s = '\'%s\' t "%s" w lp lw 3 ps 2' % (fn, label)
		plots.append(s)
	cmds += ','.join(plots)
	cmds += ';'
	cmds += 'quit;\n'
	pipe = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
	pipe.communicate(cmds)
# }}}

def lines(files, xlabel, ylabel, outfile, extra=''): # {{{
	cmds = 'set term postscript eps enhanced "Helvetica, 28" color;'
	cmds += 'set output "%s";' % outfile
	cmds += 'set xlabel "%s";' % xlabel
	cmds += 'set ylabel "%s";' % ylabel
	cmds += extra
	cmds += 'plot '
	plots = list()
	for fn, label in files:
		s = '\'%s\' t "%s" w l lw 3' % (fn, label)
		plots.append(s)
	cmds += ','.join(plots)
	cmds += ';'
	cmds += 'quit;\n'
	pipe = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
	pipe.communicate(cmds)
# }}}

def points(files, xlabel, ylabel, outfile, extra='', **kwargs): # {{{
	cmds = 'set term postscript eps enhanced "Helvetica, 28" color;'
	cmds += 'set output "%s";' % outfile
	cmds += 'set xlabel "%s";' % xlabel
	cmds += 'set ylabel "%s";' % ylabel
	cmds += 'set yrange [0:1];'
	cmds += extra
	cmds += 'plot '
	plots = list()
	for fn, label in files:
		using = kwargs.get('using', '1:2')
		s = '\'%s\' u %s t "%s" w points ps 1.5' % (fn, using, label)
		plots.append(s)
	cmds += ','.join(plots)
	cmds += ';'
	cmds += 'quit;\n'
	pipe = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
	pipe.communicate(cmds)
# }}}

def density(fn, xlabel, ylabel, outfile, extra=''): # {{{
	cmds = 'set term postscript eps enhanced "Helvetica, 28" color;'
	cmds += 'set output "%s";' % outfile
	cmds += 'set xlabel "%s";' % xlabel
	cmds += 'set ylabel "%s";' % ylabel
	cmds += 'set cbrange [0:1];'
	cmds += 'set pm3d map corners2color c1;'
	# set palette defined ( 0 "white" , 0.1 "gray80" , 10 "black" );
	cmds += extra
	cmds += 'splot \'%s\' notitle;' % fn
	cmds += 'quit;\n'
	pipe = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
	pipe.communicate(cmds)
# }}}
