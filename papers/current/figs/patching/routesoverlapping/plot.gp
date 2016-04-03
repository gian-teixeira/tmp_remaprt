set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "routesoverlapping.eps";
set xlabel "Fraction of paths that overlap the detection"
set ylabel "Cumulative Fraction of Detections" offset 1.5,0;
set xrange [0:1];
set yrange [0:1];
#set key bottom right
unset key;
plot 'routes.overlapping.cdf' u 1:2 w steps lt 4 lw 5
