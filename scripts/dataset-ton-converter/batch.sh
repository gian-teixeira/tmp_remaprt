#!/bin/sh
set -eu

DIR=/mnt/data/cunha/dataset-ton-dtrack-fastmap/data
OUT=/mnt/data/cunha/dataset-ton-dtrack-fastmap/converter/output

mkdir -p $OUT

for mon in $(ls $DIR) ; do
	[ -d $DIR/$mon ] || continue
	[ -d $DIR/$mon/dtrack ] || continue
	mkdir -p $OUT/$mon
	echo "$OUT/$mon"
	set +e
	python ./converter.py --data-dir $DIR/$mon --base-outdir $OUT/$mon
	if [ $? -ne 0 ] ; then
		rm -rf $OUT/$mon
	fi
	set -e
done
