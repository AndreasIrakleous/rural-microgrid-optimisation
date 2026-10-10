import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# ============================================================
# 1. Load data
# ============================================================
load_path = "input/load_profiles/load_profiles_new.csv"
pv_path = "input/PV_profiles_files/case_study_pv.csv"

df_load = pd.read_csv(load_path)
df_pv = pd.read_csv(pv_path)

# ============================================================
# 2. Standardise time column
# ============================================================
if "time" not in df_load.columns:
    df_load["time"] = df_load.index

if "time" not in df_pv.columns:
    df_pv["time"] = df_pv.index

# ============================================================
# 3. Identify residential load column
# ============================================================
# Adjust here if your exact column name differs
if "residential" in df_load.columns:
    load_col = "residential"
elif "house" in df_load.columns:
    load_col = "house"
else:
    raise ValueError("Could not find residential load column in load profile file.")

# ============================================================
# 4. Identify PV generation column
# ============================================================
# Assumes the PV file has one generation column besides time
pv_columns = [col for col in df_pv.columns if col != "time"]

if len(pv_columns) == 1:
    pv_col = pv_columns[0]
else:
    # If there are multiple columns, select the first non-time column
    pv_col = pv_columns[0]

# ============================================================
# 5. Normalize by total daily energy
# ============================================================
df_plot = pd.DataFrame()
df_plot["time"] = df_load["time"]

load_total = df_load[load_col].sum()
pv_total = df_pv[pv_col].sum()

df_plot["Residential load"] = (
    df_load[load_col] / load_total if load_total > 0 else df_load[load_col]
)
df_plot["PV generation"] = (
    df_pv[pv_col] / pv_total if pv_total > 0 else df_pv[pv_col]
)

# ============================================================
# 6. Style settings
# ============================================================
plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial"],
    "font.size": 11,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10
})

# ============================================================
# 7. Figure size (full single column)
# ============================================================
fig_width = 6.7
fig_height = 3.5
fig, ax = plt.subplots(figsize=(fig_width, fig_height))

# ============================================================
# 8. Plot
# ============================================================
ax.plot(
    df_plot["time"],
    df_plot["Residential load"],
    linestyle='-',
    linewidth=2.2,
    alpha=1,
    marker='o',
    markersize=3,
    label="Residential load"
)

ax.plot(
    df_plot["time"],
    df_plot["PV generation"],
    linestyle='-',
    linewidth=2.2,
    alpha=1,
    marker='s',
    markersize=3,
    label="PV generation"
)

# ============================================================
# 9. Axes formatting
# ============================================================
ax.set_xlabel("Hour of day")
ax.set_ylabel("Normalized profile")

ax.set_xlim(0, 23)
ax.set_xticks(np.arange(0, 24, 1))
ax.tick_params(axis='x', labelrotation=45)

y_max = max(df_plot["Residential load"].max(), df_plot["PV generation"].max())
ax.set_ylim(0, y_max * 1.1)

# ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3)

# ============================================================
# 10. Legend
# ============================================================
ax.legend(frameon=True, loc="upper right")

# ============================================================
# 11. Final layout
# ============================================================
plt.tight_layout()
plt.savefig("output/plots/solar_load_profile.pdf", bbox_inches="tight")
plt.show()