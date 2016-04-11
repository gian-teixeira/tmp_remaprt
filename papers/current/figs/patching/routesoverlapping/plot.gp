set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "routesoverlapping.eps";
set xlabel "Fraction of Paths that Overlap the Detection"
set ylabel "Cumul. Fraction of Routing Events" offset 1.5,0;
set xrange [0:1];
set yrange [0:1];
#set key bottom right
unset key;
plot 'routes.overlapping.cdf' u 1:2 w steps lt 4 lw 5
