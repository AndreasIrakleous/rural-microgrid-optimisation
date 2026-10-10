"""
Objective: Determine the optimal technology distribution for a given configuration

Inputs:
1. Configuration of nodes
2. Power flow simulation results (unmet load)

The optimisation aims to minimize the total cost, which is a weighted sum of:
- Cost of PV installations
- Cost of battery capacity
- Penalty for unmet energy demand

The unmet energy depends on the tech distribution for a given configuration.

The Bayesian optimser will try the black box approach where a set of inputs (tech distribution)
is provided and the output (total cost) is returned.

Hyper parameters:
1. PV area per node
2. Battery capacity per node
3. Penalty for unmet energy

Output:
Total cost
"""

#%%
import sys
import os
from matplotlib.pylab import load

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from pathlib import Path
import pandas as pd
from src.main import *
from src.dispatch_strategy.power_flow_edgeless import *
import optuna
from concurrent.futures import ProcessPoolExecutor, as_completed 
import time
import plotly.express as px

timeframe_years = 15

def cost_function(pv_sum, battery_sum, edge_distance_sum, unmet_sum, unmet_max, profile_length=24, timeframe_years=timeframe_years, w=1.0, hydro_power_sum=0, peak_load=0):
    """
    The cost function is a weighted sum of the prices of PV, battery, and unmet energy over a year.
    The prices depend on Gambia case study
    Args:
        pv_sum (int): sum of solar panels installed
        battery_sum (float): sum of battery capacity per node
        unmet_sum (float):  sum of unmet energy per node

    Returns:
        float: total cost
    
    Limitations:
        Does not consider the emission cost of energy sources.
    """

    timeframe_hours = timeframe_years * 365 * 24
    pv_capacity = 1 # kW
    pv_install = 900 # Price for rated capacity of 1 PV
    pv_om = (18) * timeframe_years # $/kWp/year
    pv_cost_per_pv = pv_install + pv_om # $/kW
    pv_cost = pv_cost_per_pv * pv_sum 
    pv_emissions = 1520 * pv_sum # kg CO2 per PV installed

    # Battery
    minimum_SOC = 0.2
    nominal_battery_capacity = 1 # kWh
    effective_battery_capacity = nominal_battery_capacity * (1 - minimum_SOC) 
    battery_install = 300 # Price of battery per battery
    battery_install_kwh = battery_install / effective_battery_capacity 
    battery_om_kwh_year = 6 / effective_battery_capacity 
    battery_om_kwh = battery_om_kwh_year * timeframe_years 
    battery_lifetime_years = 15 
    battery_replacement_cost_kwh = 0#timeframe_years // battery_lifetime_years * (battery_install_kwh) 
    battery_cost_kwh = battery_install_kwh + battery_om_kwh + battery_replacement_cost_kwh 
    battery_cost = battery_cost_kwh * battery_sum
    battery_emissions = 110 * battery_sum / (1 - minimum_SOC) 

    # Converter costs:
    converter_install = 300 
    converter_om = 6 * timeframe_years 
    converter_emission = 124 
    converter_cost = (converter_install + converter_om) * peak_load 
    converter_emissions = converter_emission * peak_load 

    # Diesel: for Case study we ignore diesel
    d_generator = 385 
    d_om = 0.15 * timeframe_years 
    d_fuel = 1 # $/litre
    d_energy = 10 # kWh/litre
    d_fuel_kwh = d_fuel / d_energy 
    fuel_cost = d_fuel_kwh * unmet_sum * (timeframe_hours / profile_length) 
    generator_cost = (d_generator + d_om) * unmet_max 
    gnererator_install_emissions = 0 * unmet_max 

    # Emissions:
    emission_factor = 3.0 # kg CO2 / kWh
    fuel_emissions = d_fuel_kwh * unmet_sum * (timeframe_hours / profile_length) * emission_factor 
    carbon_price = 57 # $/tonne CO2 (UKETS)

    hydro_install = 1501.82038835 
    hydro_OM = 45.0546116505 
    hydro_cost_kwh = hydro_install + hydro_OM * timeframe_years 
    hydro_cost = hydro_cost_kwh * hydro_power_sum 
    hydro_emissions = 0 * hydro_power_sum 

    # Edge cost
    edge_cost = 12200 * edge_distance_sum # $/km

    cost_distribution = {
        "PV": pv_cost,
        "Battery": battery_cost,
        "Hydro": hydro_cost, 
        "Edges": edge_cost,
        "Fuel": fuel_cost,
        "Diesel Generator": generator_cost,
        "Converter": converter_cost
    }

    economic_cost = pv_cost + battery_cost + edge_cost + hydro_cost+converter_cost + generator_cost + fuel_cost
    total_emissions = pv_emissions + battery_emissions + fuel_emissions + gnererator_install_emissions + hydro_emissions + converter_emissions 
    total_cost = w * economic_cost + (1 - w) * total_emissions

    return total_cost, economic_cost, total_emissions, cost_distribution

