"""Matplotlib visualizations for event study results.

Three chart types:

    plot_car_by_source    — grouped bar chart comparing mean CARs across
                            source types and windows (the "headline" chart)
    plot_car_distribution — histograms showing the spread of individual CARs
    plot_cumulative_ar    — day-by-day average cumulative AR path (shows PEAD)

All functions return a matplotlib Figure. The caller decides whether to
fig.savefig() or plt.show().
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from v2.event_study.models import EventStudyResult


def plot_car_by_source(result: EventStudyResult) -> Figure:
    """Grouped bar chart: mean CAR by source_type and event window.

    X-axis: event windows ([0,+1], [0,+5], [0,+20]).
    Each bar group: one bar per source_type (8-K, 10-Q, etc.).
    Y-axis: mean CAR in %.
    Error bars: bootstrap 95% CI (asymmetric).

    This is the primary chart — it answers "do earnings move prices,
    and does the signal differ by filing type?"
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Only plot source types that have computed window stats
    aggregates = [a for a in result.aggregates if a.windows]
    if not aggregates:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig

    # Collect all unique window labels and source types
    window_labels = sorted({w.window for a in aggregates for w in a.windows})
    source_types = [a.source_type for a in aggregates]
    x = np.arange(len(window_labels))
    width = 0.8 / len(source_types)  # bar width to fit all groups side by side

    for i, agg in enumerate(aggregates):
        window_map = {w.window: w for w in agg.windows}

        # Build arrays for bar heights and asymmetric error bars
        means = []
        errors_lo = []  # distance from mean to lower CI bound
        errors_hi = []  # distance from mean to upper CI bound
        for wl in window_labels:
            w = window_map.get(wl)
            if w:
                means.append(w.mean_car * 100)  # convert to %
                errors_lo.append((w.mean_car - w.ci.lower) * 100)
                errors_hi.append((w.ci.upper - w.mean_car) * 100)
            else:
                means.append(0)
                errors_lo.append(0)
                errors_hi.append(0)

        # Offset each source_type's bars so they don't overlap
        offset = (i - len(source_types) / 2 + 0.5) * width
        ax.bar(
            x + offset, means, width,
            yerr=[errors_lo, errors_hi], capsize=3,
            label=agg.source_type,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(window_labels)
    ax.set_ylabel("Mean CAR (%)")
    ax.set_title("Mean CAR by Source Type and Window")
    ax.axhline(0, color="black", linewidth=0.8)  # reference line at 0
    ax.legend()
    fig.tight_layout()
    return fig


def plot_car_distribution(
    result: EventStudyResult, window: str = "[0,+1]",
) -> Figure:
    """Histogram of individual event CARs, one subplot per source_type.

    Shows the spread of CARs — are they clustered or widely dispersed?
    Vertical lines at 0 (no effect) and at the mean (average effect).

    A tight distribution around a non-zero mean = consistent signal.
    A wide distribution = high variance, even if mean is significant.
    """
    # Map window labels to EventCAR attribute names
    car_attr = {"[0,+1]": "car_0_1", "[0,+5]": "car_0_5", "[0,+20]": "car_0_20"}
    attr = car_attr.get(window, "car_0_1")

    # Group individual CAR values by source_type
    groups: dict[str, list[float]] = {}
    for e in result.events:
        val = getattr(e, attr)
        if val is not None:
            groups.setdefault(e.source_type, []).append(val * 100)

    if not groups:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig

    # One subplot per source_type, arranged horizontally
    source_types = sorted(groups)
    fig, axes = plt.subplots(1, len(source_types), figsize=(6 * len(source_types), 5))
    if len(source_types) == 1:
        axes = [axes]

    for ax, st in zip(axes, source_types):
        vals = np.array(groups[st])
        ax.hist(vals, bins=20, edgecolor="black", alpha=0.7)
        ax.axvline(0, color="black", linewidth=0.8, linestyle="--")     # no-effect reference
        ax.axvline(vals.mean(), color="red", linewidth=1.5,              # sample mean
                   label=f"mean={vals.mean():.2f}%")
        ax.set_title(f"{st} — {window}")
        ax.set_xlabel("CAR (%)")
        ax.set_ylabel("Count")
        ax.legend()

    fig.tight_layout()
    return fig


def plot_cumulative_ar(
    result: EventStudyResult, source_type: str | None = None,
) -> Figure:
    """Average cumulative AR path from day 0 to day +20.

    This chart shows how the abnormal return accumulates day by day
    after the event. Key patterns to look for:

    - Sharp jump at day 0-1 → immediate market reaction
    - Continued drift → PEAD (post-earnings announcement drift)
    - Reversion → initial overreaction
    - Flat after day 1 → efficient pricing

    One line per source_type (or a single line if source_type is specified).
    Shaded band = ±1 standard error around the mean.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Group daily AR series by source_type
    groups: dict[str, list[list[float]]] = {}
    for e in result.events:
        if source_type is not None and e.source_type != source_type:
            continue
        if e.daily_ar:
            groups.setdefault(e.source_type, []).append(e.daily_ar)

    if not groups:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        return fig

    for st in sorted(groups):
        ar_lists = groups[st]

        # Pad shorter AR series with NaN so we can stack into a 2D array.
        # (Recent events may have fewer than 21 post-event days.)
        max_len = max(len(ar) for ar in ar_lists)
        padded = np.full((len(ar_lists), max_len), np.nan)
        for i, ar in enumerate(ar_lists):
            padded[i, : len(ar)] = ar

        # Cumulative sum along each row (each event's AR path)
        cum_ar = np.nancumsum(padded, axis=1)

        # Average across events: mean and standard error
        mean_car = np.nanmean(cum_ar, axis=0) * 100
        n_valid = np.sum(~np.isnan(cum_ar), axis=0)
        se_car = np.nanstd(cum_ar, axis=0, ddof=1) / np.sqrt(n_valid) * 100

        days = np.arange(max_len)
        ax.plot(days, mean_car, label=f"{st} (n={len(ar_lists)})")
        ax.fill_between(days, mean_car - se_car, mean_car + se_car, alpha=0.2)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Trading Days After Event")
    ax.set_ylabel("Cumulative AR (%)")
    ax.set_title("Average Cumulative Abnormal Return Path")
    ax.legend()
    fig.tight_layout()
    return fig
