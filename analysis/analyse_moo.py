#%%
import plotly.express as px
import plotly.graph_objects as go
import optuna
import optuna.visualization as vis
import numpy as np 
import pandas as pd
from pathlib import Path

# --- 1. SETUP CONSTANTS FOR A4 PORTRAIT ---
# A4 is 210mm x 297mm. At 96 DPI: 210mm ~ 79 4px.
A4_WIDTH = 794*0.8
A4_QUARTER_HEIGHT = 280*1.2  # Approx 1/4 of A4 height (1123px)
FONT_SIZE = 12

# Define specific colors for consistency across all three charts
STUDY_COLORS = {
    "Isolated": "#1f77b4",          # Blue
    "MST": "#ff7f0e",               # Orange
    "Optimally Connected": "#2ca02c" # Green
}

# --- 2. SETUP PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
results_folder = BASE_DIR / "output" / "optuna_results"

studies_config = {
    "Isolated": {"file": "MOO_isolated_20260422_093210.db", "years": 1},
    "MST": {"file": "MOO_MST_20260422_113106.db", "years": 1},
    # "Optimally Connected": {"file": "MOO_OptimallyConnected_20260422_120102.db", "years": 1}
}

all_pareto_data = []
all_conv_traces = []

# --- 3. DATA PROCESSING ---
for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists():
        print(f"Skipping {label}: File not found at {file_path}")
        continue
        
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    # Process Pareto Data
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completed_trials:
        continue

    data = []
    for t in completed_trials:
        # Edge logic for different study types
        if label == "Isolated": 
            n_edges = 0
        elif label == "MST": 
            n_edges = 6
        else: 
            n_edges = sum(val for key, val in t.params.items() if key.startswith("edge_"))

        data.append({
            "number": t.number,
            "val_0": t.values[0] / config["years"],
            "val_1": (t.values[1] / config["years"]) / 1000,
            "n_edges": n_edges,
            "unmet_ratio": t.user_attrs.get("unmet_ratio", 0) 
        })
    
    df = pd.DataFrame(data)
    pareto_indices = [t.number for t in study.best_trials]
    pareto_df = df[df['number'].isin(pareto_indices)].copy()
    pareto_df['study_label'] = label
    all_pareto_data.append(pareto_df)

    # Process Hypervolume Convergence
    raw_values = np.array([t.values for t in completed_trials])
    nadir_point = np.max(raw_values, axis=0) 
    auto_ref_point = nadir_point * 1.1

    try:
        hv_fig = vis.plot_hypervolume_history(study, reference_point=auto_ref_point)
        for trace in hv_fig.data:
            trace.name = f"{label}"
            trace.line.color = STUDY_COLORS.get(label) # Sync convergence line color
            all_conv_traces.append(trace)
    except Exception as e:
        print(f"Convergence plot failed for {label}: {e}")

# --- 4. FINAL PLOTTING ---
# --- Updated Plot 1: Pareto Fronts (Emissions on X, Cost on Y) ---

combined_df = pd.concat(all_pareto_data, ignore_index=True)
fig_pareto = go.Figure()
shape_map = {"Isolated": "square", "MST": "circle", "Optimally Connected": "triangle-up"}

for label, shape in shape_map.items():
    # Sort by Emissions (val_1) now that it is on the X-axis
    subset = combined_df[combined_df['study_label'] == label].sort_values("val_1")
    if subset.empty: continue
    
    trace_color = STUDY_COLORS.get(label)

    fig_pareto.add_trace(go.Scatter(
        x=subset["val_1"], # Emissions on X
        y=subset["val_0"], # Cost on Y
        mode='markers+lines',
        name=label,
        line=dict(color=trace_color),
        marker=dict(
            size=10, 
            symbol=shape, 
            color=trace_color,
            line=dict(width=1, color='white')
        ),
        hovertemplate="<b>%{name}</b><br>Emissions: %{x:,.2f}t<br>Cost: $%{y:,.0f}<extra></extra>"
    ))

