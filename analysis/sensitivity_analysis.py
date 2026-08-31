import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# 1. Data
# ============================================================

parameters = ["Solar", "Battery", "Diesel"]

E_load = 5376000  # 15 years

low = [483851.1, 487245.9, 427175.6]      
baseline = [488944.4, 488944.4, 488944.4] 
high = [522495.8, 491642, 544447.6]       

# Convert to COE
low = [cost / E_load for cost in low]
baseline = [cost / E_load for cost in baseline]
high = [cost / E_load for cost in high]

# ============================================================
# 2. Style (MATCH previous plots)
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
# 3. Figure (HALF COLUMN)
# ============================================================
fig_width = 6.7 * 0.4
fig_height = 6.2 * 0.4

fig, ax = plt.subplots(figsize=(fig_width, fig_height))

# ============================================================
# 4. Plot
# ============================================================
x = np.arange(len(parameters))
width = 0.25

ax.bar(x - width, low, width, label="-20%", alpha=0.9, edgecolor="black", linewidth=0.5)
ax.bar(x, baseline, width, label="Baseline", alpha=0.9, edgecolor="black", linewidth=0.5)
ax.bar(x + width, high, width, label="+20%", alpha=0.9, edgecolor="black", linewidth=0.5)

# ============================================================
# 5. Formatting
# ============================================================
ax.set_xlabel("Parameter")
ax.set_ylabel("Cost of energy ($/kWh)")

ax.set_xticks(x)
ax.set_xticklabels(parameters)

ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3, axis='y')

# Compact legend (consistent style)
ax.legend(
    frameon=True,
    loc="upper left",
    fontsize=8,
    borderpad=0.3,
    labelspacing=0.3,
    handletextpad=0.4
)

# Optional: tighten y-axis for clarity
y_min = min(low + baseline + high)
y_max = max(low + baseline + high)
ax.set_ylim(y_min * 0.98, y_max * 1.02)

# ============================================================
# 6. Final layout
# ============================================================
plt.tight_layout()
plt.savefig("output/plots/sensitivity_isolated.pdf", bbox_inches="tight")
plt.show()