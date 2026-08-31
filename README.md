# Electricity Sharing MSci Project

Simulate and optimize electricity networks for rural communities. Determines the cost-benefit of energy sharing via solar, batteries, and diesel generators using Optuna-based multi-objective optimization.

## Quick Start

### Install
```bash
pip install -r requirements.txt
```

### Run a Simulation
```python
from main import Configuration
from dispatch_strategy.power_flow_edgeless import MicrogridSimulator

config = Configuration()
config.import_nodes_from_csv("input/configurations/small_community_new.csv")
config.bulk_configure_assets(
    solar_map={"H001": 20, "H002": 15, "C001": 120},
    battery_map={"H001": 50, "H002": 30, "C001": 200}
)

sim = MicrogridSimulator(config, delta_t=1)
profiles_df = config.get_profiles_dataframe()
final_df, logs, _, report, summary = sim.run_periodic(profiles_df)
```

### Run Optimization
```python
from optimisation.optimisation import run_study

study = run_study(
    config_id=0,
    config_data="input/configurations/small_community_new.csv",
    n_trials=300,
    seed=42
)
```

## What It Does

**Simulation** — Model communities as networks of nodes (buildings). Each hour, the system:
- Calculates available solar and local demand
- Shares excess energy across connections (if any)
- Manages batteries and diesel generation
- Tracks unmet demand, discarded energy, and costs

**Optimization** — Uses [Optuna](https://optuna.org/) to find optimal sizing of solar/batteries and network topology:
- Single-objective: minimize cost (TPE sampler)
- Multi-objective: cost + emissions trade-off (NSGA-II)
- Reliability constraint: max 10% unmet demand

**Result** — Pareto fronts showing cost vs. emissions for different network topologies (isolated, MST, optimally connected).

## Project Structure

```
Electricity_Sharing_MSci_Project/
├── main.py                               # Configuration class (extends NetworkX)
├── dispatch_strategy/
│   ├── power_flow_edgeless.py           # Hourly energy dispatch simulator
│   └── power_flow.py                    # Connected network power flow
├── optimisation/
│   ├── optimisation.py                  # Single-objective (cost minimization)
│   ├── MO_optimisation.py               # Multi-objective (cost + emissions)
│   ├── Pareto.py                        # Pareto front analysis
│   └── CaseStudy optimisation.py        # Ethiopia case study
├── input/configurations/                # Node/building definitions (CSV)
├── input/load_profiles/                 # Hourly demand profiles
├── input/PV_profiles_files/             # Solar irradiance data
├── analysis/                            # Post-processing and visualization
│   ├── analyse_optimisation_results.py  # Topology comparison
│   ├── analyse_moo.py                   # Pareto visualization
│   ├── validation.py                    # Case study validation
│   └── sensitivity_analysis.py          # Parameter sensitivity
└── output/                              # Results and Optuna databases
```

## Input Format

Communities are defined in CSV format with columns:
- `node_id` — Unique identifier
- `latitude`, `longitude` — Location
- `load_profile_type` — house | commercial | hospital | school | farm | water_pump
- `load_profile_scale_kwh_yr` — Annual demand (scaled)
- `solar_area_m2` — Available roof/land area
- `battery_limit_kwh` — Max battery capacity
- `hydro_power_kW` — Local hydro generation (if any)
- `deferable_load_kWh_day` — Flexible load (e.g., water pumping)

See `input/configurations/` for examples.

## Key Concepts

### Configuration Class
Extends NetworkX Graph. Nodes represent buildings with properties like solar area limits, battery capacity, and demand profiles. Edges represent electrical connections.

### Dispatch Logic (hourly)
1. Serve local load from available solar
2. Share excess energy with connected nodes
3. Charge batteries if surplus remains
4. Use diesel generators for unmet demand
5. Track discarded energy and costs

### Optimization Parameters
- **Solar area & battery size** at each node (continuous)
- **Network edges** (binary: connected or not)
- **Objective**: minimize cost (TPE) or cost + emissions (NSGA-II)
- **Constraint**: max 10% unmet demand (reliability)

## Analysis & Visualization

- `analysis/analyse_optimisation_results.py` — Compare isolated vs. connected vs. optimally-connected
- `analysis/analyse_moo.py` — Generate Pareto fronts (cost vs. emissions)
- `analysis/validation.py` — Validate against Ethiopia case study
- `analysis/sensitivity_analysis.py` — Parameter sensitivity

## Background

### The Problem

~730 million people still lack access to electricity, mostly in rural areas of developing countries. While grid extension is standard in developed regions, it's prohibitively expensive in remote areas separated by mountains and rivers.

Off-grid solar + battery + diesel systems are cheaper to deploy, but isolated systems waste energy. The question: **Does connecting buildings to share energy reduce total cost?**

### Key Finding

**Yes, but mainly for low-emission designs.** Cost savings from reduced battery/diesel requirements (due to less wasted energy) outweigh connection costs. This effect is strongest in cleaner designs.

### Related Work

- [CLOVER Framework](https://github.com/CLOVER-energy/CLOVER) — Community-scale energy system modelling
- Sandwell et al. (2025) — [Opportunities for decentralised solar power](https://doi.org/10.1038/s41467-025-62948-8)
- IEA/IRENA (2025) — [Tracking SDG7](https://www.iea.org/reports/tracking-sdg7-2025)

## Authors

Developed by MSci Physics students **Andreas Irakleous** and **Ismail Abdelmonem** under the supervision of Research Associate **Benedict Winchester** at Imperial College London.
