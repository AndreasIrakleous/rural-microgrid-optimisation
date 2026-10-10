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