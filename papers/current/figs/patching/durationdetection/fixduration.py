from collections import defaultdict
f = open("duration.detection.txt","r")

dots_qtt = defaultdict(lambda: 0)
total = 0
for l in f:
    l=float(l.strip())
    if(l>10000):
        continue
    dots_qtt[l] += 1
    total += 1

keys = dots_qtt.keys()
keys.sort()
o1 = open("duration.detection_2.txt","w")
for key in keys:
    print >> o1, key, dots_qtt[key]/float(total)
