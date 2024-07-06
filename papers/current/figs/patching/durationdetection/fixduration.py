from collections import defaultdict
f = open("duration.detection.txt","r")

dots_qtt = defaultdict(lambda: 0)
total = 0
for l in f:
    l = l.strip()
    l_float=float(l)
    
    if(l_float<10000):
        total+=1
    if(l_float>7200):
        continue
    if(l == "0.0"):
        l_float = 300
    if(l == "0"):
        l_float = 0
    minutes = l_float/60

    dots_qtt[minutes] += 1

keys = dots_qtt.keys()
keys.sort()
o1 = open("duration.detection_minutes.txt","w")
for key in keys:
    print >> o1, key, dots_qtt[key]/float(total)
