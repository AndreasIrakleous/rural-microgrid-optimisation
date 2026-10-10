
#%%
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
from pathlib import Path

# ==========================================
# GLOBAL STYLE CONFIGURATION
# ==========================================
a4width = 8.27
a4height = 11.69

STYLE = {
    'dimensions': {
        'figsize': (a4width, a4height * 0.33),      
    },
    'colors': {
        'met_base': '#3498db',
        'met_defer': '#2ecc71',
        'discarded': '#e74c3c',
        'charging': '#9b59b6',
        'unmet_base': "#7f7f7f",
        'unmet_defer': "#2B2B2B",
        'line_hydro': 'blue',
        'line_pv': 'orange',
        'line_total': 'black'
    },
    'lines': {
        'width_hydro': 3,
        'width_pv': 3,
        'width_total': 3,
        'alpha_bars': 0.7
    },
    'fonts': {
        'axes_label': 14,
        'ticks': 12,
        'legend': 10
    },
    'labels': {
        'met_base': 'Met Base Load',
        'met_defer': 'Met Deferable Load',
        'discarded': 'Discarded Energy',
        'charging': 'Energy Stored (Charging)',
        'unmet_base': 'Unmet Base Load',
        'unmet_defer': 'Unmet Deferable Load',
        'hydro': 'Supply: Hydro',
        'pv': 'Supply:PV',
        'total': 'Total Supply (PV + Battery Discharge)'
    }
}

# ==========================================
# DATA LOADING & PREPROCESSING
# ==========================================
try:
    current_dir = os.path.dirname(__file__)
except NameError:
    current_dir = os.getcwd()

sys.path.append(os.path.abspath(os.path.join(current_dir, '..')))
BASE_DIR = Path(current_dir).resolve().parent

file_path = BASE_DIR / 'output' /'Timeframes' / 'sim_results_low_emission_MST.csv'
if not os.path.exists(file_path):
    fallbacks = ['output/Ethiopia_sim_output.csv', 'Ethiopia_sim_output.csv', 'optimal_configuration_results.csv']
    for path in fallbacks:
        if os.path.exists(path):
            file_path = path
            break

df = pd.read_csv(file_path)
df = df.sort_values(['node_id', 'time'])

df['next_SOC'] = df.groupby('node_id')['battery_SOC'].shift(-1)
for node in df['node_id'].unique():
    hour_0_soc = df[(df['node_id'] == node) & (df['time'] == 0)]['battery_SOC'].values[0]
    df.loc[(df['node_id'] == node) & (df['time'] == 23), 'next_SOC'] = hour_0_soc

df['charging_energy'] = (df['next_SOC'] - df['battery_SOC']).clip(lower=0)
df['energy_used_shifted'] = (df['battery_SOC'] - df['next_SOC']).clip(lower=0)
df['met_base_load'] = df['load_profile'] - df['unmet_load']

agg_df = df.groupby('time').agg({
    'met_base_load': 'sum', 'met_deferable_load': 'sum', 'discarded_energy': 'sum',
    'charging_energy': 'sum', 'unmet_load': 'sum', 'unmet_deferable_load': 'sum',
    'pv_profile': 'sum', 'hydro_power': 'sum', 'energy_used_shifted': 'sum',
    'load_profile': 'sum', 'deferable_load': 'sum'
}).reset_index()

# ==========================================
# PLOTTING FUNCTION
# ==========================================
def generate_energy_plot(data, show_hydro=True):
    fig, ax = plt.subplots(figsize=STYLE['dimensions']['figsize'], dpi=600)
    
    times = data['time']
    bottom = np.zeros(len(times))
    
    # Base bars (Z-order default is 1)
    bars = [
        (data['met_base_load'], STYLE['colors']['met_base'], STYLE['labels']['met_base']),
        (data['met_deferable_load'], STYLE['colors']['met_defer'], STYLE['labels']['met_defer']),
        (data['discarded_energy'], STYLE['colors']['discarded'], STYLE['labels']['discarded']),
        (data['charging_energy'], STYLE['colors']['charging'], STYLE['labels']['charging']),
        (data['unmet_load'], STYLE['colors']['unmet_base'], STYLE['labels']['unmet_base']),
        (10 * data['unmet_deferable_load'], STYLE['colors']['unmet_defer'], STYLE['labels']['unmet_defer'])
    ]
    
    for values, color, label in bars:
        ax.bar(times, values, bottom=bottom, label=label, color=color, alpha=STYLE['lines']['alpha_bars'])
        bottom += values

    supply_hydro = data['hydro_power']
    supply_hydro_pv = supply_hydro + data['pv_profile']
    supply_total = supply_hydro_pv + data['energy_used_shifted']

    # --- LINE STYLING & Z-ORDER ---
    if show_hydro:
        ax.step(times, supply_hydro, where='mid', label=STYLE['labels']['hydro'],
                 color=STYLE['colors']['line_hydro'], linewidth=STYLE['lines']['width_hydro'], 
                 linestyle=':', zorder=5) # Dotted for hydro
    
    # Total Supply (Drawn first/middle)
    ax.step(times, supply_total, where='mid', label=STYLE['labels']['total'],
             color=STYLE['colors']['line_total'], linewidth=STYLE['lines']['width_total'], 
             zorder=10)

    # Supply: PV (Dashed and forced to top using zorder=15)
    ax.step(times, supply_hydro_pv, where='mid', label=STYLE['labels']['pv'],
             color=STYLE['colors']['line_pv'], linewidth=STYLE['lines']['width_pv'], 
             linestyle='--', zorder=15)

    # Axis Labels & Formatting
    ax.set_xlabel('Time (h)', fontsize=STYLE['fonts']['axes_label'])
    ax.set_ylabel('Energy (kWh)', fontsize=STYLE['fonts']['axes_label'])
    ax.set_xticks(times)
    ax.tick_params(labelsize=STYLE['fonts']['ticks'])
    
    # Legend with spacing
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.25),
              ncol=3, fontsize=STYLE['fonts']['legend'], frameon=False)

    ax.grid(axis='y', linestyle='-', alpha=0.4)
    plt.subplots_adjust(bottom=0.3)
    plt.show()

# ==========================================
# EXECUTION
# ==========================================
SHOW_HYDRO_GLOBAL = False

generate_energy_plot(agg_df, show_hydro=SHOW_HYDRO_GLOBAL)

for node in df['node_id'].unique():
    generate_energy_plot(df[df['node_id'] == node], show_hydro=SHOW_HYDRO_GLOBAL)
# %%
