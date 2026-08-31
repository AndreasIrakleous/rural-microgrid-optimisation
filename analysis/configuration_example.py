"""
Date: 28-01-2026
Try the optimisation code on two houses only

"""

from main import *
from dispatch_strategy.power_flow_edgeless import *
import matplotlib.pyplot as plt
from matplotlib import rc, rcParams
import networkx as nx
import seaborn as sns
import pandas as pd
from matplotlib.ticker import FormatStrFormatter
# from optimisation import *

#Create configuration of a small community
config = Configuration() 
config.import_nodes_from_csv("input/configurations/Ethiopia_case_study.csv")

data = []
for node, attr in config.nodes(data=True):
    lat, lon = attr["coordinates"]
    lon = lon - 37 
    lat = lat - 5.85
    data.append({
        "longitude": lon,
        "latitude": lat,
        "Village Name": attr["profile_type"],
        "scale_kwh_yr": attr["profile_scale_kwh_yr"]
    })

df = pd.DataFrame(data)

#Plot the configuration
w = 13.3
h = 7.5
plt.figure(figsize=(w*0.5,h*.75))
ax = sns.scatterplot(
    data=df,
    x="longitude",
    y="latitude",
    hue="Village Name",
    size="scale_kwh_yr",
    sizes=(60, 400)
)

handles, labels = ax.get_legend_handles_labels()

# Keep only the profile type entries
n = df["Village Name"].nunique() + 1
ax.legend(handles[:n], labels[:n], loc="upper left")

#To adjust the ticks on the axes
# ax.ticklabel_format(useOffset=False)
ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
ax.margins(0.2)

plt.xlabel("Longitude (+37°)")
plt.ylabel("Latitude (+5.85°)")
plt.title("Ethiopia Case Study Map")

# Plotting context
rc("font", **{"family": "sans-serif", "sans-serif": ["Arial"], "size": 7})
sns.set_context(
    "talk",
    rc={
        "font.size": 16,
        "axes.titlesize": 18,
        "axes.labelsize": 24,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14
    }
)
sns.set_style("ticks")

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
rcParams["pdf.fonttype"] = 42
rcParams["ps.fonttype"] = 42

plt.rcParams["font.size"] = 24

#Show the plot
plt.tight_layout()
plt.savefig("output/Ethiopia_configuration", dpi=300, bbox_inches="tight")

# # x axis: longitude, y axis: latitude
# x = [config.nodes[node]['coordinates'][1] for node in config.nodes]
# y = [config.nodes[node]['coordinates'][0] for node in config.nodes]
# # value of the scale for every node
# scale = [config.nodes[node]['load_profile_scale_kwh_yr'] for node in config.nodes]
# # house profiles
# profile = [config.nodes[node]['load_profile_type'] for node in config.nodes]
# # different point shape for different profiles


