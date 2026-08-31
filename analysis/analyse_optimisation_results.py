#%%
import sys
import os
import optuna
from pathlib import Path

import plotly

# Define the parent directory as your base
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))#sys.path.append(os.path.abspath(os.path.join(os.getcwd(), os.pardir)))
from dispatch_strategy.power_flow_edgeless import MicrogridSimulator, energy_distribution
from main import *
import plotly.express as px
from optimisation.MO_optimisation import *
BASE_DIR = Path(__file__).resolve().parent.parent
#%%load study
# Go up one level then into output
# Use the BASE_DIR you already defined
folder = BASE_DIR / "output" / "optuna_results"/"final_studies"

# Get all .db files using pathlib (cleaner)
files = list(folder.glob("*.db")) 
if not files:
    raise FileNotFoundError(f"No .db files found in {folder}")

latest_file = max(files, key=os.path.getctime)
#file_to_open= latest_file
file_to_open = BASE_DIR / "output" / "optuna_results" /"final_studies"/"soo_small_community_optimal_15years.db"
storage_url = f"sqlite:///{file_to_open.resolve()}"
summaries = optuna.get_all_study_summaries(storage=storage_url)
# Load the latest study
study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
#pareto_plot=optuna.visualization.plot_pareto_front(study, target_names=["economic_cost_value", "emission_cost_value"])
#open visulaization in browser
#plotly.offline.plot(pareto_plot, filename=str(BASE_DIR / "output" / "pareto_front.html"), auto_open=True)
#%%plot unmet load vs economic cost, colored by emissions
trial_info=study.trials_dataframe()
best_trial_number = study.best_trial.number
best_trial = study.trials[best_trial_number]
best_params = best_trial.params

trial_info['total_edges'] = trial_info[[col for col in trial_info.columns if col.startswith("params_edge_")]].sum(axis=1)
#total emissions 
print(f"cost: {study.best_trial.value}, unmet ratio: {study.best_trial.user_attrs.get('unmet_ratio', 'N/A')}")
#trial_info.to_csv("optuna_trials.csv", index=False)
#%%
optuna.visualization.plot_optimization_history(study)
#%%plot optimization history with y axis in log scale using plotly express
#plot trial number vs log of ecomonic cost, coloured by edge number
import plotly.express as px
import plotly.graph_objects as go

# 1. Define a discrete color scale for 7 values (0 to 6)
# Each number gets a solid block of color


import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. Define Convergence Criterion ---
# We define convergence as the point where the best value doesn't improve 
# by more than 0.1% over the last 50 trials.
# --- Objective Parameter Selection ---
total_trials = len(trial_info)
window = int(total_trials * 0.15)  # 15% of budget
# Threshold: Stop if improvement is less than the cost of a single typical component (e.g., $50)
precision_threshold_dollars = 100 
current_best = trial_info['value'].min()
threshold = precision_threshold_dollars / current_best

# --- Automated Search ---
trial_info = trial_info.sort_values("number")
trial_info['running_min'] = trial_info['value'].cummin()

convergence_trial = None
for i in range(window, len(trial_info)):
    improvement = (trial_info['running_min'].iloc[i - window] - trial_info['running_min'].iloc[i])
    # Check if the improvement over the window is less than our precision goal
    if improvement < precision_threshold_dollars:
        convergence_trial = trial_info['number'].iloc[i]
        break
# --- 2. Base Plotting ---
discrete_viridis = [
    [0.0, "#440154"], [0.142, "#440154"],   # 0
    [0.142, "#443983"], [0.285, "#443983"],  # 1
    [0.285, "#31688e"], [0.428, "#31688e"],  # 2
    [0.428, "#21918c"], [0.571, "#21918c"],  # 3
    [0.571, "#5ec962"], [0.714, "#5ec962"],  # 4
    [0.714, "#b8de29"], [0.857, "#b8de29"],  # 5
    [0.857, "#fde725"], [1.0, "#fde725"]     # 6
]
base_font_size = 20

