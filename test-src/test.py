import subprocess
from sys import argv
from os import listdir

def list2path(ids):
    id2ip = lambda id : f'{id}.{id}.{id}.{id}'
    ids = list(map(id2ip, ids))
    data = ':0:0.00,0.00,0.00,0.00:|'.join(ids+[''])
    return data[:-1]

tests = [x for x in listdir(".") if(x.find(".in") != -1 and x.find("log") == -1)]
tests.sort()

for f in tests:
    test_file = open(f,"r")
    old_path = list2path([x for x in test_file.readline().strip().split(",")])
    new_path = list2path([x for x in test_file.readline().strip().split(",")])
    right_path = list2path([x for x in test_file.readline().strip().split(",")])
    dst = test_file.readline().strip()
    dstip = dst+"."+dst+"."+dst+"."+dst
    ttl = test_file.readline().strip()

    command = ["../src/remaproute", "-i", "eno8303", "-d", dstip, "-o", old_path,\
            "-n", new_path, "-t", ttl, "-x", "10", "-l", "log."+str(f)]


    print("test: ", f)
    with subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8') as process:
        outs, errs = process.communicate(timeout=1)
        remaprt_path = outs.strip().split(" ")[-4]
        if(right_path == remaprt_path):
            print("pass")
        else:
            print(remaprt_path)
            print(right_path)
    
