set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "cpssize.eps";
set xlabel "CPS Size"
set ylabel "Cumul. Fraction of Routing Events" offset 1.5,0;
set xrange [0:15];
set yrange [0:1];
set key bottom right
#unset key;
plot 'cps_bigger_0.cdf'  u 1:2 t 'OCS detected by CPS ' w steps lt 4 lw 5,\
    'cps_not_cover_has_lczd.cdf'  u 1:2 t 'OCS not detected by CPS ' w steps lt 1 lw 5,\
    'cps_not_cover_not_lczd.cdf'  u 1:2 t 'OCS is empty' w steps lt 5 lw 5
