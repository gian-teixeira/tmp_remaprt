set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "overlapcoverage_only_lczd.eps";
set xlabel "% of CPS that detect change"
set ylabel "Cumul. Frac. of Overlapping Paths" offset 1.5,0;
set xrange [0:1];
set yrange [0:1];
#set key bottom right
unset key;
plot 'overlap.coverage.only.lczd.cdf' u 1:2 w steps lt 4 lw 5
