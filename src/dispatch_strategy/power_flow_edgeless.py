#%% Microgrid simulator class
import pandas as pd
import numpy as np
import networkx as nx
import random
import os
import platform
from src.main import *

class MicrogridSimulator:
    def __init__(self, graph, delta_t, breakrate=0.0, seed=2):
        self.graph = graph
        self.delta_t = delta_t
        self.breakrate = breakrate
        self.seed = seed
        self.broken_edges_log = []
        random.seed(self.seed)
        self.subgraphs = list(nx.connected_components(self.graph))
        
        # Enforce strict alphabetical order to prevent data columns from swapping between nodes
        self.node_ids = sorted(list(self.graph.nodes()))

    def _apply_edge_breakage(self, t):
        """Stochastically removes edges and logs the event."""
        for edge in list(self.graph.edges()):
            rand_val = random.random()
            if rand_val < self.breakrate:
                self.graph.remove_edge(*edge)
                self.broken_edges_log.append([edge, t, rand_val])

    def _distribute_proportional(self, sub_df, mask_givers, mask_receivers, supply_col, demand_col):
        """
        Generalized logic to move energy from 'givers' to 'receivers'.
        Handles both Peer-to-Peer transfer and Storage redistribution.
        """
        total_supply = sub_df.loc[mask_givers, supply_col].abs().sum()
        total_demand = sub_df.loc[mask_receivers, demand_col].abs().sum()

        if total_supply <= 1e-9 or total_demand <= 1e-9:
            return pd.Series(0.0, index=sub_df.index), pd.Series(0.0, index=sub_df.index)

        moved_amount = min(total_supply, total_demand)
        give_ratio = moved_amount / total_supply
        rec_ratio = moved_amount / total_demand

        change_givers = -sub_df.loc[mask_givers, supply_col] * give_ratio
        change_receivers = sub_df.loc[mask_receivers, demand_col].abs() * rec_ratio
        
        return change_givers, change_receivers

    def run(self, df):
        # Pre-cache battery capacities from the Graph
        caps = pd.Series({n: self.graph.nodes[n].get('battery_capacity', 0) for n in self.graph.nodes()})
        
        result_cols = ['net','change_1', 'net_2', 'excess_energy', 'change_2','net_3',
                       'discarded_energy','net_4', 'unmet_load','discarded_energy_pv','discarded_energy_hydro']
        
        for col in result_cols:
            df[col] = 0.0

        unique_times = sorted(df["time"].unique())
        time0_mask = df["time"] == 0
        for node in df.loc[time0_mask, 'node_id']:
            df.loc[time0_mask & (df['node_id'] == node), 'battery_SOC'] = caps[node]
            
        for t in unique_times:
            self._apply_edge_breakage(t)
            mask = df["time"] == t
            t_df = df[mask].copy().set_index("node_id")

            t_df['net'] = (t_df['pv_profile'] + t_df['battery_SOC']) - t_df['load_profile']

            for component_nodes in nx.connected_components(self.graph):
                sub = t_df.loc[list(component_nodes)].copy()
                node_caps = caps.reindex(sub.index)

                # Phase 1: Peer-to-Peer Transfer
                give_1, rec_1 = self._distribute_proportional(
                    sub, sub['net'] >= 0, sub['net'] < 0, 'net', 'net'
                )
                sub['change_1'] = give_1.add(rec_1, fill_value=0)
                sub['net_2'] = sub['net'] + sub['change_1']
                sub['unmet_load'] = sub['net_2'].apply(lambda x: abs(x) if x < 0 else 0)

                # Phase 2: Storage Redistribution
                sub['excess_energy'] = -node_caps + sub['net_2']
                excess_mask = sub['excess_energy'] > 0
                room_mask = sub['excess_energy'] < 0
                
                give_2, rec_2 = self._distribute_proportional(
                    sub, excess_mask, room_mask, 'excess_energy', 'excess_energy'
                )
                sub['change_2'] = give_2.add(rec_2, fill_value=0)
                sub['net_3'] = sub['net_2'] + sub['change_2']
                
                discarded = (sub['net_3'] - node_caps).clip(lower=0)
                sub['discarded_energy'] = discarded
                sub['net_4'] = sub['net_3'].clip(upper=node_caps,lower=0)

                t_df.update(sub)

            # Write time-step results back safely using mapping
            for col in t_df.columns:
                df.loc[mask, col] = df.loc[mask, 'node_id'].map(t_df[col])

            next_mask = df["time"] == (t + self.delta_t)
            if any(next_mask):
                df.loc[next_mask, 'battery_SOC'] = df.loc[next_mask, 'node_id'].map(t_df['net_4'])
                
        df['energy_used'] = 0.0
        for node in df['node_id'].unique():
            node_df = df[df['node_id'] == node].copy()
            for i in range(1, len(node_df)):
                prev_soc = node_df.iloc[i-1]['battery_SOC']
                curr_soc = node_df.iloc[i]['battery_SOC']
                if curr_soc < prev_soc:
                    df.loc[node_df.index[i], 'energy_used'] = prev_soc - curr_soc
        return df, self.broken_edges_log

    def run_periodic(self, profile_df):
        caps = pd.Series({n: self.graph.nodes[n].get('battery_capacity', 0) for n in self.graph.nodes()})
        deferable_init = pd.Series({n: self.graph.nodes[n].get('deferable_load', 0) for n in self.graph.nodes()})
        print("Deferrable load targets:")
        print(deferable_init)
        unique_times = sorted(profile_df["time"].unique())
        nodes = profile_df["node_id"].unique()
        
        current_iteration_initial_SOC = caps.copy() * 0
        
        max_iterations = 200
        tolerance = 0.01
        df_list = []
        iteration = 0
        
        while iteration < max_iterations:
            if iteration == 5:
                for node in nodes:
                    current_iteration_initial_SOC[node] = caps[node]
            df = profile_df.copy()
            
            for col in ['net','change_1', 'net_2', 'excess_energy', 'change_2','net_3',
                       'discarded_energy','net_4', 'unmet_load', 'battery_SOC', 'potentially_discarded_energy', 
                       'discarded_energy_pv','discarded_energy_hydro','remaining_deferable', 'met_deferable_load',"unmet_deferable_load"]:
                df[col] = 0.0

            time0_mask = df["time"] == unique_times[0]
            df.loc[time0_mask, 'remaining_deferable'] = df.loc[time0_mask, 'node_id'].map(deferable_init)
            for node in nodes:
                df.loc[time0_mask & (df['node_id'] == node), 'battery_SOC'] = current_iteration_initial_SOC[node]

            # --- Run Simulation ---
            for i, t in enumerate(unique_times):
                mask = df["time"] == t
                t_df = df[mask].copy().set_index("node_id")
                
                self._apply_edge_breakage(t)
                t_df['net'] = (t_df['pv_profile'] + t_df['battery_SOC'] + t_df['hydro_power']) - t_df['load_profile']

                for component_nodes in nx.connected_components(self.graph):
                    sub = t_df.loc[list(component_nodes)].copy()
                    node_caps = caps.reindex(sub.index)

                    # Peer-to-Peer
                    give_1, rec_1 = self._distribute_proportional(sub, sub['net'] >= 0, sub['net'] < 0, 'net', 'net')
                    sub['change_1'] = give_1.add(rec_1, fill_value=0)
                    sub['net_2'] = sub['net'] + sub['change_1']
                    sub['unmet_load'] = sub['net_2'].apply(lambda x: abs(x) if x < 0 else 0)

                    # Storage Redistribution
                    sub['excess_energy'] = sub['net_2'] - node_caps
                    give_2, rec_2 = self._distribute_proportional(sub, sub['excess_energy'] > 0, sub['excess_energy'] < 0, 'excess_energy', 'excess_energy')
                    sub['change_2'] = give_2.add(rec_2, fill_value=0)
                    sub['net_3'] = sub['net_2'] + sub['change_2']
                
                    sub['potentially_discarded_energy'] = (sub['net_3'] - node_caps).clip(lower=0)

                    # Deferrable Loads
                    give_def, rec_def = self._distribute_proportional(
                        sub, 
                        sub['potentially_discarded_energy'] > 0, 
                        sub['remaining_deferable'] > 0, 
                        'potentially_discarded_energy', 
                        'remaining_deferable'
                    ) 
                    
                    sub['met_deferable_load'] = rec_def.abs().reindex(sub.index, fill_value=0.0)
                    sub['discarded_energy'] = sub['potentially_discarded_energy'].add(give_def, fill_value=0.0)
                    sub['remaining_deferable'] = sub['remaining_deferable'] - sub['met_deferable_load']

                    sub['discarded_energy_pv'] = sub['discarded_energy'] * (sub['pv_profile'] / (sub['pv_profile'] + sub['hydro_power'] + 1e-6))
                    sub['discarded_energy_hydro'] = sub['discarded_energy'] * (sub['hydro_power'] / (sub['pv_profile'] + sub['hydro_power'] + 1e-6))
                    
                    sub['net_4'] = sub['net_3'].clip(upper=node_caps, lower=0)
                    t_df.update(sub)

                for col in t_df.columns:
                    df.loc[mask, col] = df.loc[mask, 'node_id'].map(t_df[col])

                # Carry SOC and deferrable forward
                if i + 1 < len(unique_times):
                    next_t = unique_times[i+1]
                    next_mask = df["time"] == next_t
                    df.loc[next_mask, 'battery_SOC'] = df.loc[next_mask, 'node_id'].map(t_df['net_4'])
                    df.loc[next_mask, 'remaining_deferable'] = df.loc[next_mask, 'node_id'].map(t_df['remaining_deferable'])

            final_t = unique_times[-1]
            final_mask = df["time"] == final_t
            
            for node in nodes:
                remaining = df.loc[final_mask & (df['node_id'] == node), 'remaining_deferable'].iloc[0]
                if remaining > 0.01:
                    hourly_unmet = remaining / len(unique_times)
                    node_mask = df['node_id'] == node
                    df.loc[node_mask, 'unmet_deferable_load'] = hourly_unmet
                    
            final_SOC_series = df[df['time'] == unique_times[-1]].set_index('node_id')['net_4']
            diff = (final_SOC_series - current_iteration_initial_SOC).abs().max()
            
            print(f"Iteration {iteration}: Max SOC diff = {diff:.4f}")
            df_list.append(df.copy())

            if diff < tolerance:
                break
            
            current_iteration_initial_SOC = final_SOC_series
            iteration += 1

        df['energy_used'] = 0.0
        for node in nodes:
            node_mask = df['node_id'] == node
            sim_rows = df[node_mask]
            SOC_before = sim_rows['battery_SOC'].shift(1).fillna(sim_rows['battery_SOC'])
            SOC_after = sim_rows['battery_SOC']
            energy_used = SOC_before - SOC_after
            energy_used[energy_used < 0] = 0 
            df.loc[node_mask, 'energy_used'] = energy_used

       # --- Final Subgraph and Community Analysis ---
        subgraph_reports = []
        unmet_peak_sum = 0.0
        met_peak_sum = 0.0
        total_unmet = 0.0

        for idx, component_nodes in enumerate(nx.connected_components(self.graph)):
            sub_mask = df['node_id'].isin(component_nodes)
            sub_df = df[sub_mask].copy()
            
            hourly_stats = sub_df.groupby('time').apply(lambda x: pd.Series({
                'met_profile': (x['load_profile'] - x['unmet_load']).sum() + x['met_deferable_load'].sum(),
                'unmet_profile': x['unmet_load'].sum() + x['unmet_deferable_load'].sum()
            }))
            
            met_prof = hourly_stats['met_profile'].values.tolist()
            unmet_prof = hourly_stats['unmet_profile'].values.tolist()
            
            sub_energy_met = sum(met_prof)
            sub_energy_unmet = sum(unmet_prof)
            sub_peak_met = max(met_prof) if met_prof else 0.0
            sub_peak_unmet = max(unmet_prof) if unmet_prof else 0.0
            
            unmet_peak_sum += sub_peak_unmet
            met_peak_sum += sub_peak_met
            total_unmet += sub_energy_unmet
            
            subgraph_reports.append({
                'subgraph_index': idx,
                'nodes': list(component_nodes),
                'profiles': {
                    'total_met_load_profile': met_prof,
                    'total_unmet_load_profile': unmet_prof
                },
                'metrics': {
                    'total_energy_met_kwh': sub_energy_met,
                    'total_energy_not_met_kwh': sub_energy_unmet,
                    'peak_met_kw': sub_peak_met,
                    'peak_unmet_kw': sub_peak_unmet
                }
            })

        community_summary = {"unmet_peak_sum": unmet_peak_sum, "met_peak_sum": met_peak_sum, "total_unmet": total_unmet}

        return df, self.broken_edges_log, df_list, subgraph_reports, community_summary

    def profile_visualiser(self, df, subgraph):
        subgraph_mask = df['node_id'].isin(subgraph)
        subgraph_df = df[subgraph_mask].copy()
        subgraph_summary = subgraph_df.groupby('time').agg({
            'load_profile': 'sum',
            'pv_profile': 'sum',
            'hydro_power': 'sum',
            'battery_SOC': 'sum',
            'energy_used': 'sum',
            'net': 'sum',
            'net_2': 'sum',
            'net_3': 'sum',
            'net_4': 'sum',
            'unmet_load': 'sum',
            'discarded_energy': 'sum'
        }).reset_index()
        
        subgraph_summary['met_load'] = subgraph_summary['load_profile'] - subgraph_summary['unmet_load']
        subgraph_summary['contribution'] = subgraph_summary['pv_profile'] + subgraph_summary['hydro_power'] + subgraph_summary['energy_used']
        
        import matplotlib.pyplot as plt
        plt.figure(figsize=(12, 6))
        plt.bar(subgraph_summary['time'], subgraph_summary['load_profile'], label='Load Profile', color='red', alpha=0.5)
        plt.bar(subgraph_summary['time'], subgraph_summary['contribution'], label='Energy provided', color='blue', alpha=0.5)
        plt.bar(subgraph_summary['time'], subgraph_summary['discarded_energy'], label=' Discarded Energy',color='green', alpha=0.5)
 
        plt.xlabel('Time')
        plt.ylabel('Energy (kWh)')
        plt.title('Energy Profile for Subgraph')
        plt.legend()
        plt.show()
        return subgraph_summary
        
