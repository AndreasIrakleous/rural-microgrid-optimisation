
from main import *
from dispatch_strategy.power_flow_edgeless import *
from optimisation.optimisation import *
import matplotlib.pyplot as plt
from matplotlib import rc, rcParams
import networkx as nx
import seaborn as sns
import pandas as pd
from matplotlib.ticker import FormatStrFormatter

#Constraint function:
def constraints_func(trial):
    unmet_ratio = trial.user_attrs.get("unmet_ratio")
    if unmet_ratio is None:
        return [1.0] # Infeasible if simulation failed/didn't run
    return [unmet_ratio - 0.10]

#Storage
folder_name = "./output/optuna_results"
if not os.path.exists(folder_name):
    os.makedirs(folder_name)
db_filename = f"case_study_no_connection2.db"
#Run optimization for a single weight
storage_url = f"sqlite:///{os.path.join(folder_name, db_filename)}"
BASE_DIR = Path(__file__).resolve().parent.parent #



config=Configuration()
config.import_nodes_from_csv("input/configurations/Ethiopia_case_study.csv")

seed = 42
start_time = time.time()
study_name = f"study1"

sampler = optuna.samplers.TPESampler(
    seed=seed,
    n_startup_trials=100,
    constraints_func=constraints_func
)
study = optuna.create_study(
    directions=["minimize"],
    storage=storage_url, 
    study_name=study_name,
    sampler=sampler,
    load_if_exists=True)
study.optimize(lambda trial: objective(trial, config), n_trials=1000)