fig = px.scatter(
    trial_info, 
    x="number", 
    y="value", 
    color="total_edges",
    color_continuous_scale=discrete_viridis,
    range_color=[-0.5, 6.5], 
    labels={"number": "Trial Number", "value": "Economic Cost ($)", "total_edges": "Total Edges"},
    log_y=True,
)

fig.update_traces(marker=dict(size=10, opacity=0.85))

# --- 3. Add Convergence Vertical Line ---
if convergence_trial:
    fig.add_vline(
        x=convergence_trial, 
        line_width=3, 
        line_dash="dot", 
        line_color="green",
        annotation_text=f"Convergence Met (Trial {convergence_trial})", 
        annotation_position="top left"
    )

# --- 4. Add Best Value Horizontal Line ---
best_value = study.best_trial.value
fig.add_shape(
    type="line",
    x0=0, y0=best_value,
    x1=trial_info["number"].max(), y1=best_value,
    line=dict(color="red", width=4, dash="dash"),
    layer="below"
)

# --- 5. Add Best Trial Marker ---
best_row = trial_info[trial_info['number'] == study.best_trial.number].iloc[0]
fig.add_trace(go.Scatter(
    x=[best_row['number']],
    y=[best_row['value']],
    mode='markers',
    marker=dict(
        size=20, 
        color=[best_row['total_edges']], 
        coloraxis="coloraxis",       
        line=dict(width=4, color='black') 
    ),
    name="Best Trial",
    showlegend=True
))

