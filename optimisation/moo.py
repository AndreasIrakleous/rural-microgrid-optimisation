"""
Multi Objective Optimization
"""
from datetime import datetime
from skeleton import *
from power_flow_edgeless import *
from power_flow import *
import optuna
from concurrent.futures import ProcessPoolExecutor, as_completed # For parallel execution
import time
import plotly.express as px

def economic_cost(pv_sum, battery_sum, edge_distance_sum, unmet_sum, unmet_max,profile_length=30*24,timeframe_years=20):
    """
    The cost function is a weighted sum of the prices of PV, battery, and unmet energy over a year.
    The prices depend on Gambia case study
    Args:
        pv_sum (float): sum of PV area per node 
        battery_sum (float): sum of battery capacity per node
        unmet_sum (float):  sum of unmet energy per node

    Returns:
        float: total cost
    
    Limitations:
        Does not consider the emission cost of energy sources.
    """
    timeframe_hours = timeframe_years * 365 * 24
    pv_capacity = 0.275 #kW
    pv_install = 95   # Price for the capacity of 0.275kW ($/kWp)
    pv_install = pv_install / pv_capacity  # Price per unit capacity of PV ($/kWp)
    pv_om =  (0.1 / pv_capacity) * timeframe_years# $/kWp/year (How to consider the cost over the timeframe?) From the size of load profile
    pv_cost_kwp = pv_install + pv_om  # $/kWp
    # Convert pv_price from from kwp to area
    panel_area = 0.15675 **2 * 60 # 60 solar cells per panel. 
    kwp_per_m2 = pv_capacity / panel_area  # kWp/m2
    pv_cost = pv_cost_kwp * kwp_per_m2 # Price per unit area of PV ($/m2) (64.4$/m2)

    #Battery
    battery_capacity = 3.1 # kWh
    battery_install = 280  # Price of battery kwh
    battery_install = battery_install / battery_capacity  # Price per unit capacity of battery ($/kWh)
    battery_om = 0.28 * timeframe_years    # $/kWh/year (How to consider the cost over the timeframe?)
    battery_cost = battery_install + battery_om  # $/kWh (90.3 $/kWh)

    #Diesel
    # Maximum capacity corresponds to the maximum unmet load
    d_generator = 400  # Price per unit capacity of diesel generator ($/kW)
    d_om = 0.02 * timeframe_years # $/kW/year 
    d_fuel = 1 # $/litre
    #d_fuel = 10000
    d_energy = 9.7 # kWh/litre
    d_fuel_kwh = d_fuel / d_energy  # $/kWh  (0.103 $/kWh)

    # Edge cost (estimate for now)
    edge_cost= 22000  # $/km (from GISEle article) (18500 euros / km for links)
    unmet_sum_extrapolated = (unmet_sum / profile_length) * timeframe_hours # Extrapolate unmet load to the whole timeframe
    #Debugging
    #print(f"PV Cost: {pv_cost}, Battery Cost: {battery_cost}, Diesel Cost per kWh: {d_fuel_kwh}, Diesel Generator Cost per kW: {d_generator}")
    diesel_cost = d_fuel_kwh * unmet_sum_extrapolated + (d_generator+ d_om )* unmet_max  # $/kWh
    #print(f"Diesel Cost: {diesel_cost}, Unmet Sum: {unmet_sum}, Unmet Max: {unmet_max}, edge distance sum: {edge_distance_sum}, pv_sum: {pv_sum}, battery_sum: {battery_sum}")
    #show cost of generator and fuel separately for debugging, smame for PV and battery
    cost_distribution = {
        "PV": pv_cost * pv_sum,
        "Battery": battery_cost * battery_sum,
        "Diesel Fuel": d_fuel_kwh * unmet_sum_extrapolated,
        "Diesel Generator": (d_generator+ d_om) * unmet_max,
        "Edges": edge_cost * edge_distance_sum
        
    }
    total_cost = pv_cost * pv_sum + battery_cost * battery_sum + diesel_cost + edge_cost * edge_distance_sum
    return total_cost, cost_distribution