# %%  Methods for exporting and analyzing results
def export_and_open(df, open_file=False):
    """
    Open dataframe in .csv
    """
    file_path = 'power_flow_output.csv'
    df.to_csv(file_path, index=False)
    if open_file:
        if platform.system() == 'Darwin': os.system(f'open "{file_path}"')
        elif platform.system() == 'Windows': os.startfile(file_path)
        else: os.system(f'xdg-open "{file_path}"')

def energy_distribution(df):
    """
    Total energy distribution for a simulation.
    Used for the pie chart.
    """
    batteries = df['energy_used'].sum()
    unmet_load = df['unmet_load'].sum()
    total_load = df['load_profile'].sum()
    hydro_power_sum = df['hydro_power'].sum() - df['discarded_energy_hydro'].sum()
    pv_contributed = df['pv_profile'].sum() - df['discarded_energy_pv'].sum()
    
    return {
        "batteries": batteries,
        "unmet_load": unmet_load,
        "hydro_power": hydro_power_sum,
        "pv_contributed": pv_contributed
    }
    
#%% Main execution block
if __name__ == "__main__":
    import os
    if not os.path.exists("output"):
        os.makedirs("output")
        
    example_config = Configuration()
    example_config.import_nodes_from_csv("Ethiopia_case_study.csv")
    
    # Toggle connection state:
    # To run as a connected microgrid, keep this uncommented
    example_config.minimum_spanning_tree()
    
    # To run as unconnected/standalone, uncomment the following line instead:
    # example_config.clear_edges()
    
    # Configure assets dynamically from the Ethiopia case study CSV
    eth_df = pd.read_csv("Ethiopia_case_study.csv")
    solar_map = dict(zip(eth_df['node_id'], eth_df['solar_area_m2']))
    battery_map = dict(zip(eth_df['node_id'], eth_df['battery_limit_kwh']))
    example_config.bulk_configure_assets(battery_map=battery_map, solar_map=solar_map)
    
    profiles_df = example_config.get_profiles_dataframe(
        load_profiles_file="case_study_load.csv", 
        irradiance_profile_file="case_study_pv.csv"
    )
    
    print("Graph Edges:", list(example_config.edges()))
    sim = MicrogridSimulator(example_config, delta_t=1)
    df, broken_edges, df_list, report, summary = sim.run_periodic(profiles_df)
    
    # Save df
    df.to_csv("output/Ethiopia_sim_output.csv", index=False)
    print("\nSimulation Summary:")
    print(summary)