# --- 6. Layout Updates ---
fig.update_layout(
    template="plotly_white",
    font=dict(family="Arial", size=base_font_size, color="black"), 
    width=900, height=600,
    margin=dict(l=80, r=40, t=100, b=80), 
    coloraxis_colorbar=dict(
        title=dict(text="Total Edges", font=dict(size=base_font_size)),
        tickvals=[0, 1, 2, 3, 4, 5, 6],
        x=1.02
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig.update_xaxes(showgrid=True, gridcolor='LightGray')
fig.update_yaxes(showgrid=True, gridcolor='LightGray')

fig.show()
# Export as PDF for high-quality vector graphics (Marking: Typographical Quality)
fig.show()
fig.write_image(str(BASE_DIR / "output" / "optimization_history.pdf"), format="pdf", scale=2)  # scale=2 for higher resolution
#%% analyse optimimal configuration. Output of best trial
optimal_configuration = Configuration()
optimal_configuration.import_nodes_from_csv(str(BASE_DIR / "input" / "configurations" / "small_community_new.csv"))
print(optimal_configuration.nodes)
print(optimal_configuration.edges())
print(best_params)
optimal_configuration.import_trial_params(best_params   )
optimal_configuration.minimum_spanning_tree() # This is just to ensure we have a valid configuration, the actual optimal configuration is determined by the trial parameters and not the MST. We can remove this line if we want to see the actual configuration from the trial parameters without any modifications.
# optimal_configuration.add_edge("GG","MG")
# optimal_configuration.add_edge("GG","QL")
print(optimal_configuration.edges())
#%%
import matplotlib.pyplot as plt
from matplotlib import rc, rcParams
import networkx as nx
import seaborn as sns
import pandas as pd
import matplotlib.lines as mlines
from matplotlib.ticker import FormatStrFormatter, MaxNLocator
from matplotlib import patheffects, ticker
import numpy as np
optimal_configuration.minimum_spanning_tree()
# --- 1. Data Preparation ---
data = []
pos_map = {} 

for node, attr in optimal_configuration.nodes(data=True):
    lat, lon = attr["coordinates"]
    pos_map[node] = (lon, lat)
    
    data.append({
        "node_id": node, # Using your existing node ID attribute
        "longitude": lon,
        "latitude": lat,
        "Building Type": attr["profile_type"],
        "battery_size": attr.get("battery_capacity", 0),
        "solar_panels": attr.get("solar_panel_area", 0)
    })

df = pd.DataFrame(data)

# --- 2. Style Settings ---
sns.set_style("ticks")
sns.set_context("talk", rc={"font.size": 12, "axes.labelsize": 12, "axes.titlesize": 12, "legend.fontsize": 12})
plt.rcParams.update({
    "pdf.fonttype": 42, 
    "ps.fonttype": 42, 
    "font.family": "sans-serif", 
    "font.sans-serif": ["Arial"]
})

# Shape Mapping
marker_map = {
    "hospital": "P", 
    "school": "*",
    "house": "o",
    "commercial": "s",
    "water_pump": "v",
    "MG": "X",
    "QL":"X",
    "GG":"X"
}

# --- 3. Create Plot ---
w=8.27 
fig, ax = plt.subplots(figsize=(w*0.4, w*0.6))

# Draw Infrastructure Edges (High Visibility Red)
for u, v in optimal_configuration.edges():
    x_coords = [pos_map[u][0], pos_map[v][0]]
    y_coords = [pos_map[u][1], pos_map[v][1]]
    ax.plot(x_coords, y_coords, color="#FF1111", alpha=0.8, 
            linewidth=4, zorder=1, solid_capstyle='round')

# --- 4. Fixed Scaling for Comparison ---

# Color Normalization (Fixed max at 120 kW)
#fixed_solar_max = 100
fixed_solar_max = 50
norm = plt.Normalize(0, fixed_solar_max)
sm = plt.cm.ScalarMappable(cmap="viridis", norm=norm)
sm.set_array([])

# Battery Size Normalization (Fixed max at 300 kWh)
fixed_battery_max = 500
size_norm = plt.Normalize(0, fixed_battery_max)

# Plot Markers
sns.scatterplot(
    data=df,
    x="longitude",
    y="latitude",
    hue="solar_panels",
    palette="viridis",
    hue_norm=norm,
    style="Building Type",
    markers=marker_map,
    size="battery_size",
    size_norm=size_norm,
    sizes=(300, 6000), # Constant visual scale
    edgecolor="black",
    linewidth=1.2,
    ax=ax,
    legend=False, 
    zorder=3
)

# # Add Labels for Node IDs
# for i, row in df.iterrows():
#     ax.text(
#         row['longitude'], 
#         row['latitude'] + 0.00008, # Nudge label above marker
#         str(row['node_id']),
#         fontsize=12,
#         fontweight='bold',
#         ha='center',
#         zorder=5,
#         path_effects=[patheffects.withStroke(linewidth=3, foreground="white")]
#     )

# --- 5. Legends & Colorbar ---

# Horizontal Colorbar at bottom
cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.05, pad=0.35, extend="max")
cbar.set_label('Solar Panel Capacity (kW)', fontsize=12)

# Custom Legend for Building Types
type_handles = []
present_types = sorted(df["Building Type"].unique())
for b_type in present_types:
    marker = marker_map.get(b_type, "o")
    handle = mlines.Line2D([], [], color='none', marker=marker, 
                           markerfacecolor="#3471FF", markeredgecolor='black',
                           markersize=12, label=b_type.capitalize(), linestyle='None')
    type_handles.append(handle)

ax.legend(handles=type_handles, title="Building Type", 
          frameon=True, edgecolor="gray", fontsize=12,bbox_to_anchor=(0.5, 1.1),  ncol=3, loc='lower center')

# --- 6. Coordinate Formatting ---
ax.set_xlim(36.99950429
-0.001/2, 37.00100429
+0.001/2)
ax.set_ylim(5.999082857
-0.001/2, 6.000752857
+0.001/2)
# ax.set_xlim(37.0732-0.01, 37.1252+0.01)
# ax.set_ylim(5.89097-0.01, 5.95382+0.01)
ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5, prune='both'))
ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5, prune='both'))
ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
ax.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))

plt.xticks(rotation=15)

# --- 7. Final Touches ---
ax.grid(True, linestyle='--', alpha=0.3, zorder=0)
ax.set_xlabel("Longitude (°)", labelpad=10)
ax.set_ylabel("Latitude (°)", labelpad=10)

#plt.tight_layout()
plt.savefig(str(BASE_DIR / "output" / "connected_configuration_map.pdf"), format="pdf", dpi=300)
plt.show()

