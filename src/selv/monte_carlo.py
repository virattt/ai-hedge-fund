import numpy as np
import pandas as pd
from pathlib import Path
from src.selv.indicators import (
    add_indicators,
    long_short_strategy,
    buy_sell_strategy,
)  # strategy executors
from mpmath import erfinv, sqrt
import math

# CSV_PATH = Path("btc_data.csv")
# N_PATHS = 5_000  # simulations
# SEED = 42

# --- 1. fit simple GBM to 1‑minute log‑returns ------------------------------
# raw_df = pd.read_csv(CSV_PATH, parse_dates=["datetime"], index_col="datetime")
# log_ret = np.log(raw_df["close"]).diff().dropna()
# mu = log_ret.mean()  # drift per minute
# sig = log_ret.std(ddof=0)  # vol per minute
# dt = 1  # 1 minute




def simulate_path(start_price: float, rng: np.random.Generator, original_df: pd.DataFrame) -> pd.Series:
   """
   Generate a synthetic price path using Geometric Brownian Motion (GBM).
   
   This function creates a simulated price series that follows a GBM model,
   calibrated to the statistical properties of the input price data. The
   simulation uses the historical mean and volatility to generate a path
   with similar characteristics but different random variations.
   
   Parameters:
   -----------
   start_price : float
       The initial price from which to begin the simulated path
   rng : np.random.Generator
       Random number generator for reproducible randomness
   original_df : pd.DataFrame
       DataFrame containing historical price data with a 'close' column
       
   Returns:
   --------
   pd.Series
       A series of simulated prices following a GBM process
   """
   # Step 1: Calculate log returns from the historical price data
   log_ret = np.log(original_df["close"]).diff()
   
   # Step 2: Extract statistical parameters from the historical log returns
   mu = log_ret.mean()          # Mean of log returns (drift rate per time step)
   sig = log_ret.std(ddof=0)    # Standard deviation of log returns (volatility per time step)
   dt = 1                       # Time increment (1 minute in this case)
   horizon = len(original_df) - 1  # Number of future steps to simulate (match historical length)
   
   # Step 3: Generate random normal shocks scaled by the drift and volatility
   # - mu * dt: Expected drift per time step
   # - sig * sqrt(dt): Volatility scaled by square root of time step (from Ito's lemma)
   # - This creates normally distributed random increments with the right statistical properties
   shocks = rng.normal(mu * dt, sig * np.sqrt(dt), horizon)
   
   # Step 4: Convert to a price path using geometric Brownian motion formula
   # - Start with log of initial price
   # - Add cumulative sum of random shocks to create a random walk with drift
   # - Cumulative sum models the path dependency of prices over time
   log_prices = np.log(start_price) + np.cumsum(shocks)
   
   # Step 5: Convert log prices back to actual prices using exponential function
   # - exp(log_prices) reverses the logarithm to get actual price levels
   # - This ensures prices remain positive, a key property of GBM
   return np.exp(log_prices)


# --- Strategy Entry Functions -------------------------------------------------


# TODO: understand this function 
def min_track_record_length(sr_hat: float,
                            sr_bench: float = 0,
                            skew: float = 0,
                            kurt: float = 0,
                            alpha: float = 0.05) -> int:
    """
    Return n_min for given Sharpe at (1-alpha) confidence.

    Uses the same denominator as the Probabilistic Sharpe Ratio (Bailey & López de Prado, 2012).
    Note: kurtosis should be the raw kurtosis (not excess; i.e., Fisher + 3).
    """
    from math import isnan
    if sr_hat == sr_bench or isnan(sr_hat):
        return float("inf")
    z = sqrt(2) * erfinv(1 - 2*alpha)        # normal quantile
    # numerator and denominator per Bailey & López de Prado (2012)
    num = (1 - skew*sr_hat*sr_bench + (kurt-3)/4 * sr_hat**2) * z**2
    den = (sr_hat - sr_bench)**2
    return int(num/den + 1)