def emission_cost(unmet_sum):
    """
    Calculate the emission cost based on the unmet energy.
    Args:
        unmet_sum (float): Total unmet energy in kWh.

    Returns:
        float: Emission cost in dollars.
    """
    emission_factor = 3.0 # kg CO2 / kWh 
    carbon_price = 57 # $/tonne CO2 (UKETS)

    total_emissions = emission_factor * unmet_sum / 1000  # Convert kg to tonnes
    total_cost = total_emissions * carbon_price
    return total_cost

def objective(trial, configuration: Configuration):
    """
    Objective function for the Bayesian optimizer.
    Args:
        trial (optuna.trial.Trial): Optuna trial object.
        configuration (Configuration): Configuration of nodes.

    Returns:
        float: total cost
    """
    # Suggest PV area and battery capacity for each node
    solar_map = {} # Dictionary node: solar area
    battery_map = {}
    
    node_list = list(configuration.nodes)
    #Initialise adjacency matrix for edges with node IDs using nested dict.
    # 2D dict comprehension.
    A = {u: {v: 0 for v in node_list} for u in node_list}


    for node in configuration.nodes:
        #Max area of solar from node:
        max_solar = configuration.nodes[node]["available_area"]
        max_battery = configuration.nodes[node]["battery_limit"]
        solar_area = trial.suggest_float(f"solar_{node}", 0, max_solar)  # Example range 
        battery_capacity = trial.suggest_int(f"battery_{node}", 0, max_battery)  # Example range (to be adjusted based on realistic limits)
        solar_map[node] = solar_area
        battery_map[node] = battery_capacity
    
    # Suggest edge connections between nodes (0 or 1)
    for i, u in enumerate(node_list):
        for j, v in enumerate(node_list):
            if i < j: # To avoid duplicate edges and self-loops
                edge_connection = trial.suggest_int(f"edge_{u}_{v}", 0, 1)
                A[u][v] = edge_connection
                A[v][u] = edge_connection
    
    # Update configuration edges based on suggested connections
    #print(f"Suggested adjacency matrix: {A}")
    configuration.adjacency_matrix(A) 
    #print(f"Edges after configuration: {configuration.edges()}") 
  
    # Configure assets
    configuration.bulk_configure_assets(
        battery_map=battery_map,
        solar_map=solar_map
    )
    # Get profiles dataframe
    profiles_df = configuration.get_profiles_dataframe()

    # Run power flow simulation
    # sim = MicrogridSimulator(configuration, delta_t=1, breakrate=0.0)
    # df, logs = sim.run(profiles_df)
    sim = MicrogridSimulator(configuration, delta_t=1)
    df, A = sim.run(profiles_df)

    #Calculate total edge distance:
    #print(f"Edges in configuration:{configuration.edges()}")
    edge_total= configuration.total_edge_distance()

    # Calculate costs
    pv_total = sum(solar_map.values())
    battery_total = sum(battery_map.values())
    unmet_total = df['unmet_load'].sum()
    unmet_max = df['unmet_load'].max()
    trial.set_user_attr("unmet_load", float(unmet_total)) # Store unmet load for analysis

    economic_cost_value, cost_distribution = economic_cost(pv_total, battery_total, edge_total, unmet_total, unmet_max)
    trial.set_user_attr("cost_distribution", cost_distribution) # Store cost distribution for analysis

    emission_cost_value = emission_cost(unmet_total)

    return economic_cost_value, emission_cost_value

if __name__ == "__main__":
    # Example usage
    # Create a configuration with 3 nodes and some edges
    config = Configuration()
    config.import_nodes_from_csv("configurations/small_community.csv")
    study = optuna.create_study(directions=["minimize", "minimize"])

    study.optimize(lambda t: objective(t, config), n_trials= 30) # Adjust n_trials and timeout as needed
    optuna.visualization.plot_pareto_front(study, target_names=["economic_cost_value", "emission_cost_value"]).show()