# --- 8. Simulation & Export ---
profiles_df = optimal_configuration.get_profiles_dataframe(
    #load_profiles_file=BASE_DIR / "input" / "load_profiles" / "case_study_load.csv",
    load_profiles_file=BASE_DIR / "input" / "load_profiles" / "load_profiles_new.csv",
    irradiance_profile_file=BASE_DIR / "input" / "PV_profiles_files" / "case_study_pv.csv"
)
sim = MicrogridSimulator(optimal_configuration, delta_t=1)
final_df, logs, iterative_df_list,report,summary = sim.run_periodic(profiles_df)
final_df.to_csv(str(BASE_DIR / "output" / "optimal_configuration_results.csv"), index=False)
print("met peak load:", summary["met_peak_sum"])
 #%%Cost Pie Chart
#creat pie chart of cost distribution in the optimal configuration with matplotlib, use blue for battery cost, yellow for pv cost, grey for diesel cost
cost_dist = study.best_trial.user_attrs["cost_distribution"]
print(cost_dist)
#remove Diesel Generator cost from the cost distribution
cost_dist.pop("Diesel Generator", None)
cost_dist.pop("Fuel", None)
#convert object representation of dictionary to actual dictionary
labels = cost_dist.keys()
sizes = cost_dist.values()
colors = ['Yellow', 'orange', 'blue', "red","grey","purple"]
plt.figure(figsize=(8, 8))
#use valeeus instead of percentages
plt.pie(sizes, labels=labels, autopct=lambda pct: f'{pct/100*sum(sizes):.1f}', startangle=140, colors=colors)
plt.title('Cost Distribution in the Microgrid')
plt.axis('equal')
plt.show()
#%%
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# 1. Professional Context & Styling
sns.set_context("talk", font_scale=1.)
sns.set_style("ticks")
plt.rcParams["pdf.fonttype"] = 42

fig, ax = plt.subplots(figsize=(11, 7))

# --- Data Mapping ---
# Using the index as the trial number to show optimization progress over time
x = trial_info["total_edges"]
y = trial_info["value"]
hue = trial_info.index 

# 2. Logarithmic Scale Logic
# This makes the difference between $1,000 and $2,000 visually larger 
# than the difference between $100,000 and $101,000.
ax.set_yscale("log")

# 3. Swarmplot with Trial Number Gradient
# 'viridis' or 'plasma' are great for showing progression
plot = sns.swarmplot(
    data=trial_info,
    x="total_edges", 
    y="value", 
    hue=trial_info.index,
    palette="viridis",
    size=6, 
    edgecolor="white", 
    linewidth=0.7,
    ax=ax
)

# 4. Refined Log Axis Formatting
# Custom formatter to show 'k' values even on a log scale
ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'${x/1000:g}k'))
# Ensure we have enough ticks to see the "spread"
ax.yaxis.set_major_locator(ticker.LogLocator(base=10, numticks=10))

# 5. Legend Update
# Since Trial Numbers aren't usually in the thousands, we remove the /1000 logic here
handles, labels = ax.get_legend_handles_labels()
ax.legend(
    handles, labels,
    title="Trial Sequence (Time)",
    bbox_to_anchor=(0.5, 1.1), 
    loc='lower center',
    ncol=6,
    frameon=True,
    fontsize='x-small',
    title_fontsize='small',
    edgecolor='gray'
)

# 6. Final Polish
plt.xlabel("Total Number of Edges", fontweight='bold')
plt.ylabel("Economic Cost ($) - Log Scale", fontweight='bold')
plt.title("Microgrid Optimization: Cost Convergence by Trial", pad=20, fontweight='bold')

sns.despine()
plt.tight_layout()

plt.show()
# %%Create a table of the Total Capacity of Solar Panels and Batteries in the Optimal Configuration, the cost of  solar panels, the cost of batteries, the cost of diesel, and the total economic cost. the energy produced by solar panels, the energy stored in batteries, and the energy produced by diesel generators. Save this table as a csv file.
# #    cost_distribution = {
#         "PV": pv_cost,
#         "Battery": battery_cost,
#         "Hydro": hydro_cost,  
#         "Edges": edge_cost,
#         "Fuel": fuel_cost,
#         "Diesel Generator": generator_cost
#     }
# "def energy_distribution(df):
#     """
#     Total energy distribution for a simulation.
#     Used for the pie chart.
#     """
#     # Example function to calculate total energy used by the microgrid
    
