import argparse
import json
import os
from src.core.network import MicrogridNetwork
from src.optimisation.optimiser import run_study

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Microgrid Simulation & Optimization")
    parser.add_argument("--scenario", type=str, required=True, help="Scenario folder name")
    parser.add_argument("--config", type=str, default="default.json", help="Specific config file to run")
    parser.add_argument("--trials", type=int, default=None, help="Override trial budget for quick testing")
    args = parser.parse_args()

    # Automatically route to the configs folder
    settings_path = os.path.join("input", args.scenario, "configs", args.config)
    
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Configuration file not found: {settings_path}")
        
    with open(settings_path, "r") as f:
        settings = json.load(f)

    study_cfg = settings.get("study", {})
    obj_mode = study_cfg.get("objective", "soo")
    n_trials = args.trials or study_cfg.get("trials", 30)
    topologies = study_cfg.get("topologies_to_run", ["isolated"])
    nodes_path = os.path.join("input", args.scenario, "nodes.csv")

    print(f"=== Scenario: {args.scenario} | Config: {args.config} | Objective: {obj_mode.upper()} ===")

    for topo in topologies:
        print(f"\n--- Starting Topology: {topo.upper()} ---")
        
        network = MicrogridNetwork()
        network.load_nodes_from_csv(nodes_path)

        if topo == "mst":
            network.minimum_spanning_tree()
        elif topo == "isolated":
            network.clear_edges()
            
        settings["study"]["active_topology"] = topo
        
        run_study(network, settings, n_trials=n_trials)
        
    print("\n=== Scenario Execution Complete ===")