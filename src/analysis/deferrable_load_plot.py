import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# 1. Data (from CSV)
# ============================================================
time = np.arange(24)

wp01_load = [
0.893019, 0.893019, 0.893019, 0.893019, 0.893019, 0.893019,
0.893019, 0.893019, 0.893019, 0.893019, 0.893019, 0.893019,
0.893019, 0.893019, 0.893019, 13.634135, 8.972976, 0.893019,
0.893019, 0.893019, 0.893019, 0.893019, 0.893019, 0.893019
]

discarded_energy = [
0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
0.0, 0.0, 0.0, 12.74112, 8.079957, 0.0,
0.0, 0.0, 0.0, 0.0, 0.0, 0.0
]

# ============================================================
# 2. Style settings (consistent across report)
# ============================================================
plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8
})

# ============================================================
# 3. Figure (full column)
# ============================================================
fig_width = 6.7
fig_height = 3.5
fig, ax = plt.subplots(figsize=(fig_width, fig_height))

# ============================================================
# 4. Plot
# ============================================================
ax.plot(
    time,
    wp01_load,
    linestyle='-',
    linewidth=2.2,
    alpha=0.85,
    marker='o',
    markersize=3,
    label="Deferrable load"
)

ax.plot(
    time,
    discarded_energy,
    linestyle='-',
    linewidth=2.2,
    alpha=0.85,
    marker='s',
    markersize=3,
    label="Surplus energy"
)

# ============================================================
# 5. Axes formatting
# ============================================================
ax.set_xlabel("Hour of day")
ax.set_ylabel("Energy (kWh)")

ax.set_xlim(0, 23)
ax.set_xticks(np.arange(0, 24, 1))
ax.tick_params(axis='x', labelrotation=45)

y_max = max(max(wp01_load), max(discarded_energy))
ax.set_ylim(0, y_max * 1.1)

ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3)

# ============================================================
# 6. Legend (compact)
# ============================================================
ax.legend(
    loc="upper right",
    frameon=True,
    fontsize=8,
    borderpad=0.3,
    labelspacing=0.3,
    handletextpad=0.4
)

# ============================================================
# 7. Save and show
# ============================================================
plt.tight_layout()
plt.savefig("output/plots/deferrable_load.pdf", bbox_inches="tight")
plt.show()