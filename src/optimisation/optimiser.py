import optuna
from src.dispatch_strategy.simulator import MicrogridSimulator

def calculate_costs(pv_total, battery_total, unmet_total, unmet_max, peak_load, edge_distance, settings):
    """Calculates economic and emission costs based on trial results."""
    # Base parameters (you can move these to settings.json later)
    years = settings.get("study", {}).get("timeframe_years", 20)    
    # Simple Economic Math (Consolidated from your scripts)
    pv_cost = (95 / 0.275 + (0.1 / 0.275) * years) * pv_total 
    battery_cost = (280 / 3.1 + 0.28 * years) * battery_total
    edge_cost = 22000 * edge_distance
    
    # Diesel/Unmet Penalty
    diesel_fuel_kwh = 1 / 9.7
    diesel_cost = (diesel_fuel_kwh * unmet_total) + ((400 + 0.02 * years) * unmet_max)
    
    economic_cost = pv_cost + battery_cost + edge_cost + diesel_cost
    
    # Emission Math (kg CO2 -> tonnes)
    emission_factor = 3.0
    carbon_price = 57 
    emissions_tonnes = (emission_factor * unmet_total) / 1000
    emission_cost = emissions_tonnes * carbon_price
    
    return economic_cost, emissions_tonnes

def objective(trial, network, settings):
    """The core Optuna objective function."""
    solar_map = {}
    battery_map = {}
    
    # 1. Suggest Parameters
    for node in network.nodes:
        max_solar = network.nodes[node].get("available_area", 100)
        max_battery = network.nodes[node].get("battery_limit", 100)
        
        solar_map[node] = trial.suggest_float(f"solar_{node}", 0, max_solar)
        battery_map[node] = trial.suggest_int(f"battery_{node}", 0, max_battery)
        
    network.set_asset_capacities(battery_map=battery_map, solar_map=solar_map)

    topo_mode = settings.get("study", {}).get("active_topology", "isolated")
    if topo_mode == "optimal":
        # Generate the MST to find the candidate cables
        temp_net = network.copy()
        temp_net.minimum_spanning_tree()
        
        # Start with an isolated grid, then let Optuna choose which cables to build
        network.clear_edges()
        for u, v in temp_net.edges():
            # Optuna suggests 0 (don't build) or 1 (build)
            if trial.suggest_int(f"edge_{u}_{v}", 0, 1) == 1:
                network.add_edge(u, v)
    # -----------------------------------------------
    # 2. Run Simulation
    load_path = f"input/{settings['scenario_name']}/load.csv"
    pv_path = f"input/{settings['scenario_name']}/pv.csv"
    profiles_df = network.build_timeseries_dataframe(load_path, pv_path)
    
    sim = MicrogridSimulator(network, settings, delta_t=1)
    df, _, _, _, summary = sim.run(profiles_df)
    
    # 3. Calculate Costs
    edge_total = network.total_edge_distance()
    pv_total = sum(solar_map.values())
    battery_total = sum(battery_map.values())
    unmet_total = summary.get('total_unmet', 0)
    unmet_max = summary.get('unmet_peak_sum', 0)
    peak_load = summary.get('met_peak_sum', 0)
    
    eco_cost, emissions = calculate_costs(pv_total, battery_total, unmet_total, unmet_max, peak_load, edge_total, settings)
    
    # Store data for dashboard analysis
    trial.set_user_attr("unmet_load", float(unmet_total))
    trial.set_user_attr("economic_cost", eco_cost)
    trial.set_user_attr("emissions", emissions)
    
    # 4. Dynamic Return
    obj_mode = settings.get("study", {}).get("objective", "soo").lower()
    if obj_mode == "moo":
        return eco_cost, emissions
    else:
        return eco_cost
import os
from datetime import datetime
import optuna

def run_study(network, settings, n_trials=30):
    """Initializes and runs an Optuna study with strict hierarchical tagging."""
    study_cfg = settings.get("study", {})
    
    # 1. Determine Objective and Topology Types
    obj_mode = study_cfg.get("objective", "soo").lower()
    topo_mode = study_cfg.get("active_topology", "isolated").lower()
    directions = ["minimize", "minimize"] if obj_mode == "moo" else ["minimize"]
    
    # 2. Create Naming and Folder Structure
    scenario_name = settings.get("scenario_name", "default_scenario")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    study_name = f"{scenario_name}_{obj_mode}_{topo_mode}_{timestamp}"
    
    db_dir = os.path.join("output", scenario_name, "optimisation_histories", obj_mode)
    os.makedirs(db_dir, exist_ok=True)
    
    db_path = os.path.join(db_dir, f"{study_name}.db")
    storage_url = f"sqlite:///{os.path.abspath(db_path)}"
    
    # 3. Create and Run
    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url,
        load_if_exists=True,
        directions=directions
    )
    study.optimize(lambda t: objective(t, network, settings), n_trials=n_trials)
    
    print(f"Study saved to: {db_path}")
    return study