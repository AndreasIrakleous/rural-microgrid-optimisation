import pytest
import pandas as pd
from src.core.network import MicrogridNetwork
from src.dispatch_strategy.simulator import MicrogridSimulator

def test_deficit_strategies():
    # 1. SETUP: Create a tiny network with 1 node, 0 solar, 0 battery.
    network = MicrogridNetwork()
    network.add_node("NodeA", battery_limit=0.0, available_area=0.0, hydro_power=0.0, deferable_load=0.0)
    network.set_asset_capacities(battery_map={"NodeA": 0.0}, solar_map={"NodeA": 0.0})
    
    # Create a 1-hour dataframe where Demand is 10 and PV is 0.
    df = pd.DataFrame([{
        "time": 0, "node_id": "NodeA", "load_profile": 10.0, 
        "pv_profile": 0.0, "battery_SOC": 0.0, "hydro_power": 0.0, "deferable_load": 0.0
    }])

    # 2. ACTION: Test Diesel Strategy
    settings_diesel = {"physics": {"deficit_strategy": "diesel"}}
    sim_diesel = MicrogridSimulator(network, settings=settings_diesel)
    df_diesel, _, _, _, _ = sim_diesel.run(df)
    
    # 3. ACTION: Test Unmet Load Strategy
    settings_unmet = {"physics": {"deficit_strategy": "unmet_load"}}
    sim_unmet = MicrogridSimulator(network, settings=settings_unmet)
    df_unmet, _, _, _, _ = sim_unmet.run(df)

    # 4. ASSERTIONS
    # If using diesel, unmet load should be 0, and diesel used should be 10.
    assert df_diesel.iloc[0]["unmet_load"] == 0.0
    assert df_diesel.iloc[0]["diesel_used"] == 10.0
    
    # If using unmet load, diesel used should be 0, and unmet load should be 10.
    assert df_unmet.iloc[0]["unmet_load"] == 10.0
    assert df_unmet.iloc[0]["diesel_used"] == 0.0