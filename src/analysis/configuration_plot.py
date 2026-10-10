import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib.lines as mlines
from matplotlib.ticker import FormatStrFormatter
from matplotlib import ticker
import networkx as nx
from itertools import combinations

# ============================================================
# 1. Load data
# ============================================================
csv_path = "input/configurations/small_community_new.csv"
df = pd.read_csv(csv_path)

# Standardise column names if needed
column_map = {
    "lat": "latitude",
    "lon": "longitude",
    "type": "load_profile_type"
}
df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

# If no node_id exists, create one
if "node_id" not in df.columns:
    df["node_id"] = np.arange(len(df))

# ============================================================
# 2. Build graph and compute MST
# ============================================================
G = nx.Graph()

# Add nodes with positions
for _, row in df.iterrows():
    node = row["node_id"]
    lon = row["longitude"]
    lat = row["latitude"]
    G.add_node(
        node,
        pos=(lon, lat),
        load_profile_type=row["load_profile_type"]
    )

# Add all pairwise edges weighted by Euclidean distance
for i, j in combinations(df.index, 2):
    node_i = df.loc[i, "node_id"]
    node_j = df.loc[j, "node_id"]

    x1, y1 = df.loc[i, "longitude"], df.loc[i, "latitude"]
    x2, y2 = df.loc[j, "longitude"], df.loc[j, "latitude"]

    dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    G.add_edge(node_i, node_j, weight=dist)

# Minimum spanning tree
mst = nx.minimum_spanning_tree(G, weight="weight")

# ============================================================
# 3. Style settings (consistent across report)
# ============================================================
plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial"],
    "font.size": 11,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10
})

marker_map = {
    "hospital": "P",
    "health_centre": "P",
    "school": "*",
    "house": "o",
    "residential": "o",
    "commercial": "s",
    "water_pump": "v"
}

# ============================================================
# 4. Figure size (half column)
# ============================================================
fig_width = 3.35
fig_height = 3.1
fig, ax = plt.subplots(figsize=(fig_width, fig_height))

# ============================================================
# 5. Plot MST edges
# ============================================================
pos = {row["node_id"]: (row["longitude"], row["latitude"]) for _, row in df.iterrows()}

for u, v in mst.edges():
    x_coords = [pos[u][0], pos[v][0]]
    y_coords = [pos[u][1], pos[v][1]]
    ax.plot(
        x_coords,
        y_coords,
        color="#D62728",
        linewidth=1.4,
        alpha=0.9,
        zorder=1
    )

# ============================================================
# 6. Plot nodes
# ============================================================
for b_type in df["load_profile_type"].dropna().unique():
    subset = df[df["load_profile_type"] == b_type]
    ax.scatter(
        subset["longitude"],
        subset["latitude"],
        color="#4C72B0",
        s=40,
        marker=marker_map.get(b_type, "o"),
        edgecolor="black",
        linewidth=0.5,
        zorder=3
    )

# ============================================================
# 7. Building type legend
# ============================================================
type_handles = []
present_types = sorted(df["load_profile_type"].dropna().unique())

for b_type in present_types:
    handle = mlines.Line2D(
        [], [],
        linestyle="None",
        marker=marker_map.get(b_type, "o"),
        markerfacecolor="#4C72B0",
        markeredgecolor="black",
        markeredgewidth=0.5,
        markersize=6,
        label=b_type.replace("_", " ").capitalize()
    )
    type_handles.append(handle)

ax.legend(
    handles=type_handles,
    title="Building type",
    loc="upper right",
    frameon=True,
    fontsize=8,          # smaller text
    title_fontsize=9,    # slightly larger title
    borderpad=0.3,       # padding inside box
    labelspacing=0.3,    # spacing between entries
    handletextpad=0.4,   # space between marker and text
    borderaxespad=0.3    # space from axes edge
)

# ============================================================
# 8. Axes formatting
# ============================================================
x_pad = (df["longitude"].max() - df["longitude"].min()) * 0.05
y_pad = (df["latitude"].max() - df["latitude"].min()) * 0.05

ax.set_xlim(df["longitude"].min() - x_pad, df["longitude"].max() + x_pad)
ax.set_ylim(df["latitude"].min() - y_pad, df["latitude"].max() + y_pad)

ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=4))
ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4))
ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
ax.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))

ax.set_xlabel("Longitude (°)")
ax.set_ylabel("Latitude (°)")

ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3, zorder=0)
plt.xticks(rotation=15)

# ============================================================
# 9. Save and show
# ============================================================
plt.tight_layout()
plt.savefig("output/plots/fictitious_community_mst.pdf", bbox_inches="tight")
plt.show()