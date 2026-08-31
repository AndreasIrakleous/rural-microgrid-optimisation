"""
This script we want to implement code for implementing the dispatch strategy
Task: Determine the dispatch strategy for the a given configuration at all time steps.

"""
from skeleton import *
import platform

""" # Initial power flow function which is not used anymore.
def power_flow2(G):
    #Turn graph into directed graph
    G = G.to_directed()
    next_nodes = [] # List to keep track of nodes to process
    #Determine nodes with degree = 2
    bound_nodes = [node for node in G.nodes if G.degree[node] == 2] 
    for node in bound_nodes: # Calculate net load for bound nodes and rest of graph
        neighbors = list(G.neighbors(node))
        G.nodes[node]["net_load_close"] = G.nodes[node]['pv'] - G.nodes[node]['profile_scale_kwh_yr']
        net_load_rest = sum(G.nodes[n]['pv'] - G.nodes[n]['profile_scale_kwh_yr'] for n in G.nodes if n != node)
        if G.nodes[node]["net_load_close"] < net_load_rest:
            # Bound node has deficit
            G.remove_edge(node, neighbors[0])
        else:
            # Bound node has surplus
            G.remove_edge(neighbors[0], node)
        next_nodes += neighbors
    print(f"next nodes: {next_nodes}")
    neighbors1 = set(G.successors(next_nodes[0])) | set(G.predecessors(next_nodes[0]))
    print(f"Neighbors: {neighbors1}")
    # Determine power flow for rest of graph
    for node in next_nodes:
        neighbors = set(G.successors(node)) | set(G.predecessors(node))
        neighbors = list(neighbors)
        graph_net_load = sum(G.nodes[n]['pv'] - G.nodes[n]['profile_scale_kwh_yr'] for n in G.nodes)
        close_neighbor = [neighbor for neighbor in neighbors if G.degree[neighbor]<3] # List comprehension to find close neighbor
        far_neighbor = [neighbor for neighbor in neighbors if G.degree[neighbor]>=3]
        print(f"Close and far neighbour {close_neighbor, far_neighbor}")
        G.nodes[node]["net_load"] = G.nodes[node]['pv'] - G.nodes[node]['profile_scale_kwh_yr']
        G.nodes[node]["net_load_close"] = G.nodes[close_neighbor[0]]['net_load_close'] + G.nodes[node]["net_load"]
        net_load_rest = graph_net_load - G.nodes[node]["net_load_close"]
        if G.nodes[node]["net_load_close"] < net_load_rest:
            # Neighbor has deficit
            G.remove_edge(far_neighbor[0], node)
        else:
            # Neighbor has surplus
            G.remove_edge(node, far_neighbor[0])
    #  # If node has more than two double-connected edges, skip
    #     if True:
    #         next_nodes += node
    #         continue
    
    return G
"""

def edge_filter(u_rm, v_rm):
    """
    Edge filter function to exclude a specific edge (u_rm, v_rm)
    from the graph view.
    """
    def filter_edge(u, v):
        return not ((u == u_rm and v == v_rm) or (u == v_rm and v == u_rm))
    return filter_edge
