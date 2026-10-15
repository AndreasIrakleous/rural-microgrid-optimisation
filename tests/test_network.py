import pytest
from src.core.network import MicrogridNetwork

def test_haversine_distance():
    # 1. SETUP
    network = MicrogridNetwork()
    # Add two nodes on the equator, exactly 1 degree of longitude apart
    network.add_node("NodeA", coordinates=(0.0, 0.0))
    network.add_node("NodeB", coordinates=(0.0, 1.0))
    
    # 2. ACTION
    distance = network.haversine_distance("NodeA", "NodeB")
    
    # 3. ASSERT
    # 1 degree at the equator is ~111.19 km. We round to 1 decimal place.
    assert round(distance, 1) == 111.2

def test_set_asset_capacities():
    # 1. SETUP
    network = MicrogridNetwork()
    network.add_node("TestNode", battery_limit=100.0, available_area=50.0)
    
    # 2. ACTION
    test_battery_map = {"TestNode": 25.0}
    test_solar_map = {"TestNode": 10.0}
    network.set_asset_capacities(battery_map=test_battery_map, solar_map=test_solar_map)
    
    # 3. ASSERT
    assert network.nodes["TestNode"]["battery_capacity"] == 25.0
    assert network.nodes["TestNode"]["solar_panel_area"] == 10.0