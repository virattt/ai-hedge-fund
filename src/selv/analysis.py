"""
Analyze Monte‑Carlo back‑test results saved in ``mc_results.csv``.

This script:
1. Loads the CSV.
2. Separates each *strategy_name* into its own DataFrame.
3. Produces a summary table of key statistics.
4. Saves the summary to ``mc_summary.csv``.
5. Saves a Sharpe‑ratio box‑plot as ``sharpe_boxplot.png``.

Run it directly or import the helper functions in a notebook.
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def load_results(path: str | Path = "mc_results.csv") -> pd.DataFrame:
    """Load the Monte‑Carlo results CSV."""
    return pd.read_csv(path)


def split_by_strategy(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return a dict mapping strategy_name → DataFrame of that strategy’s runs."""
    return {name: grp.copy() for name, grp in df.groupby("strategy_name")}


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per‑strategy performance metrics.

    Returns a DataFrame sorted by mean Sharpe ratio.
    """
    grouped = df.groupby("strategy_name")
    summary = (
        grouped.agg(
            num_paths=("path_id", "nunique"),
            equity_mean=("equity", "mean"),
            equity_median=("equity", "median"),
            sharpe_mean=("sharpe", "mean"),
            sharpe_median=("sharpe", "median"),
            max_dd_mean=("max_dd", "mean"),
            max_dd_median=("max_dd", "median"),
        )
        .reset_index()
        .sort_values("sharpe_mean", ascending=False)
    )
    return summary


def plot_sharpe_distribution(
    df: pd.DataFrame,
    save_path: str | Path = "sharpe_boxplot.png",
) -> None:
    """Save a box‑plot of Sharpe ratios by strategy."""
    strategies = df["strategy_name"].unique()
    data = [df.loc[df["strategy_name"] == s, "sharpe"].values for s in strategies]

    plt.figure(figsize=(10, 6))
    plt.boxplot(data, labels=strategies, showmeans=True)
    plt.title("Sharpe Ratio Distribution by Strategy")
    plt.ylabel("Sharpe Ratio")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


# --------------------------------------------------------------------------- #
# Main runnable                                                               #
# --------------------------------------------------------------------------- #

def main() -> None:
    df = load_results()
    summary = summarize(df)
    summary.to_csv("mc_summary.csv", index=False)
    plot_sharpe_distribution(df)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()