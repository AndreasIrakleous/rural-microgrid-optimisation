import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from matplotlib import ticker

# --- 1. Data Preparation (Same as before) ---
years = [2001, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023]
data = {
    "Year": years * 3,
    "Access Rate (%)": [
        79, 80, 81, 82, 83, 84.5, 86, 87, 89, 90, 91.5, 91.8,
        63, 66, 69.5, 72.5, 76, 80, 83.5, 88, 92.5, 95.5, 98.8, 98.8,
        26, 29.5, 29, 32.5, 32.8, 36, 37.8, 39, 43.5, 47, 50.5, 53
    ],
    "Region": (["Global"] * 12) + (["Central Asia and Southern Asia"] * 12) + (["Sub-Saharan Africa"] * 12)
}
df = pd.DataFrame(data)

# --- 2. Style Settings ---
sns.set_style("ticks")
sns.set_context("talk", rc={"font.size": 26, "axes.labelsize": 26,"xtick.labelsize": 20, "ytick.labelsize": 20})

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial"]
})

colors = ["#7030A0", "#92D050", "#C00000"] 

# --- 3. Create Plot ---
# Width is ~6.6 (half of 13.3), Height is 7.5 (full slide height)
fig, ax = plt.subplots(figsize=(6.6, 7.5))

sns.lineplot(
    data=df, 
    x="Year", 
    y="Access Rate (%)", 
    hue="Region", 
    palette=colors,
    marker="o", 
    markersize=8, 
    linewidth=2.5, 
    ax=ax
)

# --- 4. Custom Formatting ---
ax.set_ylim(20, 105)
ax.set_ylabel("Total electricity access rate\n(% of total population)", labelpad=15)
ax.set_xlabel("Year", labelpad=15)
#make x-axis ticks with a visible line

ax.xaxis.set_major_locator(ticker.FixedLocator([2001, 2005, 2009, 2013, 2017, 2021]))
ax.yaxis.set_major_locator(ticker.MultipleLocator(20))


# Ensure only the bottom spine is visible
sns.despine(left=True, bottom=False) 

# Enable tick marks for the x-axis only
ax.tick_params(axis='x', which='major', length=6, width=1.5, colors='black')
# Keep y-axis ticks hidden (since you have grid lines)
ax.tick_params(axis='y', length=0)

ax.grid(axis='y', linestyle='-', alpha=0.3)
# --- 6. The "Un-squish" Legend Fix ---
# This moves the legend ABOVE the plot area so the box can expand
ax.legend(
    title="", 
    loc='lower center', 
    bbox_to_anchor=(0.5, 1.02), # 1.02 puts it just above the top axis
    ncol=1,                     # Stacked vertically looks better for half-slide
    frameon=False, 
    fontsize=20,
    handletextpad=0.5
)

# Adjust layout to make sure the floating legend isn't cut off
plt.tight_layout(rect=[0, 0, 1, 0.95]) 

plt.savefig("accestoenergy.png", dpi=300, bbox_inches='tight')
plt.show()