#     batteries = df['energy_used'].sum()
#     unmet_load = df['unmet_load'].sum()
#     total_load = df['load_profile'].sum()
#     hydro_power_sum = df['hydro_power'].sum()- df['discarded_energy_hydro'].sum()
#     pv_contributed = df['pv_profile'].sum() - df['discarded_energy_pv'].sum()
    
#     return {
#         "batteries": batteries,
#         "unmet_load": unmet_load,
#         "hydro_power": hydro_power_sum,
#         "pv_contributed": pv_contributed
#     }
#     "
#add diesel gen cost and capacity to the optimal configuration and energy distribution also the km of edges in the optimal configuration and cost of edges, add these to the table as well
import pandas as pd
profiles_df = optimal_configuration.get_profiles_dataframe(
    #load_profiles_file=BASE_DIR / "input" / "load_profiles" / "case_study_load.csv",
    load_profiles_file=BASE_DIR / "input" / "load_profiles" / "load_profiles_new.csv",
    irradiance_profile_file=BASE_DIR / "input" / "PV_profiles_files" / "case_study_pv.csv"
)
sim= MicrogridSimulator(optimal_configuration, delta_t=1)
final_df, logs, iterative_df_list,report,summary = sim.run_periodic(profiles_df)

cost_dist = study.best_trial.user_attrs["cost_distribution"]
energy_dist = energy_distribution(final_df)
table_data = {
    "Total Solar Capacity (kW)": sum(optimal_configuration.nodes[node]['solar_panel_area'] for node in optimal_configuration.nodes),
    "Total Battery Capacity (kWh)": sum(optimal_configuration.nodes[node]['battery_capacity'] for node in optimal_configuration.nodes)/0.8,
    #"Total Diesel Generator Capacity (kW)":summary["unmet_peak_sum"],  # Assuming unmet load is met by diesel generators,
    "Converter Capacity (kW)": summary["met_peak_sum"],  # Assuming all met load requires conversion
    #"Total Edge Length (km)": optimal_configuration.total_edge_distance(),
    "Cost of Solar Panels ($)": cost_dist["PV"],
    "Cost of Batteries ($)": cost_dist["Battery"],
    "Cost of Converters ($)": cost_dist.get("Converter", 0),  # In case converter cost is not present
    #"Cost of Diesel Fuel ($)": cost_dist["Fuel"],
    #"Cost of Diesel Generators ($)": cost_dist["Diesel Generator"],
    "Cost of Hydro ($)": cost_dist.get("Hydro", 0),  # In case hydro cost is not present
    "Cost of Edges ($)": cost_dist["Edges"],
    "Total Economic Cost ($)": study.best_trial.value,
    #"Energy Produced by Solar Panels (kWh)": energy_dist["pv_contributed"],
    #"Energy Stored in Batteries (kWh)": energy_dist["batteries"],
    #"Energy Produced by Diesel Generators (kWh)": energy_dist["unmet_load"],
    #"Total Emissions (kg CO2)": study.best_trial.user_attrs["total_emissions"]
    "Unmet Ratio": study.best_trial.user_attrs.get("unmet_ratio", "N/A"),
    #"Total Discarded Energy (kWh)": final_df['discarded_energy'].sum(),
    #"Total Energy Produced (kWh)": final_df['pv_profile'].sum() + final_df['hydro_power'].sum(),
    "Discarded Energy ratio": final_df['discarded_energy'].sum() / (final_df['pv_profile'].sum() + final_df['hydro_power'].sum()),
    #"Total Met Load (kWh)": final_df['load_profile'].sum()- final_df['unmet_load'].sum() + final_df['met_deferable_load'].sum()
    #clcuate LCUE for sola
}
df = pd.DataFrame([table_data])
df.to_csv("optimal_configuration_table.csv", index=False)

#%%%