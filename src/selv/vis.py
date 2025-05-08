#!/usr/bin/env python
"""
plot_synthetic_paths.py
Usage:  python plot_synthetic_paths.py
Requires: pandas, matplotlib, pyarrow (Parquet engine)
"""

from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt

def plot_synthetic_paths(debug_dir_path="src/selv/debug", save_path=None, figsize=(12, 8), alpha=0.6):
    """
    Load and plot synthetic price paths from parquet files.
    
    Parameters:
    -----------
    debug_dir_path : str or Path
        Directory containing the synthetic path parquet files.
    save_path : str or Path, optional
        If provided, save the plot to this path. 
    figsize : tuple, default (12, 8)
        Figure size for the plot.
    alpha : float, default 0.6
        Transparency value for plot lines.
        
    Returns:
    --------
    matplotlib.figure.Figure
        The plot figure object.
    pandas.DataFrame
        The combined dataframe of all loaded paths.
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    
    # Convert to Path object if string
    debug_dir = Path(debug_dir_path)
    
    # Find parquet files
    files = sorted(debug_dir.glob("sim_path_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No sim_path_*.parquet files found in {debug_dir}")
    
    # Regex to extract strategy and path_id from filename
    name_re = re.compile(r"^sim_path_(.+)_(\d+)\.parquet$")
    
    # Load each file into a list
    frames = []
    for f in files:
        m = name_re.match(f.name)
        if not m:
            continue
        
        strategy = m.group(1).replace("_", " ")
        path_id = int(m.group(2))
        
        try:
            df = pd.read_parquet(f)
            
            # Ensure datetime index is a column for plotting
            df = df.reset_index(names="datetime")
            
            df["strategy"] = strategy
            df["path_id"] = path_id
            frames.append(df[["datetime", "close", "strategy", "path_id"]])
        except Exception:
            pass  # Silently skip files with errors
    
    if not frames:
        raise ValueError("No valid dataframes could be loaded")
    
    # Combine everything into one big tidy frame
    mc = pd.concat(frames, ignore_index=True)
    
    # Create plot
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot each path
    for (strategy, path_id), g in mc.groupby(["strategy", "path_id"]):
        ax.plot(g["datetime"], g["close"],
                alpha=alpha, linewidth=0.8,
                label=f"{strategy} | id {path_id}")
    
    ax.set_title("Synthetic BTC Price Paths")
    ax.set_xlabel("Datetime")
    ax.set_ylabel("Price")
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize="small")
    plt.tight_layout()
    
    # Save if requested
    if save_path:
        plt.savefig(save_path)
    
    return fig, mc


def compare_strategies(data, metric="close", figsize=(12, 6)):
    """
    Compare the performance of different strategies side by side.
    
    Parameters:
    -----------
    data : pandas.DataFrame
        Combined dataframe with multiple strategies and paths.
    metric : str, default "close"
        The column to use for comparison.
    figsize : tuple, default (12, 6)
        Figure size for the plot.
        
    Returns:
    --------
    matplotlib.figure.Figure
        The plot figure object.
    """
    
    # Calculate mean values per strategy
    strategy_means = data.groupby(['strategy', 'datetime'])[metric].mean().unstack('strategy')
    
    # Create comparison plot
    fig, ax = plt.subplots(figsize=figsize)
    strategy_means.plot(ax=ax)
    
    ax.set_title(f"Strategy Comparison - Average {metric.capitalize()}")
    ax.set_xlabel("Datetime")
    ax.set_ylabel(metric.capitalize())
    plt.legend(title="Strategy")
    plt.tight_layout()
    
    return fig


def analyze_monte_carlo_results(results_path="mc_results.csv"):
    """
    Analyze the Monte Carlo simulation results.
    
    Parameters:
    -----------
    results_path : str or Path, default "mc_results.csv"
        Path to the CSV file with Monte Carlo results.
        
    Returns:
    --------
    pandas.DataFrame
        A summary dataframe with statistics by strategy.
    matplotlib.figure.Figure
        A boxplot showing distribution of key metrics.
    """
    
    # Load results
    mc_df = pd.read_csv(results_path)
    
    # Calculate statistics by strategy
    summary = mc_df.groupby('strategy_name').agg({
        'equity': ['mean', 'median', 'std', 'min', 'max'],
        'sharpe': ['mean', 'median', 'std', 'min', 'max'],
        'max_dd': ['mean', 'median', 'std', 'min', 'max']
    })
    
    # Create boxplots
    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    
    # Plot equity, sharpe, and max_dd distributions by strategy
    mc_df.boxplot('equity', by='strategy_name', ax=axes[0])
    mc_df.boxplot('sharpe', by='strategy_name', ax=axes[1])
    mc_df.boxplot('max_dd', by='strategy_name', ax=axes[2])
    
    axes[0].set_title('Final Equity by Strategy')
    axes[1].set_title('Sharpe Ratio by Strategy')
    axes[2].set_title('Maximum Drawdown by Strategy')
    
    plt.suptitle('Monte Carlo Simulation Results')
    plt.tight_layout()
    
    return summary, fig