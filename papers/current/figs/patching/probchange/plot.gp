set term postscript eps enhanced "Helvetica,30";
set encoding utf8;
unset title;
set output "probchange.eps";
set xlabel "Fraction (%) of the Intersection over Detection LCZD"
set ylabel "Probability of Change" offset 1.5,0;
#set xrange [0:1];
set yrange [0:1];
#set key bottom right
unset key;
set boxwidth 0.5;
set style fill solid;
plot 'prob.change.txt' using 1:3:xtic(2) with boxes