def configuration_costs(configuration, df):
    """
    Calculate cost from a configuration and a dataframe of results.
    """
    edge_total = configuration.total_edge_distance()
    pv_total = sum([configuration.nodes[node]["solar_panel_area"] for node in configuration.nodes])
    battery_total = sum([configuration.nodes[node]["battery_capacity"] for node in configuration.nodes])
    unmet_total = df['unmet_load'].sum()
    unmet_max = df['unmet_load'].max()
    hydro_power_sum = sum([configuration.nodes[node].get("hydro_power", 0) for node in configuration.nodes])
    
    total_cost, economic_cost, total_emissions, cost_distribution = cost_function(pv_total, battery_total, edge_total, unmet_total, unmet_max, hydro_power_sum=hydro_power_sum)
    
    return economic_cost, cost_distribution

def objective(trial, configuration: Configuration, w: float = 1.0):
    """
    Objective function for the Bayesian optimizer.
    """
    solar_map = {} 
    battery_map = {}
    node_list = list(configuration.nodes)


    for node in configuration.nodes:
        max_solar = configuration.nodes[node]["available_area"]
        max_battery = configuration.nodes[node]["battery_limit"]
        solar_area = trial.suggest_int(f"solar_{node}", 0, max_solar) 
        battery_capacity = trial.suggest_int(f"battery_{node}", 0, max_battery) 
        solar_map[node] = solar_area
        battery_map[node] = battery_capacity

      
    # configuration.minimum_spanning_tree() 
    
    # A = {u: {v: 0 for v in node_list} for u in node_list}
    # for u in configuration.nodes:
    #     for v in configuration.nodes:
    #         if u != v and (u, v) in configuration.edges() or (v, u) in configuration.edges(): 
    #             edge = tuple(sorted((u, v)))
    #             edge_value = trial.suggest_int(f"edge_{edge[0]}_{edge[1]}", 0, 1) 
    #             A[u][v] = edge_value
    #             A[v][u] = edge_value 
    # configuration.adjacency_matrix(A)




    configuration.bulk_configure_assets(battery_map=battery_map, solar_map=solar_map)
    
    profiles_df = configuration.get_profiles_dataframe("input/load_profiles/load_profiles_new.csv", irradiance_profile_file="input/PV_profiles_files/case_study_PV.csv")
    print(configuration.edges())
    sim = MicrogridSimulator(configuration, delta_t=1)
    df, A, c,report,summary = sim.run_periodic(profiles_df)

    edge_total = configuration.total_edge_distance()
    pv_total = sum(solar_map.values())
    battery_total = sum(battery_map.values())
    unmet_total = summary['total_unmet']
    unmet_max = summary['unmet_peak_sum']
    peak_load = summary['met_peak_sum']
    
    trial.set_user_attr("unmet_load", float(unmet_total))
    hydro_power_sum = sum([configuration.nodes[node].get("hydro_power", 0) for node in configuration.nodes])


    total_cost, economic_cost, total_emissions, cost_distribution = cost_function(
        pv_total, battery_total, edge_total, unmet_total, unmet_max,
        hydro_power_sum=hydro_power_sum, w=w, peak_load=peak_load
    )

    trial.set_user_attr("cost_distribution", cost_distribution)
    trial.set_user_attr("total_emissions", total_emissions)
    trial.set_user_attr("economic_cost", economic_cost)
    trial.set_user_attr("w", w)
    
    total_load = df['load_profile'].sum()+df["met_deferable_load"].sum()+df["unmet_deferable_load"].sum()
    unmet_ratio = (unmet_total / total_load) if total_load > 0 else 0
    trial.set_user_attr("unmet_ratio", unmet_ratio)
    
    print(f"Trial {trial.number}: Total Cost={total_cost}, Economic Cost={economic_cost}, Total Emissions={total_emissions}, Unmet Ratio={unmet_ratio}")
    return economic_cost, total_emissions

