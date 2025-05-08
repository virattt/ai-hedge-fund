import numpy as np
import pandas as pd
from pathlib import Path
from src.selv.indicators import add_indicators  # your TA helpers
from src.selv.backtest import run_strategy_on_df  # we'll write this wrapper next

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


# Strategy 1: EMA Crossover (10/30 min)
def long_ema_10_30_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for EMA 10/30 crossover."""
    return df["EMA_10"] > df["EMA_30"]


def short_ema_10_30_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for EMA 10/30 crossover."""
    return df["EMA_10"] < df["EMA_30"]


# Strategy 2: SMA Crossover (50/200 min - Golden/Death Cross)
def long_sma_50_200_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for SMA 50/200 crossover."""
    return df["SMA_50"] > df["SMA_200"]


def short_sma_50_200_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for SMA 50/200 crossover."""
    return df["SMA_50"] < df["SMA_200"]


# Strategy 3: RSI (Oversold/Overbought)
def long_rsi_30_70(df: pd.DataFrame) -> pd.Series:
    """Long entry for RSI < 30."""
    return df["rsi"] < 30


def short_rsi_30_70(df: pd.DataFrame) -> pd.Series:
    """Short entry for RSI > 70."""
    return df["rsi"] > 70


# Strategy 4: MACD Crossover (Standard)
def long_macd_cross(df: pd.DataFrame) -> pd.Series:
    """Long entry for MACD crossover."""
    return df["MACD_12_26_9"] > df["MACDs_12_26_9"]


def short_macd_cross(df: pd.DataFrame) -> pd.Series:
    """Short entry for MACD crossunder."""
    return df["MACD_12_26_9"] < df["MACDs_12_26_9"]


# Strategy 5: MACD + RSI (Confirmation)
def long_macd_rsi_confirm(df: pd.DataFrame) -> pd.Series:
    """Long entry for MACD crossover and RSI > 55."""
    return (df["MACD_12_26_9"] > df["MACDs_12_26_9"]) & (df["rsi"] > 55)


def short_macd_rsi_confirm(df: pd.DataFrame) -> pd.Series:
    """Short entry for MACD crossunder and RSI < 45."""
    return (df["MACD_12_26_9"] < df["MACDs_12_26_9"]) & (df["rsi"] < 45)


STRATEGIES = {
    "EMA_10_30_Cross": {
        "long_entry_fun": long_ema_10_30_cross,
        "short_entry_fun": short_ema_10_30_cross,
    },
    # "SMA_50_200_Cross": {
    #     "long_entry_fun": long_sma_50_200_cross,
    #     "short_entry_fun": short_sma_50_200_cross,
    # },
    # "RSI_30_70": {
    #     "long_entry_fun": long_rsi_30_70,
    #     "short_entry_fun": short_rsi_30_70,
    # },
    # "MACD_Cross": {
    #     "long_entry_fun": long_macd_cross,
    #     "short_entry_fun": short_macd_cross,
    # },
    # "MACD_RSI_Confirm": {  # This is the original default
    #     "long_entry_fun": long_macd_rsi_confirm,
    #     "short_entry_fun": short_macd_rsi_confirm,
    # },
}


def simulate_and_run_strategy(args):
    """Generates a synthetic price path and runs a given strategy."""
    worker_id, strategy_name, long_entry_fun, short_entry_fun, seed, original_df = args

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
    if worker_id < 200:  # Save first few paths for inspection (per strategy)
        Path("debug").mkdir(exist_ok=True)
        # Sanitize strategy_name for filename
        safe_strategy_name = "".join(c if c.isalnum() else "_" for c in strategy_name)
        synthetic.to_parquet(f"debug/sim_path_{safe_strategy_name}_{worker_id}.parquet")

    result = run_strategy_on_df(
        synthetic,
        long_entry_fun=long_entry_fun,
        short_entry_fun=short_entry_fun,
    )
    result["path_id"] = worker_id
    result["strategy_name"] = strategy_name
    return result


# --- 2. Monte‑Carlo loop (parallel) ----------------------------------------

# if __name__ == "__main__":
#     np.random.seed(SEED)

#     tasks = []
#     for strategy_name, funcs in STRATEGIES.items():
#         for i in range(N_PATHS):
#             # Each task: (unique_id_for_rng_and_path, strategy_name, long_func, short_func)
#             # To ensure unique paths for each (strategy, path_num) combination,
#             # we can use a global path counter for the seed or combine strategy index and path index.
#             # Here, (i) will be the path_id for a given strategy.
#             # The RNG seed will be SEED + i, meaning path i for strategy A is same as path i for strategy B.
#             # If truly independent paths are needed for each strategy-path combo, adjust seeding.
#             tasks.append(
#                 (i, strategy_name, funcs["long_entry_fun"], funcs["short_entry_fun"])
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