def dispatch_strategy(Graph,df, delta_t=1):
    """
    Objective: 
    Minimize total unmet load for a given configuration to maximize reliability

    How to achieve this:
    First minimise unmet load; then maximise stored energy.

    Approach:
    Cut based flow determination algorithm.
    Treat the original graph as immutable during analysis.
    Use graph view to break edges at different points in the graph and determine power flow.


    Power flow Determination Algorithm:
    1. Remove an edge between 2 connected nodes
    2. Implement dispatch strategy algorithm
    3. Determine flow transfer between both both nodes
    4. Assign direction and magnitude to adjacency matrix
    5. Repeat for all edges in the graph over all time steps

    Limitations:
    1. Only works for MSTs currently.
    2. When net_u == net_v, direction assigned from node u to node v arbitrarily. 
    3. Does not depend on electrical components (resistance, reactance, capacity etc.)
    4. Ignores discharge limits of batteries, line capacities, and battery charge limit for now.

    Power Flow Method:
    1. Choose an edge (u,v) to hide
    2. Create edge filter with edge (u,v) removed
    3. Create graph view with edge filter
    4. Dispatch strategy to determine power flow between both subgraphs
    5. Assign direction and magnitude to adjacency matrix
    
    Adjacnecy matrix convention:
    A[i][j] > 0 if power flows from node i to node j
    A[i][j] < 0 if power flows from node j to node i
    A[i][j] = 0 if no power flow between node i and node j

    Dispatch strategy:
    1. Satisfy load using local energy supply 
        (net_energy_local = load_local - (PV_local + Battery_local)
        load_local = 0 if net_energy_local <= 0 else net_energy_local
        supply_local = 0 if net_energy_local >= 0 else -net_energy_local
        )
	2. Satisfy other subgraph load using surplus energy from subgraph
        (net_energy = PV_total + battery_total - load_total) 
    If surplus energy remains after satisfying local and other subgraph load:
	3. Charge local battery
	4. Charge other's batteries
    5. Discard energy

    For every edge determine the deficit / surplus and the net available energy.
    From that determine the power flow per edge
    Determine the energy state of each node outside the edge analysis loop
    Start another edge loop to determine the power flow based on storage capacity
    Update the final state of the battery SOC per node after all edges have been analysed



    Returns:
    G_directed: Directed graph with power flow directions assigned to edges.
    """
    #Variables that will be used: (Values now are placeholders)
    discharge_limit = 0.8 #Battery discharge limit (80% of capacity)
    line_capacity = 10000 #Line capacity in Watts (10 kW)
    charge_limit = 0.9 #Battery charge limit (90% of capacity)
    
    # Dictionaries to store adjacency matrices for each timestep
    timestep_A1 = {}      # phase 1 flows
    timestep_A2 = {}      # phase 2 flows
    timestep_A_total = {}   # A1 + A2

    for t in df['time'].unique(): #Loop over time steps 
        """
        Determine power flow for each time step
        """
        #Determine the number of subgraphs in the graph:
        subgraphs = list(nx.connected_components(Graph))
        #Create a list of subgraph graphs:
        subgraphs = [Graph.subgraph(sg).copy() for sg in subgraphs]

        # Initialize empty matrices for this timestep (full graph nodes)
        if t not in timestep_A1:
            node_all = list(Graph.nodes())
            timestep_A1[t] = {u: {v: 0 for v in node_all} for u in node_all}
            timestep_A2[t] = {u: {v: 0 for v in node_all} for u in node_all}
            timestep_A_total[t] = {u: {v: 0 for v in node_all} for u in node_all}

        for G in subgraphs:

         #Create a list of edges to analyse:
            edge_list = list(G.edges()) #Tuple shape that will be used for edge filter
            node_list = list(G.nodes())
            
            # Initialize adjacency matrix using node IDs as keys
            A = {u: {v: 0 for v in node_list} for u in node_list}

            for node in G.nodes(): #Loop over nodes to calculate energy before transfer
                pv=df.loc[(df['time'] == t) & (df['node_id'] == node), 'pv_profile'].values[0]
                load=df.loc[(df['time'] == t) & (df['node_id'] == node), 'load_profile'].values[0]
                soc=df.loc[(df['time'] == t) & (df['node_id'] == node), 'battery_SOC'].values[0]
                #Step 1: Satify local load using local energy supply
                net_energy_local = pv + soc - load
                df.loc[(df['time'] == t) & (df['node_id'] == node), 'net_energy_local'] = net_energy_local #Store net energy local in dataframe
                if net_energy_local < 0: #Deficit and surplus per node
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'deficit'] = -net_energy_local
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'surplus'] = 0
                else:
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'deficit'] = 0
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'surplus'] = net_energy_local
            # for loop over edges to determine power flow direction:
            for edge in edge_list:
                u_rm, v_rm = edge
                edge_predicate = edge_filter(u_rm, v_rm)
                G_view = nx.subgraph_view(G, filter_edge=edge_predicate)
                # Get connected components. Expect 2 subgraphs since each edge is a bridge
                comps = list(nx.connected_components(G_view))
                if len(comps) != 2: 
                    raise ValueError("Graph did not split into two components") #Code breaks here if not 2 components
                #Assume energy difference calculated at each node
                # Calculate net energy for both subgraphs. Let u_rm be a subset of subgraph 1 and v_rm be a subset of subgraph 2
                
                if u_rm in comps[0]: #To assign subgraphs correctly according to nodes at the correct subgraph
                    u_node_subgraph = comps[0]
                    v_node_subgraph = comps[1]

                else:
                    u_node_subgraph = comps[1]
                    v_node_subgraph = comps[0]
                
                #net energy for each subgraph:
                net_u = df.loc[(df['time'] == t) & (df['node_id'].isin(u_node_subgraph)), 'net_energy_local'].sum()
                net_v = df.loc[(df['time'] == t) & (df['node_id'].isin(v_node_subgraph)), 'net_energy_local'].sum()

                if net_u < 0:
                    deficit_u = -net_u
                    surplus_u = 0
                else:
                    deficit_u = 0  
                    surplus_u = net_u
                if net_v < 0:
                    deficit_v = -net_v
                    surplus_v = 0
                else:
                    deficit_v = 0  
                    surplus_v = net_v


                if deficit_u > 0 and deficit_v > 0:
                    #Both subgraphs have deficit, no power flow
                    A[u_rm][v_rm] = 0
                    A[v_rm][u_rm] = 0
                    continue
                
                # Step 2: Energy transfer between subgraphs (PV + battery)
                elif surplus_u > 0 and deficit_v > 0:
                    #Subgraph 1 has surplus, subgraph 2 has deficit
                    flow_1 = min(surplus_u, deficit_v) #Ignore line capacity for now
                    A[u_rm][v_rm] = flow_1
                    A[v_rm][u_rm] = -flow_1


                    # Comment: Update dataframe to reflect energy transfer 
                    continue

                elif surplus_v > 0 and deficit_u > 0:
                    #Subgraph 2 has surplus, subgraph 1 has deficit
                    flow_1 = min(surplus_v, deficit_u)
                    A[v_rm][u_rm] = flow_1
                    A[u_rm][v_rm] = -flow_1
                    continue
                
                # Step 3: Both subgraphs have surplus, charge local batteries first
                elif surplus_u > 0 and surplus_v > 0:
                    # No power flow to satisfy load, both subgraphs have surplus
                    A[u_rm][v_rm] = 0
                    A[v_rm][u_rm] = 0
                    continue
            
            # Store the phase-1 adjacency matrix contribution for this timestep (combine all subgraph matrices)
            for u in G.nodes():
                for v in G.nodes():
                    timestep_A1[t][u][v] += A[u][v]
            
            # Determine the energy state after phase 1:
            for node in G.nodes(): #Loop over nodes to calculate energy after transfer
                net_energy_local = df.loc[(df['time'] == t) & (df['node_id'] == node), 'net_energy_local'].values[0]
                # Sum the value of energy transfer to and from the node from the adjacency matrix:
                energy_transfer = sum(A[node].values()) #Sum of row for this node 
                # energy_transfer > 0 if net energy sent out from node, < 0 if net energy received by node
                net_energy_local_2= net_energy_local - energy_transfer
                df.loc[(df['time'] == t) & (df['node_id'] == node), 'net_energy_local_2'] = net_energy_local_2

            A_2 = {u: {v: 0 for v in node_list} for u in node_list}  #Re-initialize adjacency matrix with zeros for phase 2
            for edge in edge_list:
                # Repeat edge analysis to determine power flow for storage charging
                u_rm, v_rm = edge
                edge_predicate = edge_filter(u_rm, v_rm)
                G_view = nx.subgraph_view(G, filter_edge=edge_predicate)
                # Get connected components. Expect 2 subgraphs since each edge is a bridge
                comps = list(nx.connected_components(G_view))
                if len(comps) != 2: 
                    raise ValueError("Graph did not split into two components")
                #Assume energy difference calculated at each node
                # Total deficit / surplus for both subgraphs after phase 1. Let u_rm be a subset of subgraph 1 and v_rm be a subset of subgraph 2
                if u_rm in comps[0]: #To assign subgraphs correctly according to nodes at the correct subgraph
                    u_node_subgraph = comps[0]
                    v_node_subgraph = comps[1]

                else:
                    u_node_subgraph = comps[1]
                    v_node_subgraph = comps[0]
                
                
                #net energy for each subgraph after phase 1:
                net_u = df.loc[(df['time'] == t) & (df['node_id'].isin(u_node_subgraph)), 'net_energy_local_2'].sum()
                net_v = df.loc[(df['time'] == t) & (df['node_id'].isin(v_node_subgraph)), 'net_energy_local_2'].sum()
                
                # Battery storage available for each subgraph
                for node in G_view.nodes():
                    battery_capacity = G_view.nodes[node]['battery_capacity']
                    soc = df.loc[(df['time'] == t) & (df['node_id'] == node), 'battery_SOC'].values[0]
                    battery_storage_available = battery_capacity - soc
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'battery_available'] = battery_storage_available
                
                battery_storage_available_u = df.loc[(df['time'] == t) & (df['node_id'].isin(u_node_subgraph)), 'battery_available'].sum()
                battery_storage_available_v = df.loc[(df['time'] == t) & (df['node_id'].isin(v_node_subgraph)), 'battery_available'].sum()

                if battery_storage_available_u <= 0 and battery_storage_available_v <= 0:
                    #Both subgraphs have full batteries, no power flow
                    A_2[u_rm][v_rm] = 0
                    A_2[v_rm][u_rm] = 0
                    continue

                elif battery_storage_available_u >= 0 and battery_storage_available_v >= 0:
                    #Both subgraphs have storage available, no power flow
                    A_2[u_rm][v_rm] = 0
                    A_2[v_rm][u_rm] = 0
                    continue

                elif battery_storage_available_u > 0 and battery_storage_available_v < 0:
                    #Subgraph 1 has storage available, subgraph 2 has full battery
                    flow = min(battery_storage_available_u, -battery_storage_available_v)
                    A_2[u_rm][v_rm] = flow
                    A_2[v_rm][u_rm] = -flow
                    continue

                elif battery_storage_available_v > 0 and battery_storage_available_u < 0:
                    #Subgraph 2 has storage available, subgraph 1 has full battery
                    flow = min(battery_storage_available_v, -battery_storage_available_u)
                    A_2[v_rm][u_rm] = flow
                    A_2[u_rm][v_rm] = -flow
                    continue
            
            # Merge phase-2 flows into timestep accumulator
            for u in G.nodes():
                for v in G.nodes():
                    timestep_A2[t][u][v] += A_2[u][v]

            # Determine the energy state after phase 2:
            for node in G.nodes():
                net_energy_local_2 = df.loc[(df['time'] == t) & (df['node_id'] == node), 'net_energy_local_2'].values[0]
                # Sum the value of energy transfer to and from the node from the adjacency matrix:
                energy_transfer = sum(A_2[node].values())
                net_energy_local_3= net_energy_local_2 - energy_transfer
                df.loc[(df['time'] == t) & (df['node_id'] == node), 'net_energy_local_3'] = net_energy_local_3

                # Update battery SOC based on energy transfer in phase 2
                energy_to_charge = G.nodes[node]['battery_capacity'] - net_energy_local_3
                if net_energy_local_3 < G.nodes[node]['battery_capacity'] and net_energy_local_3 > 0:
                    df.loc[(df['time'] == t+delta_t) & (df['node_id'] == node), 'battery_SOC'] = net_energy_local_3
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'discarded_energy'] = 0
                elif net_energy_local_3 >= G.nodes[node]['battery_capacity']:
                    df.loc[(df['time'] == t + delta_t) & (df['node_id'] == node), 'battery_SOC'] = G.nodes[node]['battery_capacity']
                    discarded_energy = net_energy_local_3 - G.nodes[node]['battery_capacity']
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'discarded_energy'] = discarded_energy
                elif net_energy_local_3 <= 0:
                    df.loc[(df['time'] == t+delta_t) & (df['node_id'] == node), 'battery_SOC'] = 0
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'discarded_energy'] = 0
                    df.loc[(df['time'] == t) & (df['node_id'] == node), 'unmet_load'] = -net_energy_local_3


        """
                # Both subgraphs have surplus, charge local batteries first
                battery_charge_u = min(G_view.nodes[u_rm]['battery_capacity'] - df.loc[(df['time'] == t) & (df['node_id'] == u_rm), 'battery_SOC'].values[0],
                                        surplus_u) 
                
                # Update battery SOC in dataframe
                df.loc[(df['time'] == t) & (df['node_id'] == u_rm), 'battery_SOC'] += battery_charge_u

                                        
                battery_charge_v = min(G_view.nodes[v_rm]['battery_capacity'] - df.loc[(df['time'] == t) & (df['node_id'] == v_rm), 'battery_SOC'].values[0],
                                        charge_limit,
                                        surplus_v)
                # Update battery SOC in dataframe
                df.loc[(df['time'] == t) & (df['node_id'] == v_rm), 'battery_SOC'] += battery_charge_v

                # Update net energy after charging batteries
                net_u_after_charge = surplus_u - battery_charge_u
                net_v_after_charge = surplus_v - battery_charge_v
                
               
            
                if net_u_after_charge <= 0 and net_v_after_charge <= 0:
                    # Both subgraphs have deficit after charging, no power flow
                    A[node_index[u_rm]][node_index[v_rm]] = 0
                    A[node_index[v_rm]][node_index[u_rm]] = 0
                    continue

                 # Step 4: Charge other's batteries with remaining surplus

                elif net_u_after_charge > 0 and net_v_after_charge <= 0:
                    # Subgraph 1 has surplus, subgraph 2 has deficit after charging
                    flow = min(net_u_after_charge, -net_v_after_charge) 
                    A[node_index[u_rm]][node_index[v_rm]] = flow
                    A[node_index[v_rm]][node_index[u_rm]] = -flow
                    #update battery SOC of subgraph 2
                    df.loc[(df['time'] == t) & (df['node_id'] == v_rm), 'battery_SOC'] += flow
                    continue

                elif net_v_after_charge > 0 and net_u_after_charge < 0:
                    # Subgraph 2 has surplus, subgraph 1 has deficit after charging
                    flow = min(net_v_after_charge, -net_u_after_charge)
                    A[node_index[v_rm]][node_index[u_rm]] = flow
                    A[node_index[u_rm]][node_index[v_rm]] = -flow
                    #update battery SOC of subgraph 1
                    df.loc[(df['time'] == t) & (df['node_id'] == u_rm), 'battery_SOC'] += flow
                    continue

                
                # Step 5: Discard energy
                #Discard surplus energy if both subgraphs still have surplus after charging
                elif net_u_after_charge > 0 and net_v_after_charge > 0:
                    # Both subgraphs still have surplus, no power flow
                    A[node_index[u_rm]][node_index[v_rm]] = 0
                    A[node_index[v_rm]][node_index[u_rm]] = 0
                    discard_energy_u = net_u_after_charge
                    discard_energy_v = net_v_after_charge
                    # Discard surplus energy after charging
                    df.loc[(df['time'] == t) & (df['node_id'] == u_rm), 'discard_energy'] += discard_energy_u
                    df.loc[(df['time'] == t) & (df['node_id'] == v_rm), 'discard_energy'] += discard_energy_v
                    continue
        """
        """
        #Create a directed graph from adjacency matrix
        #Create an empty directed graph
        G_directed = nx.DiGraph()
        #Add graph attributes:
        G_directed.graph.update(G.graph) #Copy graph attributes from original graph to directed graph
        #Add nodes to directed graph
        for idx in range(len(G.nodes)):
            G_directed.add_node(index_node[idx]) #index_node maps adjacency matrix index to node id
            G_directed.nodes[index_node[idx]].update(G.nodes[index_node[idx]]) #Copy node attributes from original graph to directed graph
        #Add directed edges based on adjacency matrix.
        for i in range(len(G.nodes)): #O(n^2) operation. Try to optimise.
            for j in range(len(G.nodes)):
                if A[i][j] == 1:
                    G_directed.add_edge(index_node[i], index_node[j])
        """
    # Build total matrices A_total = A1 + A2 per timestep
    for t in timestep_A_total:
        for u in timestep_A_total[t]:
            for v in timestep_A_total[t][u]:
                timestep_A_total[t][u][v] = timestep_A1[t][u][v] + timestep_A2[t][u][v]
    
    # Convert numpy int64 keys to native Python int for JSON serialization
    def convert_to_json_serializable(mats):
        """Convert numpy int64 keys to native Python types for JSON serialization"""
        result = {}
        for t, matrix in mats.items():
            t_key = int(t)  # Convert numpy int64 to Python int
            result[t_key] = {}
            for u, row in matrix.items():
                u_key = str(u)  # Node IDs as strings
                result[t_key][u_key] = {}
                for v, val in row.items():
                    v_key = str(v)  # Node IDs as strings
                    result[t_key][u_key][v_key] = float(val) if isinstance(val, (int, float)) else val
        return result
    
    #save timestep_A_total to JSON
    with open('timestep_A_total.json', 'w') as f:
        json.dump(convert_to_json_serializable(timestep_A_total), f, indent=4)


    # Turn dataframe into .csv file:
    df.to_csv('power_flow_output.csv', index=False)

    # I want to open the file automatically in an excel sheet after running the script:
    # Open the CSV file in Excel
    open_file=False
    if open_file==True:
        file_path = 'power_flow_output.csv'
        if platform.system() == 'Darwin':  # macOS
            os.system(f'open "{file_path}"')
        elif platform.system() == 'Windows':  # Windows
            os.startfile(file_path)
        else:  # Linux
            os.system(f'xdg-open "{file_path}"')
        


    return df,timestep_A_total

