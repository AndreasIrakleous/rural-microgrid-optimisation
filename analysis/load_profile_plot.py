import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator
import numpy as np

# ============================================================
# 1. Load data
# ============================================================
csv_path = "input/load_profiles/load_profiles_new.csv"
df = pd.read_csv(csv_path)

# If there is no explicit time column, use the row index
if "time" not in df.columns:
    df["time"] = df.index

# ============================================================
# 2. Normalize load columns (by total daily energy)
# ============================================================
load_columns = [
    col for col in df.columns 
    if col != "time" and col.lower() != "water_pump"
]

df_norm = df.copy()

for col in load_columns:
    total_energy = df[col].sum()
    if total_energy > 0:
        df_norm[col] = df[col] / total_energy
    else:
        df_norm[col] = df[col]
# ============================================================
# 3. Style settings
# ============================================================
plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial"],
    "font.size": 11,
    "axes.labelsize":11,
    "axes.titlesize":11,
    "legend.fontsize": 11,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
})

# ============================================================
# 4. Figure size (half column)
# ============================================================
fig_width = 6.7
fig_height = 3.5   # slightly increased height for readability
fig, ax = plt.subplots(figsize=(fig_width, fig_height))

## ============================================================
# 5. Plot normalized load profiles (ALL SOLID LINES)
# ============================================================
markers = ['o', 's', '^', 'D', 'v']

for i, col in enumerate(load_columns):
    ax.plot(
        df_norm["time"],
        df_norm[col],
        linestyle='-',                 # <-- all solid lines
        marker=markers[i % len(markers)],
        markersize=1,
        linewidth=2.2,          # <-- thicker lines
        alpha=1,             # <-- slight transparency
        label=col.replace("_", " ").capitalize()
    )

# ============================================================
# 6. Axes formatting
# ============================================================
ax.set_xlabel("Hour of day")
ax.set_ylabel("Normalized load")

ax.set_xlim(0, 23)
ax.set_xticks(np.arange(0, 24, 1))

ax.tick_params(axis='x', labelrotation=45)
# ax.grid(False, linestyle='--', linewidth=0.5, alpha=0.3)

# ============================================================
# 7. Legend
# ============================================================
ax.legend(frameon=True, loc="upper left")


# ============================================================
# 8. Final layout
# ============================================================
plt.tight_layout()
plt.savefig("output/plots/primary_load_profiles.pdf", bbox_inches="tight")
plt.show()