 python fixduration.py 
awk '{s+=$2; print $1,s}' duration.detection_minutes.txt > duration.detection_minutes.cdf
gnuplot plot.gp 