fig_pareto.update_layout(
    template="plotly_white",
    xaxis_title="Total Emissions (tonnes CO<sub>2</sub>)", #
    yaxis_title="Total Economic Cost ($)", #
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig_pareto.show()
fig_pareto.write_image("pareto_front_swapped.pdf")
#%%
# Plot 2: Convergence Comparison
# --- Updated Plot 2: Convergence Comparison ---

# Constants used for calculation (already in your code)
WINDOW = 200  
EPSILON = 0.005  # 0.5% threshold

fig_conv = go.Figure(data=all_conv_traces)

for trace in all_conv_traces:
    hv_series = pd.Series(trace.y, index=trace.x)
    
    # Calculate percentage change over the window
    # (Current HV - Previous HV) / Previous HV
    delta_hv = hv_series.diff(periods=WINDOW) / hv_series.shift(WINDOW)
    
    converged_idx = None
    for i in range(WINDOW, len(delta_hv)):
        if delta_hv.iloc[i] < EPSILON:
            converged_idx = hv_series.index[i]
            break
            
    if converged_idx:
        # --- THE CHANGE IS HERE ---
        # Label reflects the specific stopping criteria
        label_text = f"<{EPSILON*100}% growth over {WINDOW} trials"
        
# ... (inside your loop for all_conv_traces) ...

    if converged_idx:
        # Define the label as "Convergence at Trial X"
        label_text = f"Trial {converged_idx}"
        
        fig_conv.add_vline(
            x=converged_idx, 
            line_dash="dash", 
            line_color=trace.line.color,
            # Bold the study name and place the convergence info below it
            annotation_text=f"<br>{label_text}",
            annotation_position="top left",
            annotation_font_size=12
        )
        print(f"{trace.name} marked as converged at trial {converged_idx}")
fig_conv.update_layout(
    title="Hypervolume Convergence",
    xaxis_title="Trial Number",
    yaxis_title="Pareto Area (a.u.)",
    template="plotly_white",
    width=A4_WIDTH, height=A4_QUARTER_HEIGHT*1.2,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig_conv.write_image("convergence_moo.pdf")
fig_conv.show()
#%%
# Plot 3: Carbon Price Sensitivity Analysis
carbon_prices = np.linspace(0, 120, 500)
sensitivity_data = []

for label in combined_df['study_label'].unique():
    df_study = combined_df[combined_df['study_label'] == label]
    for price in carbon_prices:
        total_costs = df_study["val_0"] + (df_study["val_1"] * price)
        min_total_cost = total_costs.min()
        sensitivity_data.append({
            "Study": label,
            "Carbon Price": price,
            "Total Cost": min_total_cost
        })

sensitivity_df = pd.DataFrame(sensitivity_data)

fig_sens = px.line(
    sensitivity_df, x="Carbon Price", y="Total Cost", color="Study",
    title="Carbon Price Sensitivity",
    template="plotly_white",
    color_discrete_map=STUDY_COLORS # Ensure color consistency here too
)

fig_sens.update_layout(
    width=A4_WIDTH, height=A4_QUARTER_HEIGHT*1.2, # Slightly taller for better readability
    font=dict(size=FONT_SIZE),
    xaxis_title="Carbon Price ($/tCO2)",
    yaxis_title="Total Cost ($/yr)",
    yaxis_tickformat="$,.2s", # Simplified currency (e.g., 1.2M) for space
    margin=dict(l=70, r=20, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig_sens.show()
#%%
#%%
# Plot 4: Cost Difference (Isolated - MST) at Equivalent Emission Levels
from scipy.interpolate import interp1d

# 1. Filter data for the two groups
df_iso = combined_df[combined_df['study_label'] == "Isolated"].sort_values("val_1")
df_mst = combined_df[combined_df['study_label'] == "MST"].sort_values("val_1")

# 2. Determine the overlapping range of Emissions (val_1)
min_emissions = max(df_iso["val_1"].min(), df_mst["val_1"].min())
max_emissions = min(df_iso["val_1"].max(), df_mst["val_1"].max())

# Create a common grid of emission values for interpolation
emission_grid = np.linspace(min_emissions, max_emissions, 200)

# 3. Interpolate Costs (val_0) for both studies
# We use linear interpolation to estimate cost at specific emission points
f_iso = interp1d(df_iso["val_1"], df_iso["val_0"], kind='linear', fill_value="extrapolate")
f_mst = interp1d(df_mst["val_1"], df_mst["val_0"], kind='linear', fill_value="extrapolate")

cost_diff = f_iso(emission_grid) - f_mst(emission_grid)

# 4. Plotting
fig_diff = go.Figure()

fig_diff.add_trace(go.Scatter(
    x=emission_grid,
    y=cost_diff,
    mode='lines',
    name='Cost Savings (Isolated - MST)',
    line=dict(color='purple', width=3),
    fill='tozeroy', # Shading the area under the curve
    hovertemplate="Emissions: %{x:.2f}t<br>Cost Savings: $%{y:,.0f}<extra></extra>"
))

fig_diff.update_layout(
    title="Economic Benefit of Connection (MST vs Isolated)",
    xaxis_title="Emissions (tonnes CO<sub>2</sub>)",
    yaxis_title="Cost Difference ($)",
    template="plotly_white",
    width=A4_WIDTH, height=A4_QUARTER_HEIGHT,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=50, b=50)
)

# Add an annotation explaining what the positive value means
fig_diff.add_annotation(
    x=emission_grid[len(emission_grid)//2],
    y=max(cost_diff)*0.9,
    text="Positive values indicate MST is cheaper than Isolated",
    showarrow=False,
    font=dict(size=10, color="gray")
)

fig_diff.show()
fig_diff.write_image("cost_difference.pdf")
#%%
#%% Plot 10: Total Lifecycle Cost Breakdown (Edges at Base, Hydro Excluded)
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px

# 1. Prepare Data
stacked_records = []
total_records = []

for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists(): continue
    
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    for t in study.best_trials:
        cost_dist = t.user_attrs.get("cost_distribution", {})
        if not cost_dist: continue
        
        # Total emissions for the entire period (kg to tonnes)
        total_emissions = t.values[1] / 1000  
        # Total lifecycle economic cost
        total_lifecycle_cost = t.values[0]     
        
        # Row for Stacked Area
        row = {"Emissions": total_emissions, "Study": label, "Total": total_lifecycle_cost}
        for component, val in cost_dist.items():
            if component == "Hydro": continue
            # Use raw values for Total Lifecycle Cost
            row[component] = val 
        stacked_records.append(row)
        
        # Row for Total Line Verification
        total_records.append({"Emissions": total_emissions, "Study": label, "Total": total_lifecycle_cost})

df_stacked = pd.DataFrame(stacked_records).sort_values("Emissions")
df_total = pd.DataFrame(total_records).sort_values("Emissions")

# 2. Determine and Sort Components
all_cols = df_stacked.columns.tolist()
metadata_cols = ["Emissions", "Study", "Total"]
cost_components = [c for c in all_cols if c not in metadata_cols]

ordered_components = []
if "Edges" in cost_components:
    ordered_components.append("Edges")
ordered_components += [c for c in cost_components if c != "Edges"]

# 3. Melt Data for Plotting
df_melted = df_stacked.melt(
    id_vars=["Emissions", "Study"], 
    value_vars=ordered_components, 
    var_name="Component", 
    value_name="Cost"
)

# 4. Create the Stacked Area Plot
fig = px.area(
    df_melted, 
    x="Emissions", 
    y="Cost", 
    color="Component", 
    facet_col="Study",
    title=f"Total Lifecycle Cost Composition (Edges at Base, Hydro Excluded)",
    template="plotly_white",
    labels={"Emissions": "Total Emissions (tCO2)", "Cost": "Total Economic Cost ($)"},
    category_orders={"Component": ordered_components},
    color_discrete_sequence=px.colors.qualitative.Prism
)

# 5. Add Total Cost Verification Line
studies = df_total['Study'].unique()
for i, study_name in enumerate(studies):
    subset = df_total[df_total['Study'] == study_name]
    
    fig.add_scatter(
        x=subset["Emissions"], 
        y=subset["Total"],
        mode='lines',
        name=f"Total Lifecycle Cost ({study_name})",
        line=dict(color="black", width=2.5, dash="dash"),
        row=1, col=i+1,
        showlegend=True if i == 0 else False
    )

# 6. Final Layout
fig.update_layout(
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT * 1.6,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=80, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
    yaxis_tickformat="$,.2s"
)

fig.update_yaxes(matches='y')
fig.show()
fig.write_image("total_lifecycle_cost_breakdown.pdf")
#%% Plot 11: Refined Diverging Stacked Cost Difference (Isolated - MST)
from scipy.interpolate import interp1d

# 1. Component Data Extraction
component_dfs = {}
for label in ["Isolated", "MST"]:
    config = studies_config[label]
    storage_url = f"sqlite:///{(results_folder / config['file']).resolve()}"
    study = optuna.load_study(study_name=optuna.get_all_study_summaries(storage_url)[0].study_name, storage=storage_url)
    
    trials_data = []
    for t in study.best_trials:
        # Total emissions in tonnes
        row = {"Emissions": t.values[1] / 1000}
        for comp, val in t.user_attrs.get("cost_distribution", {}).items():
            if comp == "Hydro" or val == 0: continue
            row[comp] = val
        trials_data.append(row)
    component_dfs[label] = pd.DataFrame(trials_data).sort_values("Emissions")

# 2. Interpolation on a shared emission grid
min_em = max(component_dfs["Isolated"]["Emissions"].min(), component_dfs["MST"]["Emissions"].min())
max_em = min(component_dfs["Isolated"]["Emissions"].max(), component_dfs["MST"]["Emissions"].max())
em_grid = np.linspace(min_em, max_em, 200)

diff_records = []
all_comps = list(set(component_dfs["Isolated"].columns) | set(component_dfs["MST"].columns))
all_comps.remove("Emissions")

for comp in all_comps:
    # Get values for both (default to 0 if component doesn't exist in that study)
    v_iso = interp1d(component_dfs["Isolated"]["Emissions"], component_dfs["Isolated"][comp], 
                     kind='linear', fill_value="extrapolate")(em_grid) if comp in component_dfs["Isolated"] else np.zeros_like(em_grid)
    v_mst = interp1d(component_dfs["MST"]["Emissions"], component_dfs["MST"][comp], 
                     kind='linear', fill_value="extrapolate")(em_grid) if comp in component_dfs["MST"] else np.zeros_like(em_grid)
    
    # Calculate Savings (Positive) and Extra Costs (Negative)
    # If Isolated cost > MST cost, it's a "Benefit" (Positive)
    # If MST cost > Isolated cost, it's a "Penalty" (Negative)
    diff = v_iso - v_mst
    
    for i in range(len(em_grid)):
        diff_records.append({
            "Emissions (tCO2)": em_grid[i],
            "Component": comp,
            "Difference": diff[i]
        })

df_diff = pd.DataFrame(diff_records)

# 3. Plotting with a clearer layout
fig_diff = px.area(
    df_diff, 
    x="Emissions (tCO2)", 
    y="Difference", 
    color="Component",
    title="Economic Benefit of MST Connectivity (Isolated Cost - MST Cost)",
    labels={"Difference": "Cost Savings (+) or Added Cost (-) [$]"},
    template="plotly_white",
    color_discrete_sequence=px.colors.diverging.Spectral
)

# 4. Add the Net Total line (The actual total savings)
total_iso = interp1d(df_iso["val_1"], df_iso["val_0"] * studies_config["Isolated"]["years"], kind='linear', fill_value="extrapolate")(em_grid)
total_mst = interp1d(df_mst["val_1"], df_mst["val_0"] * studies_config["MST"]["years"], kind='linear', fill_value="extrapolate")(em_grid)
net_savings = total_iso - total_mst

fig_diff.add_scatter(
    x=em_grid, y=net_savings, 
    mode='lines', name='Net Total Savings',
    line=dict(color='black', width=3)
)

fig_diff.add_hline(y=0, line_dash="dash", line_color="black")

fig_diff.update_layout(
    width=A4_WIDTH, height=A4_QUARTER_HEIGHT * 1.8,
    font=dict(size=FONT_SIZE),
    yaxis_tickformat="$,.2s",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig_diff.show()
fig_diff.write_image("clear_cost_difference.pdf")
#%% Plot 12: Discrete Savings Bar Chart (Isolated vs MST)
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# 1. Select specific emission "Scenarios" for clearer comparison
# We'll pick 5 points along the shared emission range
min_em = max(df_iso["val_1"].min(), df_mst["val_1"].min())
max_em = min(df_iso["val_1"].max(), df_mst["val_1"].max())
scenarios = np.linspace(min_em, max_em, 6)

bar_records = []
all_comps = [c for c in df_stacked.columns if c not in ["Emissions", "Study", "Total"]]

for em_target in scenarios:
    # Interpolate each component at this specific emission target
    for comp in all_comps:
        # Isolated Value
        f_iso = interp1d(component_dfs["Isolated"]["Emissions"], component_dfs["Isolated"][comp], 
                         kind='linear', fill_value="extrapolate") if comp in component_dfs["Isolated"] else lambda x: 0
        # MST Value
        f_mst = interp1d(component_dfs["MST"]["Emissions"], component_dfs["MST"][comp], 
                         kind='linear', fill_value="extrapolate") if comp in component_dfs["MST"] else lambda x: 0
        
        v_iso = float(f_iso(em_target))
        v_mst = float(f_mst(em_target))
        
        diff = v_iso - v_mst
        if abs(diff) < 1: continue # Skip negligible differences
        
        bar_records.append({
            "Scenario (tCO2)": f"{em_target:.1f}",
            "Component": comp,
            "Difference": diff,
            "Type": "Savings (MST is cheaper)" if diff > 0 else "Penalty (Isolated is cheaper)"
        })

df_bar = pd.DataFrame(bar_records)

# 2. Create the Diverging Bar Chart
fig_bar = px.bar(
    df_bar, 
    x="Scenario (tCO2)", 
    y="Difference", 
    color="Component",
    title="Economic Impact of MST Connectivity by Emission Scenario",
    labels={"Difference": "Total Lifecycle Cost Difference ($)", "Scenario (tCO2)": "Emission Target (Total Tonnes)"},
    template="plotly_white",
    barmode="relative" # This stacks positive and negative values separately from the zero line
)

# 3. Add the Net Savings as a Dot/Line
net_data = df_bar.groupby("Scenario (tCO2)")["Difference"].sum().reset_index()
fig_bar.add_trace(go.Scatter(
    x=net_data["Scenario (tCO2)"], 
    y=net_data["Difference"],
    mode='markers+lines+text',  
    name='Net Savings',
    text=[f"${v/1e3:.3f}K" for v in net_data["Difference"]],
    textposition="top center",
    textfont=dict(
        family="Arial Black", # Optinal: choose a naturally thicker font
        size=16,              # Increase this for BIGGER text
        color="Black"      # CHOOSE YOUR COLOR HERE (e.g., "red", "black", "#FF5733")
    ),
    line=dict(color='black', width=3),
    marker=dict(size=10, symbol="diamond")
))

fig_bar.update_layout(
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT * 1.8,
    font=dict(size=FONT_SIZE),
    yaxis_tickformat="$,.2s",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig_bar.show()
fig_bar.write_image("savings_bar_chart.pdf")
#%% Plot 5: Pareto Design Space (Aggregated PV vs Battery vs Emissions)

pareto_design_data = []

for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists(): continue
    
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    # 1. Use the trials_dataframe to identify the correct parameter column names
    # Optuna prefixes parameter columns with 'params_'
    df_all = study.trials_dataframe()
    
    # Identify PV and Battery columns dynamically (case-insensitive)
    pv_cols = [col for col in df_all.columns if any(x in col.lower() for x in ["solar", "pv"])]
    batt_cols = [col for col in df_all.columns if any(x in col.lower() for x in ["battery", "batt"])]
    
    # 2. Filter for only the Best (Pareto) trials
    pareto_indices = [t.number for t in study.best_trials]
    df_pareto = df_all[df_all['number'].isin(pareto_indices)].copy()
    
    # 3. Aggregate the totals for each Pareto trial
    df_pareto['Total Solar (kW)'] = df_pareto[pv_cols].sum(axis=1)
    # Applying the 0.8 effective capacity factor from your script's logic
    df_pareto['Total Battery (kWh)'] = df_pareto[batt_cols].sum(axis=1) / 0.8
    
    # 4. Map the objective values (val_0 = cost, val_1 = emissions)
    # Note: Objective column names in the dataframe are usually 'values_0', 'values_1'
    df_pareto['Emissions (tCO2/yr)'] = (df_pareto['values_1'] / config["years"]) / 1000
    df_pareto['Cost ($/yr)'] = df_pareto['values_0'] / config["years"]
    df_pareto['Study'] = label
    
    pareto_design_data.append(df_pareto[[
        'Study', 'Total Solar (kW)', 'Total Battery (kWh)', 
        'Emissions (tCO2/yr)', 'Cost ($/yr)'
    ]])

# Combine and Plot
combined_design_df = pd.concat(pareto_design_data, ignore_index=True)

fig_pareto_design = px.scatter(
    combined_design_df, 
    x="Total Solar (kW)", 
    y="Total Battery (kWh)", 
    color="Emissions (tCO2/yr)",
    facet_col="Study",
    title="Pareto Design Space: Infrastructure Sizing vs Emissions",
    color_continuous_scale="Viridis_r", 
    template="plotly_white",
    labels={"Emissions (tCO2/yr)": "tCO2/yr"}
)

fig_pareto_design.update_layout(
    width=A4_WIDTH, height=A4_QUARTER_HEIGHT * 1.3,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=80, b=50)
)

fig_pareto_design.update_traces(marker=dict(size=12, line=dict(width=1, color='black')))
fig_pareto_design.show()
fig_pareto_design.write_image("pareto_design_space.pdf")

#%% Plot 6: Pareto Sensitivity (Infrastructure vs Emissions)
import plotly.express as px
import pandas as pd

sensitivity_plot_data = []

for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists(): continue
    
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    # Extract the Pareto front trials (best_trials)
    for t in study.best_trials:
        # Summing capacities based on keywords in your trial parameters
        total_pv = sum(val for key, val in t.params.items() if any(x in key.lower() for x in ["solar", "pv"]))
        # Total nameplate battery capacity (using the 0.8 factor from your simulation)
        total_batt = sum(val for key, val in t.params.items() if any(x in key.lower() for x in ["battery", "batt"])) / 0.8
        
        emissions = (t.values[1] / config["years"]) / 1000
        cost = t.values[0] / config["years"]

        # Format data for long-form plotting
        sensitivity_plot_data.append({"Emissions (tCO2/yr)": emissions, "Value": cost, "Metric": "Cost ($/yr)", "Study": label})
        sensitivity_plot_data.append({"Emissions (tCO2/yr)": emissions, "Value": total_pv, "Metric": "Total PV (kW)", "Study": label})
        sensitivity_plot_data.append({"Emissions (tCO2/yr)": emissions, "Value": total_batt, "Metric": "Total Battery (kWh)", "Study": label})

df_sens_lines = pd.DataFrame(sensitivity_plot_data).sort_values("Emissions (tCO2/yr)")

# Create a Faceted Line Plot
fig_sens_lines = px.line(
    df_sens_lines, 
    x="Emissions (tCO2/yr)", 
    y="Value", 
    color="Study", 
    facet_row="Metric",
    title="Infrastructure and Cost Trends across the Pareto Front",
    color_discrete_map=STUDY_COLORS,
    template="plotly_white",
    category_orders={"Metric": ["Cost ($/yr)", "Total PV (kW)", "Total Battery (kWh)"]}
)

# Crucial: Allow each row to have its own Y-axis scale
fig_sens_lines.update_yaxes(matches=None, showgrid=True, gridcolor='LightGray')

fig_sens_lines.update_layout(
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT * 2.5, # Taller to accommodate three subplots
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=80, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

# Clean up axis labels to remove "Metric=" prefix
fig_sens_lines.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))

fig_sens_lines.show()
fig_sens_lines.write_image("pareto_component_trends.pdf")
#%% Plot 7: Stacked Cost Breakdown vs Emissions (Pareto Front)

stacked_cost_data = []

for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists(): continue
    
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    # Process only Pareto front trials
    for t in study.best_trials:
        # Retrieve the cost distribution from user_attrs
        cost_dist = t.user_attrs.get("cost_distribution", {})
        if not cost_dist: continue
        
        emissions = (t.values[1] / config["years"]) / 1000  # Convert to tonnes
        
        # Create a base record for this trial
        row = {
            "Emissions (tCO2/yr)": emissions,
            "Study": label
        }
        
        # Add each cost component, annualized
        for component, val in cost_dist.items():
            row[component] = val / config["years"]
            
        stacked_cost_data.append(row)

# Convert to DataFrame
df_stacked = pd.DataFrame(stacked_cost_data).sort_values("Emissions (tCO2/yr)")

# Melt the dataframe for a stacked plot (from wide to long format)
# We exclude the index columns 'Emissions' and 'Study'
cost_components = [c for c in df_stacked.columns if c not in ["Emissions (tCO2/yr)", "Study"]]
df_melted = df_stacked.melt(
    id_vars=["Emissions (tCO2/yr)", "Study"], 
    value_vars=cost_components,
    var_name="Cost Component", 
    value_name="Annual Cost ($)"
)

# Create the Stacked Area Plot
fig_stacked = px.area(
    df_melted, 
    x="Emissions (tCO2/yr)", 
    y="Annual Cost ($)", 
    color="Cost Component",
    facet_col="Study",
    title="Annual Cost Composition vs. Emission Levels",
    template="plotly_white",
    # Professional color palette for infrastructure
    color_discrete_sequence=px.colors.qualitative.T10 
)

fig_stacked.update_layout(
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT * 1.5,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=80, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis_tickformat="$,.2s" # Simplified currency (e.g. 100k)
)

fig_stacked.show()
fig_stacked.write_image("stacked_cost_vs_emissions.pdf")

#%%
#%% Plot 9: Stacked Cost Breakdown with Total Cost Line (Pareto Front)
#%% Plot 10: Refined Stacked Cost Breakdown (No Hydro, Edges at Base)
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px

# 1. Prepare Data
stacked_records = []
total_records = []

for label, config in studies_config.items():
    file_path = results_folder / config["file"]
    if not file_path.exists(): continue
    
    storage_url = f"sqlite:///{file_path.resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    for t in study.best_trials:
        cost_dist = t.user_attrs.get("cost_distribution", {})
        if not cost_dist: continue
        
        emissions = (t.values[1] / config["years"]) / 1000  # Tonnes CO2/yr
        total_cost = t.values[0] / config["years"]         # Annualized Total
        
        # Row for Stacked Area
        row = {"Emissions": emissions, "Study": label, "Total": total_cost}
        for component, val in cost_dist.items():
            # Skip Hydro as it is zero
            if component == "Hydro": continue
            row[component] = val / config["years"]
        stacked_records.append(row)
        
        # Row for Total Line Verification
        total_records.append({"Emissions": emissions, "Study": label, "Total": total_cost})

df_stacked = pd.DataFrame(stacked_records).sort_values("Emissions")
df_total = pd.DataFrame(total_records).sort_values("Emissions")

# 2. Determine and Sort Components
# Exclude metadata columns to find pure cost categories
all_cols = df_stacked.columns.tolist()
metadata_cols = ["Emissions", "Study", "Total"]
cost_components = [c for c in all_cols if c not in metadata_cols]

# Order components so "Edges" is at the base (bottom of the stack)
ordered_components = []
if "Edges" in cost_components:
    ordered_components.append("Edges")
# Add the rest of the components
ordered_components += [c for c in cost_components if c != "Edges"]

# 3. Melt Data for Plotting
df_melted = df_stacked.melt(
    id_vars=["Emissions", "Study"], 
    value_vars=ordered_components, 
    var_name="Component", 
    value_name="Cost"
)

# 4. Create the Stacked Area Plot
fig = px.area(
    df_melted, 
    x="Emissions", 
    y="Cost", 
    color="Component", 
    facet_col="Study",
    title="Annual Cost Composition (Edges at Base, Hydro Excluded)",
    template="plotly_white",
    labels={"Emissions": "Emissions (tCO2/yr)", "Cost": "Annual Cost ($/yr)"},
    # Fix the stacking order via category_orders
    category_orders={"Component": ordered_components},
    color_discrete_sequence=px.colors.qualitative.Prism
)

# 5. Add Total Cost Verification Line
studies = df_total['Study'].unique()
for i, study_name in enumerate(studies):
    subset = df_total[df_total['Study'] == study_name]
    
    fig.add_scatter(
        x=subset["Emissions"], 
        y=subset["Total"],
        mode='lines',
        name=f"Total Budget ({study_name})",
        line=dict(color="black", width=2.5, dash="dash"),
        row=1, col=i+1,
        showlegend=True if i == 0 else False
    )

# 6. Final Layout & Polish
fig.update_layout(
    width=A4_WIDTH, 
    height=A4_QUARTER_HEIGHT * 1.6,
    font=dict(size=FONT_SIZE),
    margin=dict(l=70, r=20, t=80, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
    yaxis_tickformat="$,.2s"
)

# Ensure Y-axis is consistent for comparison between studies
fig.update_yaxes(matches='y')

fig.show()
fig.write_image("refined_cost_breakdown.pdf")

#%% --- 5. DETAILED SIMULATION OF LOWEST EMISSION SETUPS ---
#%% --- 5. DETAILED SIMULATION OF LOWEST EMISSION SETUPS ---
import sys
import os
from pathlib import Path
import pandas as pd
import optuna

# 1. Setup paths to find your modules
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from main import Configuration 
from dispatch_strategy.power_flow_edgeless import MicrogridSimulator

# 2. Define simulation files
config_path = BASE_DIR / "input" / "configurations" / "small_community_new.csv"
load_file = BASE_DIR / "input" / "load_profiles" / "load_profiles_new.csv"
pv_file = BASE_DIR / "input" / "PV_profiles_files" / "case_study_pv.csv"

# Iterate through each study defined in your studies_config
for label, config in studies_config.items():
    print(f"--- Processing Lowest Emission Setup for: {label} ---")
    
    # 3. Load study and find the trial with minimum emissions (Objective index 1)
    storage_url = f"sqlite:///{(results_folder / config['file']).resolve()}"
    summaries = optuna.get_all_study_summaries(storage=storage_url)
    study = optuna.load_study(study_name=summaries[0].study_name, storage=storage_url)
    
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    best_emission_trial = min(completed_trials, key=lambda t: t.values[1])
    
    # 4. Setup the Configuration based on trial parameters
    sim_config = Configuration()
    sim_config.import_nodes_from_csv(str(config_path))
    sim_config.import_trial_params(best_emission_trial.params)
    
    # Apply structural logic based on study type
    if label == "Isolated":
        sim_config.remove_edges_from(list(sim_config.edges()))
    elif label == "MST":
        sim_config.minimum_spanning_tree()
    
    # 5. Run Simulation to get the 'summary' object
    profiles_df = sim_config.get_profiles_dataframe(
        load_profiles_file=load_file,
        irradiance_profile_file=pv_file
    )
    sim = MicrogridSimulator(sim_config, delta_t=1)
    final_df, logs, iterative_df_list, report, summary = sim.run_periodic(profiles_df)
    
    # 6. Extract results and calculate yearly metrics
    years = config["years"]
    peak_load = summary['met_peak_sum']
    unmet_total = summary['total_unmet']
    
    # Technical Totals
    total_solar = sum(sim_config.nodes[n].get('solar_panel_area', 0) for n in sim_config.nodes)
    # 0.8 is the effective capacity factor used in your MO_optimisation
    total_batt_kwh = sum(sim_config.nodes[n].get('battery_capacity', 0) for n in sim_config.nodes) / 0.8 
    
    # 7. Emission Calculations (Using factors from MO_optimisation.py)
    em_pv = (1520 * total_solar) / years / 1000  # Tonnes CO2/yr
    em_batt = (110 * total_batt_kwh) / years / 1000  # Tonnes CO2/yr
    em_conv = (124 * peak_load) / years / 1000  # Tonnes CO2/yr
    # Fuel: (1/10) * unmet * (yearly_hours/profile_length) * emission_factor
    em_fuel = ((1/10) * unmet_total * (365 * 24 / 24) * 3.0) / 1000  # Tonnes CO2/yr
    
    # 8. Create Summary Table
    cost_dist = best_emission_trial.user_attrs.get("cost_distribution", {})
    
    table_data = {
        "Study Type": label,
        "Trial Number": best_emission_trial.number,
        "Total Solar (kW)": total_solar,
        "Total Battery (kWh)": total_batt_kwh,
        "Converter Capacity (kW)": peak_load,
        "Edge Length (km)": sim_config.total_edge_distance(),
        "Cost Solar ($/yr)": cost_dist.get("PV", 0) / years,
        "Cost Battery ($/yr)": cost_dist.get("Battery", 0) / years,
        "Cost Converter ($/yr)": cost_dist.get("Converter", 0) / years,
        "Cost Edges ($/yr)": cost_dist.get("Edges", 0) / years,
        "Cost Fuel ($/yr)": cost_dist.get("Fuel", 0) / years,
        "Economic Cost ($/yr)": best_emission_trial.values[0] / years,
        "Emissions PV (tCO2/yr)": em_pv,
        "Emissions Battery (tCO2/yr)": em_batt,
        "Emissions Converter (tCO2/yr)": em_conv,
        "Emissions Fuel (tCO2/yr)": em_fuel,
        "Total Emissions (tCO2/yr)": (best_emission_trial.values[1] / years) / 1000,
        "Unmet Ratio": best_emission_trial.user_attrs.get("unmet_ratio", 0),
        "Discarded Energy Ratio": final_df['discarded_energy'].sum() / 
                                 (final_df['pv_profile'].sum() + 1e-9)
    }
    
    # 9. Export Data
    final_df.to_csv(BASE_DIR / "output" / f"sim_results_low_emission_{label}.csv", index=False)
    pd.DataFrame([table_data]).to_csv(BASE_DIR / "output" / f"summary_low_emission_{label}.csv", index=False)
    
    print(f"Successfully exported detailed results for {label}.")