if __name__ == "__main__":
    '''
    Objective:
    Determine power flow direction between 2 nodes

    Limitations:
    1. No load (time series) data implemented yet
    2. No solar, battery, diesel (time series) data implemented yet

    Assumptions:
    1. Fixed time step t = 1 year 
    2. Gen is capacity for whole year. 
    '''
        
if __name__ == "__main__":
    example_config = Configuration()
    example_config.import_nodes_from_csv("configurations/small_community.csv")
    example_config.bulk_configure_assets(
            battery_map={
                'H001': 50,
                'H002': 30,
                'H003': 20,
                'C001': 200,
                'M001': 500,
                'S001': 100,
                'WP01': 80 },
            solar_map={
                'H001': 20,
                'H002': 15,
                'H003': 18,
                'C001': 120,
                'M001': 250,
                'S001': 80,
                'WP01': 30
            }
        )
    
    dynamic_profiles_df = example_config.get_profiles_dataframe()
    example_config.add_edge('H001', 'H002')
    example_config.add_edge('H002', 'C001')
    example_config.add_edge('H003', 'C001')
    example_config.add_edge('C001', 'M001')
    example_config.add_edge('S001', 'C001')
    example_config.add_edge('WP01', 'C001')
    df,A=dispatch_strategy(example_config, dynamic_profiles_df, delta_t=1)
    example_config.graph_plot(df=df)