# --------------------------------------------------------------------------
# Probabilistic Sharpe Ratio (Bailey & López de Prado, 2012)
# --------------------------------------------------------------------------
def probabilistic_sharpe_ratio(sr_hat: float,
                               sr_bench: float,
                               n: int,
                               skew: float = 0,
                               kurt: float = 0) -> float:
    """
    Compute the Probabilistic Sharpe Ratio (PSR), i.e. the probability
    that the true Sharpe ratio exceeds `sr_bench`.

    PSR = Φ( (SR_hat - SR_bench) * sqrt(n-1)
             / sqrt(1 - γ SR_hat SR_bench + ((κ-3)/4) SR_hat²) )

    where   γ = skewness, κ = kurtosis, Φ = standard normal CDF.

    Parameters
    ----------
    sr_hat : float
        Observed (sample) Sharpe ratio.
    sr_bench : float
        Benchmark Sharpe ratio to beat (often 0).
    n : int
        Number of independent return observations.
    skew, kurt : float
        Sample skewness and kurtosis (kurtosis *not* excess).
    """
    if n <= 1:
        return 0.0
    # denominator per Bailey & LdP (2012)
    denom = math.sqrt(
        1 - skew * sr_hat * sr_bench + ((kurt - 3) / 4.0) * sr_hat ** 2
    )
    if denom == 0:
        return 0.0
    z = (sr_hat - sr_bench) * math.sqrt(n - 1) / denom
    # Φ(z)
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def simulate_and_run_strategy(args):
    """Generates a synthetic price path and runs a given strategy."""
    (
        worker_id,
        strategy_name,
        exec_type,           # 'LS' for long_short_strategy, 'BS' for buy_sell_strategy
        long_entry_fun,
        short_entry_fun,
        tp,
        sl,
        max_minutes,
        seed,
        original_df,
    ) = args

    # Generate one synthetic price path
    rng = np.random.default_rng(
        seed + worker_id
    )  # Ensure different paths for same strategy if worker_id is unique per path
    prices = simulate_path(original_df["close"].iloc[0], rng, original_df)
    synthetic = original_df.copy()
    synthetic["close"] = np.r_[original_df["close"].iloc[0], prices]
    synthetic["volume"] = original_df["volume"].mean()  # Use mean volume for simplicity

    # Add all necessary indicators. Assumes add_indicators populates:
    # EMA_10, EMA_30, SMA_50, SMA_200, rsi, MACD_12_26_9, MACDs_12_26_9
    synthetic = add_indicators(synthetic)

    # Optionally save some paths for debugging
    # Note: worker_id here might not be unique if N_PATHS is small and many strategies
    # A unique path_id for saving could be worker_id * num_strategies + strategy_index
    # For simplicity, we'll just use worker_id and accept potential overwrites if N_PATHS is very small.
    # if worker_id < 200:  # Save first few paths for inspection (per strategy)
    #     Path("debug").mkdir(exist_ok=True)
    #     # Sanitize strategy_name for filename
    #     safe_strategy_name = "".join(c if c.isalnum() else "_" for c in strategy_name)
    #     synthetic.to_parquet(f"debug/sim_path_{safe_strategy_name}_{worker_id}.parquet")

    if exec_type == "LS":
        # long + short variant
        result = long_short_strategy(
            synthetic,
            long_entry_fun=long_entry_fun,
            short_entry_fun=short_entry_fun,
            tp=tp,
            sl=sl,
            max_minutes=max_minutes,
        )
    else:  # 'BS' → buy/sell (long‑only)
        result = buy_sell_strategy(
            synthetic,
            long_entry_fun=long_entry_fun,
            sell_entry_fun=short_entry_fun,   # exit function reused
            tp=tp,
            sl=sl,
            max_minutes=max_minutes,
        )
    result["path_id"] = worker_id
    result["strategy_name"] = strategy_name
    result["exec_type"] = exec_type
    sr  = result["sharpe"]
    sk  = synthetic["close"].pct_change().skew()
    ku  = synthetic["close"].pct_change().kurt() + 3  # convert excess to regular
    n_obs = synthetic.shape[0]
    result["psr"] = probabilistic_sharpe_ratio(sr, 0.0, n_obs, sk, ku)
    result["MinTRL"] = min_track_record_length(sr, skew=sk, kurt=ku)
    return result


# --- 2. Monte‑Carlo loop (parallel) ----------------------------------------

# if __name__ == "__main__":
#     np.random.seed(SEED)

#     tasks = []
#     # Note: tasks now include exec_type before the long/short functions
#     # (i, strategy_name, exec_type, long_fun, short_fun, tp, sl, max_minutes, seed, original_df)
#     for strategy_name, funcs in STRATEGIES.items():
#         for i in range(N_PATHS):
#             # To run both executor types for each strategy and path:
#             # exec_variants = [("LS", funcs["long_entry_fun"], funcs["short_entry_fun"]),
#             #                  ("BS", funcs["long_entry_fun"], funcs["short_entry_fun"])]
#             # for exec_type, le_fun, se_fun in exec_variants:
#             #     tasks.append(
#             #         (
#             #             i,
#             #             strategy_name,
#             #             exec_type,
#             #             le_fun,
#             #             se_fun,
#             #             funcs["tp"],
#             #             funcs["sl"],
#             #             funcs["max_minutes"],
#             #             SEED,
#             #             original_df,
#             #         )
#             #     )
#             # Or for just one exec_type:
#             tasks.append(
#                 (i, strategy_name, "LS", funcs["long_entry_fun"], funcs["short_entry_fun"], funcs.get("tp"), funcs.get("sl"), funcs.get("max_minutes"), SEED, original_df)
#             )

#     with mp.Pool() as pool:
#         stats = list(
#             tqdm.tqdm(
#                 pool.imap_unordered(simulate_and_run_strategy, tasks), total=len(tasks)
#             )
#         )

#     mc_df = pd.DataFrame(stats)
#     mc_df.to_csv("mc_results.csv", index=False)
#     print(mc_df.describe(percentiles=[0.05, 0.5, 0.95]))
