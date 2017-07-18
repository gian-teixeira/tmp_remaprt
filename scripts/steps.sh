#!/bin/sh
set -eu

dataset=/home/cunha/data/12.2/fastmapping/
src2ip=/home/cunha/data/12.2/fastmapping/src2ip.txt
outputbase=/home/cunha/data/12.2/pathremap/


gzip_files () { # {{{
	find $outputbase -name '*.dst2path' -exec gzip {} \;
	find $outputbase -name '*.dst2change' -exec gzip {} \;
} # }}}


generate_change_database () { # {{{
	for monitor in $(ls $dataset) ; do
		fullpath=$dataset/$monitor
		test -d $fullpath || continue
		echo $fullpath

		outdir=$outputbase/changedb/$monitor
		mkdir -p $outdir
		prefix=$outdir/out
		if [ -s $prefix.dst2change.gz ] ; then
			echo "skipping $monitor"
		else
			mkchanges/mkchanges.py -m $fullpath -s $src2ip -o $prefix
		fi

		outdir=$outputbase/changedb.nobal/$monitor
		mkdir -p $outdir
		prefix=$outdir/out
		if [ -s $prefix.dst2change.gz ] ; then
			echo "skipping $monitor"
		else
			mkchanges/mkchanges.py -m $fullpath -s $src2ip -o $prefix \
					--ignore-balancers
		fi
	done
} # }}}


gzip_files
# generate_change_database
