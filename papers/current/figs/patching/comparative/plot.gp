set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "change_detect.eps";
set xlabel "Budget"
set ylabel "Cumul. Frac. of Changes Detected" offset 1.5,0;
set xrange [0:50211578];
set yrange [0:1];
set key bottom right
#unset key;
plot 'comparative_oracle_abs.txt' u 3:2 t 'Algorithm 1' w lines lt 4 lw 5,\
    'comparative_oracle_abs.txt' u 5:4 t 'Algorithm Sequential' w lines lt 5 lw 5,\
    'comparative_oracle_abs.txt' u 6:7 t 'Oracle' w lines lt 6 lw 5


