# Electricity_Sharing_MSci_Project
Authors: Andreas and Ismail
Research Question:  To what extent does electricity sharing minimise cost and emissions while maintaining reliability?

Conventions:
1. Time step for simulation: 1 hour
2. Units:
    a) Load profile and generation: kW

Configuration file:
The configuration file provides information about various configurations being tested. The file has the following information:
1. Node ID
2. Load Profile Type: (House, commercial, school, hospital)
3. Load Profile scale (dimensionless): Peak kW scaling
        Peak load = load_profile_scale * nomarlized_load 
4. Position: (Longitude, Lattitude)
5. Solar Area: Area available for solar panels



