# monte_carlo.py
import numpy as np
import pandas as pd
import tqdm
from pathlib import Path
from src.selv.indicators import add_indicators  # your TA helpers
from src.selv.backtest import run_strategy_on_df  # we'll write this wrapper next
import multiprocessing as mp

CSV_PATH = Path("btc_data.csv")
N_PATHS = 5_0  # simulations
SEED = 42

# --- 1. fit simple GBM to 1‑minute log‑returns ------------------------------
raw_df = pd.read_csv(CSV_PATH, parse_dates=["datetime"], index_col="datetime")
log_ret = np.log(raw_df["close"]).diff().dropna()
mu = log_ret.mean()  # drift per minute
sig = log_ret.std(ddof=0)  # vol per minute
dt = 1  # 1 minute

horizon = len(raw_df) - 1  # same length as history


def simulate_path(start_price: float, rng: np.random.Generator) -> pd.Series:
    """Generate a GBM price path of length `horizon`."""
    shocks = rng.normal(mu * dt, sig * np.sqrt(dt), horizon)
    log_prices = np.log(start_price) + np.cumsum(shocks)
    return np.exp(log_prices)


def simulate_and_run(worker_id):
    # Generate one synthetic price path and run the strategy
    rng = np.random.default_rng(SEED + worker_id)
    prices = simulate_path(raw_df["close"].iloc[0], rng)
    synthetic = raw_df.copy()
    synthetic["close"] = np.r_[raw_df["close"].iloc[0], prices]
    synthetic["volume"] = raw_df["volume"].mean()
    synthetic = add_indicators(synthetic)
    if worker_id < 5:
        Path("debug").mkdir(exist_ok=True)
        synthetic.to_parquet(f"debug/sim_path_{worker_id}.parquet")
    result = run_strategy_on_df(synthetic)
    result["path_id"] = worker_id
    return result


# --- 2. Monte‑Carlo loop (parallel) ----------------------------------------

if __name__ == "__main__":
    np.random.seed(SEED)
    with mp.Pool() as pool:
        stats = list(
            tqdm.tqdm(
                pool.imap_unordered(simulate_and_run, range(N_PATHS)), total=N_PATHS
            )
        )

    mc_df = pd.DataFrame(stats)
    mc_df.to_csv("mc_results.csv", index=False)
    print(mc_df.describe(percentiles=[0.05, 0.5, 0.95]))
