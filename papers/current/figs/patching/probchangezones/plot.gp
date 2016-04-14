set term postscript eps enhanced "Helvetica,25";
set encoding utf8;
unset title;
set output "zones_changes_overlaps.eps";
set xlabel "Fraction (%) of the Overlap with LCZD"
set ylabel "Cumulative Fraction of Overlaps" offset 1.5,0;
#set xrange [0:1];
set yrange [0:1];
set boxwidth 0.5;
set style fill solid;
set key top left
plot 'zones_changes.perc' using 1:4:xtic(2) t 'Overlaps with Changes' with steps lw 5 lt 4, \
    'zones_overlap.perc' using 1:4:xtic(2) t 'All Overlaps' with steps lw 5 lt 3

set output "zones_changes_per_intersect.eps";
set xlabel "Fraction of Paths that Overlap the Detection"
set ylabel "Cumul. Frac. of Overlaps with Changes" offset 1.5,0;
#set xrange [0:1];
set yrange [0:1];
set boxwidth 0.5;
set style fill solid;
set key top left
plot 'changes.perc' u 1:4 notitle w l lw 5 lt 1,\
    'changes.perc' every ::300::300 u 1:4 t '1-20' w lp lw 5 lt 1 pt 5 ps 3, \
    'changes.perc' using 1:6 notitle with steps lw 5 lt 3,\
    'changes.perc' every ::300::300 u 1:6 t '21-40' w lp lw 5 lt 3 pt 6 ps 3, \
    'changes.perc' using 1:8 notitle with steps lw 5 lt 5,\
    'changes.perc' every ::300::300 u 1:8 t '41-60' w lp lw 5 lt 5 pt 7 ps 3, \
    'changes.perc' using 1:10 notitle with steps lw 5 lt 7,\
    'changes.perc' every ::300::300 u 1:10 t '61-80' w lp lw 5 lt 7 pt 8 ps 3, \
    'changes.perc' using 1:12 notitle with steps lw 5 lt 9,\
    'changes.perc' every ::300::300 u 1:12 t '81-100' w lp lw 5 lt 9 pt 9 ps 3, \


set output "zones_overlaps_per_intersect.eps";
set xlabel "Fraction of Paths that Overlap the Detection"
set ylabel "Cumul. Frac. of All Overlaps" offset 1.5,0;
#set xrange [0:1];
set yrange [0:1];
set boxwidth 0.5;
set style fill solid;
set key top left
plot 'overlaps.perc' u 1:4 notitle w l lw 5 lt 1,\
    'overlaps.perc' every ::300::300 u 1:4 t '1-20' w lp lw 5 lt 1 pt 5 ps 3, \
    'overlaps.perc' using 1:6 notitle with steps lw 5 lt 3,\
    'overlaps.perc' every ::300::300 u 1:6 t '21-40' w lp lw 5 lt 3 pt 6 ps 3, \
    'overlaps.perc' using 1:8 notitle with steps lw 5 lt 5,\
    'overlaps.perc' every ::300::300 u 1:8 t '41-60' w lp lw 5 lt 5 pt 7 ps 3, \
    'overlaps.perc' using 1:10 notitle with steps lw 5 lt 7,\
    'overlaps.perc' every ::300::300 u 1:10 t '61-80' w lp lw 5 lt 7 pt 8 ps 3, \
    'overlaps.perc' using 1:12 notitle with steps lw 5 lt 9,\
    'overlaps.perc' every ::300::300 u 1:12 t '81-100' w lp lw 5 lt 9 pt 9 ps 3, \


