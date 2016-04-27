set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "prob_cps.eps";
set xlabel "Prob Change"
set ylabel "Cumulative Frac. of CPS Groups" offset 1.5,0;
set xrange [0:1];
set yrange [0:1];
#set key bottom right
unset key;
plot 'cps.cdf' u 1:2 w steps lt 4 lw 5
