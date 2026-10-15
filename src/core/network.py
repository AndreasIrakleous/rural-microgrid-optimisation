import pandas as pd
import numpy as np
import networkx as nx
class MicrogridNetwork(nx.Graph):
    def load_nodes_from_csv(self, file_path):
        nodes_df = pd.read_csv(file_path)        
        self.graph['pos'] = {}
        for _, row in nodes_df.iterrows():
            # We only store the metadata/scaling factors in the node now
            # instead of the full arrays
            self.add_node(
                row['node_id'],
                coordinates=(row['latitude'], row['longitude']), #24 
                available_area=row['solar_area_m2'],
                profile_type=row['load_profile_type'],
                profile_scale_kwh_yr=row['load_profile_scale_kwh_yr'],
                battery_limit= row['battery_limit_kwh'],
                solar_panel_area=0.0,  # To be set later
                battery_capacity= row['battery_limit_kwh'],   # To be set later
                hydro_power= row['hydro_power_kW'],#kW of hydro power available at this node, if any
                deferable_load= row['deferable_load_kWh_day'] #kW of load that can be deferred at this node, if any
            )
            self.graph['pos'][row['node_id']] = (row['longitude'], row['latitude'])
    def set_asset_capacities(self, battery_map=None, solar_map=None):
        """
        Bulk updates nodes with battery capacities and solar panel areas.
        
        Args:
            battery_map (dict): {node_id: capacity_kwh}
            solar_map (dict): {node_id: panel_area_m2}
        """
        if battery_map:
            for node_id, capacity in battery_map.items():
                if node_id in self.nodes:
                    if capacity > self.nodes[node_id]['battery_limit']:
                        print(f"Warning: Node {node_id} battery capacity ({capacity} kWh) exceeds limit ({self.nodes[node_id]['battery_limit']} kWh).")
                    self.nodes[node_id]['battery_capacity'] = capacity
                else:
                    print(f"Warning: Node {node_id} not found. Skipping battery assignment.")

        if solar_map:
            for node_id, area in solar_map.items():
                if node_id in self.nodes:
                    # Check against the available_area defined during import
                    max_area = self.nodes[node_id].get('available_area', float('inf'))
                    if area > max_area:
                        print(f"Warning: Node {node_id} solar area ({area}) exceeds available ({max_area}).")
                    
                    self.nodes[node_id]['solar_panel_area'] = area
                else:
                    print(f"Warning: Node {node_id} not found. Skipping solar assignment.")
    def build_timeseries_dataframe(self, load_profiles_file="input/load_profiles/case_study_load.csv", irradiance_profile_file="input/PV_profiles_files/case_study_pv.csv"):
        """
        Generates a long-format DataFrame with time, node, and various quantity dimensions.
        """
        solar_efficiency = 1
        load_profiles_df = pd.read_csv(load_profiles_file)
        irradiance_profiles_df = pd.read_csv(irradiance_profile_file)

        # Normalize load profiles
        for col in load_profiles_df.columns:
            if col != "time":
                load_profiles_df[col] = load_profiles_df[col] / load_profiles_df[col].sum()

        all_records = []
        timesteps = load_profiles_df['time'].values

        for node_id, node_data in self.nodes(data=True):
            # Calculate the specific profiles for this node
            scale_hour = node_data['profile_scale_kwh_yr']/365/24 # Scale from yearly kWh to hourly kW
            area = node_data['solar_panel_area']
            
            load_values = load_profiles_df[node_data['profile_type']].values *scale_hour*len(timesteps) # Scale the normalized profile to the actual load in kW
            pv_values = irradiance_profiles_df['power_out(kWh)'].values * area 
            # Create a block of data for this node
            for i, t in enumerate(timesteps):
                all_records.append({
                    'time': t,
                    'node_id': node_id,
                    'load_profile': load_values[i],
                    'pv_profile': pv_values[i],
                    'battery_SOC': 0.0,  # Placeholder
                    'hydro_power': node_data.get('hydro_power', 0.0), # Add hydro power to the record
                    'deferable_load': node_data.get('deferable_load', 0.0) # Add deferable load to the record
                })

        # Create the DataFrame
        all_records.sort(key=lambda x: x['time'])
        df = pd.DataFrame(all_records)
        df['time'] = pd.to_numeric(df['time'])  # Ensure time is numeric
        return df   
    def adjacency_matrix(self, A):
        """
        Update edges to a graph using an adjacnency matrix 
        The adjancency matrix is a nested 2D dictionary.
        Returns:
            An updated graph from a given adjacency matrix
        """
        for u in A:
            for v in A[u]:
                if A[u][v] != 0:
                    self.add_edge(u, v)
                if A[v][u] == 0:
                    if self.has_edge(v, u):
                        self.remove_edge(v, u)
        return self
    def haversine_distance(self, u, v):
        R = 6371.0
        coord_u = self.nodes[u]['coordinates']
        coord_v = self.nodes[v]['coordinates'] # (lat, lon)
        lat1 = np.radians(coord_u[0]) # from degrees to radians
        lon1 = np.radians(coord_u[1])
        lat2 = np.radians(coord_v[0])
        lon2 = np.radians(coord_v[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        distance = R * c
        return distance
    def total_edge_distance(self):
        total_distance = 0.0
        for u, v in self.edges():
            total_distance += self.haversine_distance(u, v)
        return total_distance
    def minimum_spanning_tree(self, weight_attr: str = "weight"):
        """
        Returns an MST that connects ALL nodes, even if the current graph has no edges,
        by building a complete weighted graph using Haversine distances.
        """
        G = nx.Graph()
        G.add_nodes_from(self.nodes(data=True))  # preserves node attributes

        nodes = list(G.nodes())
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                G.add_edge(u, v, **{weight_attr: self.haversine_distance(u, v)})

        mst = nx.minimum_spanning_tree(G, weight=weight_attr, algorithm="kruskal")
        # Extract the adjacency matrix from the MST
        A = {u: {v: 0 for v in G.nodes()} for u in G.nodes()}   
        for u, v in mst.edges():
            A[u][v] = 1
            A[v][u] = 1
        self.adjacency_matrix(A)
    def import_trial_params(self,best_params):
        self.set_asset_capacities(
        battery_map={node: best_params[f"battery_{node}"] for node in self.nodes},
        solar_map={node: best_params[f"solar_{node}"] for node in self.nodes})                                               
        #read all adges from best_params and add to graph
        for key, value in best_params.items():
            if key.startswith("edge_") and value == 1:
                _, u, v = key.split("_")
                self.add_edge(u, v)
    def clear_edges(self):
        """Removes all edges to create an isolated topology."""
        self.remove_edges_from(list(self.edges()))     