def constraints_func(trial):
    unmet_ratio = trial.user_attrs.get("unmet_ratio")
    if unmet_ratio is None:
        return [1.0] 
    return [unmet_ratio - 0.10]

def run_study(config_id: int, config_data, n_trials: int = 300, seed: int = 42, w: float = 1.0, storage_url: str = None, study_name: str = None):
    configuration = Configuration()
    configuration.import_nodes_from_csv(config_data)

    sampler = optuna.samplers.TPESampler(
        seed=seed,
        n_startup_trials=20,
        constraints_func=constraints_func
    )
    if storage_url is not None:
        study = optuna.create_study(direction="minimize", sampler=sampler, storage=storage_url, study_name=study_name)
    else:
        study = optuna.create_study(direction="minimize", sampler=sampler)

    study.optimize(lambda t: objective(t, configuration, w=w), n_trials=n_trials)

def parallel_config(all_config, config_data, n_trials: int = 300, max_workers: int = 8):
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor: 
        futures = {
            executor.submit(run_study, config_id, config_data, n_trials): config_id
            for config_id in enumerate(all_config)
        }
        for future in as_completed(futures): 
            config_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Configuration {config_id} generated an exception: {e}")

    final_results = pd.concat(results, ignore_index=True)
    return final_results

#%%
if __name__ == "__main__":
    import os
    import time
    from datetime import datetime
    from pathlib import Path
    import optuna
    from optuna.samplers import NSGAIISampler
    config = Configuration()

    config.import_nodes_from_csv("input/configurations/small_community_new.csv")
    # --- USER SETTINGS ---
    RESUME_STUDY = True  # Set to False to always start fresh
    # If resuming, specify the filename. If None, it creates a new one.
    db_to_resume = "MOO_isolated_20260422_093210.db" 

    # --- Setup Paths ---
    folder_name = "./output/optuna_results"
    os.makedirs(folder_name, exist_ok=True)

    # --- Study Logic ---
    sampler = NSGAIISampler(population_size=50, crossover_prob=0.9)

    file_path = os.path.join(folder_name, db_to_resume) if db_to_resume else None

    if RESUME_STUDY and file_path and os.path.exists(file_path):
        # --- RESUME EXISTING ---
        storage_url = f"sqlite:///{file_path}"
        summaries = optuna.get_all_study_summaries(storage=storage_url)
        
        if not summaries:
            print("File found but no study inside. Creating new instead...")
            # Fallback to creation logic
            study_name = f"study_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            study = optuna.create_study(directions=["minimize", "minimize"], storage=storage_url, study_name=study_name, sampler=sampler)
        else:
            study_name = summaries[0].study_name
            study = optuna.load_study(study_name=study_name, storage=storage_url, sampler=sampler)
            print(f"Successfully resumed study '{study_name}' from {db_to_resume}")
    else:
        # --- CREATE NEW ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_filename = f"MOO_OptimallyConnected_{timestamp}.db"
        storage_url = f"sqlite:///{os.path.join(folder_name, db_filename)}"
        study_name = f"study_{timestamp}"
        
        study = optuna.create_study(
            directions=["minimize", "minimize"], 
            storage=storage_url, 
            study_name=study_name, 
            sampler=sampler
        )
        print(f"Created new study: {study_name}")

    # --- Run Optimization ---
    start_time = time.time()
    study.optimize(lambda t: objective(t, config), n_trials=2000)
    end_time = time.time()

    print(f"Optimization completed in {end_time - start_time:.2f} seconds.")