from config import process_config
from utils import graph,probe 
from sys import argv

infos = dict()
infos["features_dir"] = "/mnt/data2/elverton/TopoMap/"+\
    "experiments/Graphs/results_features_overlaps/ids_cur" 
infos["suffix"] = argv[1]

#probe.probe_prob_change_detection(infos)
#probe.probe_prob_change_per_detection(infos)
#probe.probe_new_life(infos)
#probe.probe_prob_change_detection(infos)
#probe.probe_prob_change_size_detection(infos)
#probe.probe_view(infos)
#probe.probe_new_life_buckets(infos)
#probe.probe_new_life_adaptative(infos)
probe.probe_per_cps(infos)
