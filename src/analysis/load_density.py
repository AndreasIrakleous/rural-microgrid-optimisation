# Find the distance of MST for small community

import sys
import os
from matplotlib.pylab import load

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from pathlib import Path
import pandas as pd
from src.main import *
from src.dispatch_strategy.power_flow_edgeless import *
import optuna
from concurrent.futures import ProcessPoolExecutor, as_completed 
import time
import plotly.express as px

#small community configuration
config = Configuration()
config.import_nodes_from_csv("input/configurations/small_community_new.csv")
config.minimum_spanning_tree()
total_length = config.total_edge_distance()
print("Total length of MST: ", total_length)