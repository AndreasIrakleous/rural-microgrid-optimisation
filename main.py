"""
Author: Ismail Abdelmonem & Andreas Irakleous
Date: 23 October 2025

This module serves as a skeleton template for the MSci project.

Question of the project: 
    To what extent does electricity sharing reduce cost and emissions in rural areas while maintaining reliability?


"""
# --- Import Libraries ---
# Use pandas for handling time series data (loads, solar irradiance)
import pandas as pd
# Use numpy for numerical operations
import numpy as np
# --- Placeholder for Optimization Library ---
# You will need a library like Pyomo, CVXPY, or PuLP to define
import matplotlib.pyplot as plt
import networkx as nx
import json
import plotly.graph_objects as go # Use Plotly for interactive plots
import plotly.express as px
import os # To get file paths
import webbrowser # To open the plot in a browser

class Configuration(nx.Graph):
    def import_nodes_from_csv(self, file_path):
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
    def bulk_configure_assets(self, battery_map=None, solar_map=None):
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
    def get_profiles_dataframe(self, load_profiles_file="input/load_profiles/case_study_load.csv", irradiance_profile_file="input/PV_profiles_files/case_study_pv.csv"):
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
    def save_graph_json(self,filepath):
        data_to_save = nx.readwrite.json_graph.node_link_data(self, edges="edges")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)
    def import_graph_json(self, filepath):
        """
        Imports a graph from a JSON file and populates the current graph instance (self).
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        imported_graph = nx.readwrite.json_graph.node_link_graph(data, directed=True, multigraph=True,edges="edges")
        
        # Clear current graph and update with imported data
        self.clear()
        self.add_nodes_from(imported_graph.nodes(data=True))
        self.add_edges_from(imported_graph.edges(data=True))
        
        # Copy graph-level attributes
        self.graph.update(imported_graph.graph)
    def graph_plot(self, filename="configuration_graph.html", df=None, 
                   size_metric="load_profile", 
                   color_metric=lambda row: row['pv_profile'] / row['load_profile'] if row['load_profile'] != 0 else 0,
                   size_range=(20, 70),
                   colorscale="RdYlGn",
                   color_label="PV/ Load"):
        """
        Plot an animated graph with customizable node size and color metrics.
        
        Parameters:
            filename (str): Output HTML filename
            df (pd.DataFrame): Dataframe with time-series data for nodes
            size_metric (str or callable): Column name or function(row) -> float for node size
            color_metric (str or callable): Column name or function(row) -> float for node color
            size_range (tuple): (min_size, max_size) for node markers
            colorscale (str): Plotly colorscale name (e.g., 'RdYlGn', 'Viridis', 'Turbo')
            color_label (str): Label for the colorbar
        
        Examples:
            # Size by load, color by PV
            config.graph_plot(df=df, size_metric="load_profile", color_metric="pv_profile")
            
            # Size by load, color by energy ratio
            config.graph_plot(df=df, size_metric="load_profile", 
                            color_metric=lambda row: row['net_energy_local'] / row['load_profile'] if row['load_profile'] != 0 else 0)
        """
        G = self
        if df is None:
            print("Error: graph_plot requires a dataframe with time-varying load and pv data.")
            return None, None

        print(f"Generating animated graph plot and saving to {filename}...")

        pos = G.graph.get('pos')
        if pos is None:
            print("Error: 'pos' data not found in G.graph. Cannot plot.")
            return None, None

        # Fix axis ranges so the view does not jump between frames
        xs = [coord[0] for coord in pos.values()]
        ys = [coord[1] for coord in pos.values()]
        if not xs or not ys:
            print("Error: no coordinates available to set axis ranges.")
            return None, None
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        pad_x = 0.05 * x_span if x_span != 0 else 0.01
        pad_y = 0.05 * y_span if y_span != 0 else 0.01
        x_range = [min(xs) - pad_x, max(xs) + pad_x]
        y_range = [min(ys) - pad_y, max(ys) + pad_y]

        times = sorted(df["time"].unique())
        if not times:
            print("Error: dataframe has no time values.")
            return None, None
        
        # Helper function to extract metric values from dataframe
        def get_metric_value(row, metric):
            """Extract value from row using either column name or callable."""
            if callable(metric):
                return float(metric(row))
            else:
                return float(row[metric])
        
        # Compute size and color values for all rows
        df['_size_val'] = df.apply(lambda row: get_metric_value(row, size_metric), axis=1)
        df['_color_val'] = df.apply(lambda row: get_metric_value(row, color_metric), axis=1)
        
        # Get global min/max for consistent scaling
        size_min, size_max = float(df['_size_val'].min()), float(df['_size_val'].max())
        color_min, color_max = float(df['_color_val'].min()), float(df['_color_val'].max())
        
        if size_max == size_min:
            size_min, size_max = size_min - 1.0, size_max + 1.0
        if color_max == color_min:
            color_min, color_max = color_min - 1.0, color_max + 1.0
        
        # Diverging colorscale: red at -1, white at 0, green at 1, blue beyond 1 (non-symmetric)
        applied_colorscale = colorscale
        if color_max > 0:  # Only apply diverging palette when positives exist
            color_min = min(-1.0, color_min)  # Force lower bound to at least -1
            span = color_max - color_min if color_max != color_min else 1.0
            zero_pos = (0 - color_min) / span  # Position of zero in the colorscale
            one_pos = (1 - color_min) / span   # Position of value 1 in the colorscale

            # Clamp positions into [0,1]
            zero_pos = max(0.0, min(1.0, zero_pos))
            one_pos = max(zero_pos, min(1.0, one_pos))

            # Smooth red -> white -> green -> blue
            applied_colorscale = [
                [0.0, "#b2182b"],                    # deep red at min (-1)
                [max(0.0, zero_pos * 0.6), "#f4b6a6"],
                [zero_pos, "#ffffff"],                # white at 0
                [min(1.0, zero_pos + (one_pos - zero_pos) * 0.4), "#dff4e4"],
                [one_pos, "#1b8a3c"],                 # green at 1
                [min(1.0, one_pos + (1 - one_pos) * 0.35), "#3f7fbf"],
                [1.0, "#1c4fad"]                     # blue at top
            ]

        # Static edge trace (does not change over time)
        edge_x = []
        edge_y = []
        for edge_nodes in G.edges():
            x0, y0 = pos[edge_nodes[0]]
            x1, y1 = pos[edge_nodes[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x,
            y=edge_y,
            line=dict(width=2, color="#888"),
            hoverinfo="none",
            mode="lines"
        )

        node_ids_list = []
        node_x = []
        node_y = []
        node_symbols = []
        node_hover_static = {}  # Hover info that does not change over time

        shape_map = {
            "house": "circle",
            "commercial": "square",
            "farm": "diamond",
            "hospital": "cross",
            "school": "star",
            "water_pump": "triangle-up",
            "default": "circle"
        }

        load_min = float(df["load_profile"].min())
        load_max = float(df["load_profile"].max())
        
        # Compute net_energy_local/load_profile ratio for coloring
        if 'net_energy_local' in df.columns:
            df['energy_ratio'] = df.apply(lambda row: row['net_energy_local'] / row['load_profile'] if row['load_profile'] != 0 else 0, axis=1)
            ratio_min = float(df['energy_ratio'].min())
            ratio_max = float(df['energy_ratio'].max())
        else:
            # Fallback to pv_profile if net_energy_local not available
            df['energy_ratio'] = df['pv_profile']
            ratio_min = float(df['pv_profile'].min())
            ratio_max = float(df['pv_profile'].max())
        
        if load_max == load_min:
            load_min, load_max = load_min - 1.0, load_max + 1.0
        if ratio_max == ratio_min:
            ratio_min, ratio_max = ratio_min - 1.0, ratio_max + 1.0

        # Precompute static node fields
        for node_id, data in G.nodes(data=True):
            coords = data.get("coordinates", (0, 0))
            coord_str = f"Coords: ({coords[0]:.4f} lat, {coords[1]:.4f} lon)"
            tech_info = (
                f"Solar: {data.get('solar_panel_area', 0):.1f} m², "
                f"Battery: {data.get('battery_capacity', 0):.1f} kWh"
            )
            node_hover_static[node_id] = (
                f"<b>{node_id} ({data.get('profile_type', 'N/A')})</b><br>"
                f"{coord_str}<br>"
                f"Installed: {tech_info}"
            )
            node_ids_list.append(node_id)
            node_x.append(pos[node_id][0])
            node_y.append(pos[node_id][1])
            node_symbols.append(shape_map.get(data.get("profile_type"), shape_map["default"]))

        def build_trace_for_time(timestep, include_colorbar=False):
            sizes = []
            colors = []
            hover_texts = []
            rows_at_time = df[df["time"] == timestep]

            def scale_size(size_value):
                return float(np.interp(size_value, [size_min, size_max], size_range))

            for node_id in node_ids_list:
                row = rows_at_time[rows_at_time["node_id"] == node_id]
                if row.empty:
                    size_val = size_min
                    color_val = color_min
                else:
                    size_val = float(row["_size_val"].iloc[0])
                    color_val = float(row["_color_val"].iloc[0])
                
                sizes.append(scale_size(size_val))
                colors.append(color_val)
                
                # Build hover text with dynamic metrics
                hover_info = f"{node_hover_static[node_id]}<br>"
                if not row.empty:
                    # Add common metrics if available
                    for col in ['load_profile', 'pv_profile', 'net_energy_local', 'battery_SOC']:
                        if col in row.columns:
                            val = float(row[col].iloc[0])
                            hover_info += f"{col.replace('_', ' ').title()}: {val:.2f}<br>"
                hover_texts.append(hover_info.rstrip('<br>'))

            marker_kwargs = dict(
                size=sizes,
                color=colors,
                symbol=node_symbols,
                colorscale=applied_colorscale,
                cmin=color_min,
                cmax=color_max,
                line_width=2,
                showscale=include_colorbar,
                colorbar=dict(title=color_label, ticks="outside") if include_colorbar else None,
            )
            if marker_kwargs["colorbar"] is None:
                marker_kwargs.pop("colorbar")

            return go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                hoverinfo="text",
                text=node_ids_list,
                textposition="top center",
                marker=marker_kwargs,
                hovertext=hover_texts,
                name=str(timestep)
            )

        initial_trace = build_trace_for_time(times[0], include_colorbar=True)

        frames = []
        for t in times:
            frames.append(
                go.Frame(
                    name=str(t),
                    data=[edge_trace, build_trace_for_time(t, include_colorbar=True)],
                )
            )

        sliders = [
            dict(
                active=0,
                currentvalue={"prefix": "Time: "},
                steps=[
                    dict(method="animate", args=[[str(t)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}], label=str(t))
                    for t in times
                ],
            )
        ]

        fig = go.Figure(
            data=[edge_trace, initial_trace],
            layout=go.Layout(
                title="Energy Community Over Time",
                font_size=16,
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(title="Longitude", showgrid=False, zeroline=False, range=x_range, fixedrange=True),
                yaxis=dict(title="Latitude", showgrid=False, zeroline=False, range=y_range, fixedrange=True),
                updatemenus=[
                    dict(
                        type="buttons",
                        showactive=False,
                        x=0.05,
                        y=1.15,
                        buttons=[
                            dict(label="Play", method="animate", args=[None, {"frame": {"duration": 800, "redraw": True}, "fromcurrent": True}]),
                            dict(label="Pause", method="animate", args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]),
                        ],
                    )
                ],
                sliders=sliders,
            ),
            frames=frames,
        )

        fig.write_html(filename)
        webbrowser.open('file://' + os.path.realpath(filename))
        return fig, filename

    def plot_assets_px(self, filename="configuration_assets.html"):
        """
        Plot an interactive static view of the configuration using Plotly Express.
        - Node size: Battery capacity (kWh)
        - Node color: PV area (m²)
        - Node shape: Profile type
        - Dimensions: A5 (Landscape)
        - Font Size: 24pt
        """
        G = self
        pos = G.graph.get('pos')
        if not pos:
            # Fallback: derive from stored coordinates (lon, lat)
            pos = {}
            for nid, data in G.nodes(data=True):
                coords = data.get('coordinates', (0.0, 0.0))
                pos[nid] = (coords[1], coords[0])
            G.graph['pos'] = pos

        # Calculate plot ranges
        xs = [coord[0] for coord in pos.values()]
        ys = [coord[1] for coord in pos.values()]
        if not xs or not ys:
            print("Error: No coordinates available to plot.")
            return None, None

        # Shape map matching your requirements
        shape_map = {
            "house": "circle",
            "commercial": "square",
            "farm": "diamond",
            "hospital": "cross",
            "school": "star",
            "water_pump": "triangle-up",
            "default": "circle-dot",
        }

        # Build node records
        node_records = []
        for nid, data in G.nodes(data=True):
            lon, lat = pos[nid]
            p_type = data.get('profile_type', 'default')
            node_records.append({
                'node_id': nid,
                'lon': lon,
                'lat': lat,
                'battery_capacity': float(data.get('battery_capacity', 1.0)), # Ensure > 0 for sizing
                'solar_panel_area': float(data.get('solar_panel_area', 0.0)),
                'profile_type': p_type if p_type in shape_map else 'default',
            })

        nodes_df = pd.DataFrame(node_records)

        # Create the base scatter plot
        # size_max=80 ensures the bubbles look proportional to the 24pt font
        fig = px.scatter(
            nodes_df,
            x='lon',
            y='lat',
            size='battery_capacity',      # Reference the column name string
            color='solar_panel_area',
            symbol='profile_type',
            symbol_map=shape_map,
            size_max=80,                  
            color_continuous_scale='Viridis',
            hover_name='node_id',
            hover_data={'battery_capacity': True, 'solar_panel_area': True, 'lon': ':.4f', 'lat': ':.4f'}
        )

        # Build edge trace (drawn first so it appears behind nodes)
        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            mode='lines',
            line=dict(color='black', width=2),
            hoverinfo='none',
            showlegend=False
        )

        # Combine: Clear and re-add in order (Edges -> Nodes)
        nodes_traces = list(fig.data)
        fig.data = [] 
        fig.add_trace(edge_trace)
        for tr in nodes_traces:
            fig.add_trace(tr)

        # Final Layout Styling for A5 and 24pt Font
        fig.update_layout(
            title='Configuration Map',
            width=560,   # A5 Landscape Width (px)
            height=560,  # A5 Landscape Height (px)
            
            # Global Font Setting
            font=dict(size=24, family="Arial", color="black"),
            
            # Legend repositioned to bottom to avoid overlapping colorbar
            showlegend=True,
            legend=dict(
                title="Asset Type",
                orientation="h",
                yanchor="top",
                y=-0.3,          # Pushes legend below the chart
                xanchor="center",
                x=0.5
            ),

            # Colorbar styling
            coloraxis_colorbar=dict(
                title='PV (m²)',
                thickness=25,
                len=0.8,
                yanchor="middle",
                y=0.5,
                tickfont=dict(size=18) # Slightly smaller for readability
            ),
            
            # Margins adjusted for large font and legend space
            margin=dict(l=80, r=100, t=80, b=150),
            plot_bgcolor='white'
        )

        # Clean up axes and grid
        fig.update_xaxes(showgrid=True, gridcolor='lightgray', zeroline=False, title_text="Longitude")
        fig.update_yaxes(showgrid=True, gridcolor='lightgray', zeroline=False, title_text="Latitude")
        
        # Save and Open
        fig.write_html(filename)
        webbrowser.open('file://' + os.path.realpath(filename))
        
        return fig, filename
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
    def static_plot(self): #plots graph with edge connections, correct node positions, shape based on profile type, hover info with node metadata, using matplotlib
        G = self
        pos = G.graph.get('pos')
        if not pos:
            # Fallback: build pos from stored coordinates (lat, lon -> x=lon, y=lat)
            pos = {}
            for node_id, data in G.nodes(data=True):
                coords = data.get('coordinates', (0.0, 0.0))
                pos[node_id] = (coords[1], coords[0])
            G.graph['pos'] = pos

        xs = [coord[0] for coord in pos.values()]
        ys = [coord[1] for coord in pos.values()]
        if not xs or not ys:
            print("Error: No coordinates available to plot.")
            return None, None

        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        pad_x = 0.05 * x_span if x_span != 0 else 0.01
        pad_y = 0.05 * y_span if y_span != 0 else 0.01
        x_range = [min(xs) - pad_x, max(xs) + pad_x]
        y_range = [min(ys) - pad_y, max(ys) + pad_y]

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_title("Community Configuration (Static)")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_xlim(x_range)
        ax.set_ylim(y_range)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(False)

        # Draw edges
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            ax.plot([x0, x1], [y0, y1], color="#888", linewidth=2, zorder=1)

        # Shape map (single color for all nodes)
        shape_map = {
            "house": "o",         # circle
            "commercial": "s",    # square
            "farm": "D",          # diamond
            "hospital": "+",      # plus
            "school": "*",        # star
            "water_pump": "^",    # triangle-up
            "default": "o"
        }
        uniform_color = "#1f77b4"

        # Compute per-node size from load profile scale
        scales = []
        for _, data in G.nodes(data=True):
            scales.append(float(data.get('profile_scale_kwh_yr', 0.0)))
        if len(scales) == 0:
            scales = [0.0]
        scale_min = float(np.min(scales))
        scale_max = float(np.max(scales))
        if scale_max == scale_min:
            scale_min -= 1.0
            scale_max += 1.0
        size_range = (60.0, 220.0)  # scatter size in points^2

        # Group nodes by shape with per-point sizes
        grouped = {}
        for node_id, data in G.nodes(data=True):
            profile = data.get("profile_type", "default")
            marker = shape_map.get(profile, shape_map["default"])
            x, y = pos[node_id]
            scale_val = float(data.get('profile_scale_kwh_yr', 0.0))
            size_val = float(np.interp(scale_val, [scale_min, scale_max], size_range))
            grouped.setdefault(marker, []).append((x, y, node_id, size_val))

        # Scatter artists and full node index for hover detection
        artists = []
        all_x, all_y, all_ids = [], [], []
        for marker, items in grouped.items():
            xs_m = [it[0] for it in items]
            ys_m = [it[1] for it in items]
            ids_m = [it[2] for it in items]
            sizes_m = [it[3] for it in items]
            sc = ax.scatter(xs_m, ys_m, s=sizes_m, marker=marker, c=uniform_color, edgecolors='white', linewidths=1.5, zorder=2)
            artists.append(sc)
            all_x.extend(xs_m)
            all_y.extend(ys_m)
            all_ids.extend(ids_m)

        # Single annotation for hover metadata
        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="#ffffff", ec="#333", alpha=1.0),
            arrowprops=dict(arrowstyle="->", color="#333"),
        )
        # Ensure annotation draws above other artists for readability
        annot.set_zorder(10)
        annot.set_visible(False)

        return fig, ax

        def build_hover_text(nid: str) -> str:
            data = G.nodes[nid]
            coords = data.get("coordinates", (0.0, 0.0))
            tech = f"Solar: {data.get('solar_panel_area', 0):.1f} m², Battery: {data.get('battery_capacity', 0):.1f} kWh"
            scale_info = f"Load scale: {data.get('profile_scale_kwh_yr', 0):.2f} (kWh/yr scaled)"
            limits = f"Area limit: {data.get('available_area', 0):.1f} m², Battery limit: {data.get('battery_limit', 0):.1f} kWh"
            return (
                f"{nid} ({data.get('profile_type', 'N/A')})\n"
                f"Coords: ({coords[0]:.4f} lat, {coords[1]:.4f} lon)\n"
                f"Installed: {tech}\n"
                f"{scale_info}\n"
                f"Limits: {limits}"
            )

        # Hover callback using display-coordinate distance
        def on_motion(event):
            if event.inaxes != ax or event.x is None or event.y is None:
                if annot.get_visible():
                    annot.set_visible(False)
                    fig.canvas.draw_idle()
                return

            pts = np.column_stack((all_x, all_y))
            disp = ax.transData.transform(pts)
            dists = np.hypot(disp[:, 0] - event.x, disp[:, 1] - event.y)
            idx = int(np.argmin(dists)) if len(dists) else -1
            threshold_px = 12.0
            if idx >= 0 and dists[idx] <= threshold_px:
                nid = all_ids[idx]
                annot.set_text(build_hover_text(nid))
                # Base anchor at node position
                xy_data = (all_x[idx], all_y[idx])
                annot.xy = xy_data

                # Compute dynamic offset so label stays inside axes bounds
                node_disp = ax.transData.transform(xy_data)
                ax_bbox = ax.get_window_extent()
                # Default offsets and alignment
                off_x, off_y = 12.0, 12.0
                ha, va = 'left', 'bottom'

                # If near top, place label below
                if (ax_bbox.y1 - node_disp[1]) < 60.0:
                    off_y = -12.0
                    va = 'top'
                # If near bottom, keep above
                elif (node_disp[1] - ax_bbox.y0) < 40.0:
                    off_y = 12.0
                    va = 'bottom'

                # If near right edge, place to the left
                if (ax_bbox.x1 - node_disp[0]) < 140.0:
                    off_x = -12.0
                    ha = 'right'
                # If near left edge, place to the right
                elif (node_disp[0] - ax_bbox.x0) < 40.0:
                    off_x = 12.0
                    ha = 'left'

                # Apply text position (offset points relative to xy)
                annot.set_position((off_x, off_y))
                annot.set_ha(ha)
                annot.set_va(va)
                annot.set_visible(True)
            else:
                annot.set_visible(False)
            fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', on_motion)
        plt.tight_layout()
        plt.show()
        return fig, ax
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
        self.bulk_configure_assets(
        battery_map={node: best_params[f"battery_{node}"] for node in self.nodes},
        solar_map={node: best_params[f"solar_{node}"] for node in self.nodes})                                               
        #read all adges from best_params and add to graph
        for key, value in best_params.items():
            if key.startswith("edge_") and value == 1:
                _, u, v = key.split("_")
                self.add_edge(u, v)
                

if __name__ == "__main__":
    example_config = Configuration()
    example_config.import_nodes_from_csv("input/configurations/Ethiopia_case_study.csv")
    example_config.bulk_configure_assets(solar_map={"MG":1,"GG":1,"QL":1}, battery_map={"MG":10,"GG":10,"QL":10})
    df=example_config.get_profiles_dataframe()
    #save df to csv
    df.to_csv("output/profiles_dataframe.csv", index=False)