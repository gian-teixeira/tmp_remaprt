set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "durationdetection.eps";
set xlabel "Total remapping time (minutes)"
set ylabel "Cumul. Fraction of Routing Events" offset 1.5,0;
set xrange [0:120];
set yrange [0:1];
#set key bottom right
unset key;
plot 'duration.detection_minutes.cdf' u 1:2 w steps lt 4 lw 5
