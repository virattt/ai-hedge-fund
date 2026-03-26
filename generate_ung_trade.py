"""
Generate visualizations for the specific UNG $12 straddle trade.
23 contracts, $0.85 entry, April 2 expiry (6 days).
"""
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyArrowPatch
import yfinance as yf

OUT = "outputs/taleb-strangle-analysis/charts"

# Trade parameters
SPOT = 11.98
STRIKE = 12.00
STRADDLE_COST = 0.85
CONTRACTS = 23
TOTAL_COST = STRADDLE_COST * 100 * CONTRACTS  # $1,955
BE_UP = STRIKE + STRADDLE_COST    # 12.85
BE_DOWN = STRIKE - STRADDLE_COST  # 11.15

# Colors
DARK_BG = "#0f172a"
CARD_BG = "#1e293b"
TEXT_COLOR = "#e2e8f0"
GRID_COLOR = "#334155"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#eab308"
ACCENT = "#38bdf8"
PURPLE = "#a78bfa"

def style_ax(ax, title):
    ax.set_facecolor(DARK_BG)
    ax.set_title(title, color=TEXT_COLOR, fontsize=13, fontweight="bold", pad=12)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, alpha=0.3, linewidth=0.5)

# Fetch historical weekly returns for probability overlay
print("Fetching UNG history...")
ung = yf.Ticker("UNG")
hist = ung.history(start="2025-03-26", end="2026-03-26", auto_adjust=False)
weekly_returns = hist["Close"].resample("W").last().pct_change().dropna()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 1: P&L at expiry — the classic hockey stick
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor(DARK_BG)

prices = np.linspace(8, 16, 500)
pnl_per_share = np.maximum(STRIKE - prices, 0) + np.maximum(prices - STRIKE, 0) - STRADDLE_COST
pnl_total = pnl_per_share * 100 * CONTRACTS

# Color fill
ax.fill_between(prices, pnl_total, 0, where=pnl_total > 0, color=GREEN, alpha=0.2)
ax.fill_between(prices, pnl_total, 0, where=pnl_total <= 0, color=RED, alpha=0.2)
ax.plot(prices, pnl_total, color=ACCENT, linewidth=2.5)

# Zero line
ax.axhline(y=0, color=TEXT_COLOR, linewidth=0.8, alpha=0.5)

# Breakeven markers
ax.axvline(x=BE_DOWN, color=YELLOW, linestyle="--", linewidth=1.5, alpha=0.7)
ax.axvline(x=BE_UP, color=YELLOW, linestyle="--", linewidth=1.5, alpha=0.7)
ax.axvline(x=SPOT, color=PURPLE, linestyle=":", linewidth=1.5, alpha=0.7)

# Labels
ax.annotate(f"Breakeven\n${BE_DOWN:.2f}\n(-6.9%)", xy=(BE_DOWN, 50), fontsize=9,
            color=YELLOW, ha="center", fontweight="bold")
ax.annotate(f"Breakeven\n${BE_UP:.2f}\n(+7.3%)", xy=(BE_UP, 50), fontsize=9,
            color=YELLOW, ha="center", fontweight="bold")
ax.annotate(f"Spot ${SPOT}", xy=(SPOT, -TOTAL_COST + 200), fontsize=9,
            color=PURPLE, ha="center", fontweight="bold")

# Key P&L points
scenarios = [
    (9.58, "-20%"), (10.18, "-15%"), (10.78, "-10%"),
    (13.18, "+10%"), (13.77, "+15%"), (14.38, "+20%"),
]
for price, label in scenarios:
    pnl = (max(STRIKE - price, 0) + max(price - STRIKE, 0) - STRADDLE_COST) * 100 * CONTRACTS
    marker_color = GREEN if pnl > 0 else RED
    ax.plot(price, pnl, "o", color=marker_color, markersize=8, zorder=5)
    sign = "+" if pnl > 0 else ""
    ax.annotate(f"{label}\n{sign}${pnl:,.0f}", xy=(price, pnl),
                textcoords="offset points", xytext=(0, 18 if pnl > 0 else -25),
                fontsize=8, color=marker_color, ha="center", fontweight="bold")

# Max loss annotation
ax.annotate(f"Max loss: -${TOTAL_COST:,.0f}\n(UNG stays flat)", xy=(STRIKE, -TOTAL_COST),
            textcoords="offset points", xytext=(50, -15),
            fontsize=10, color=RED, ha="center", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=RED, lw=1.5))

ax.set_xlabel("UNG Price at Expiry (April 2)", color=TEXT_COLOR, fontsize=11)
ax.set_ylabel("Profit / Loss ($)", color=TEXT_COLOR, fontsize=11)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
style_ax(ax, f"UNG $12 Straddle — 23 Contracts @ $0.85 ($1,955 Total)")
plt.tight_layout()
plt.savefig(f"{OUT}/ung_straddle_pnl.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()
print("  Chart 1: P&L at expiry")

# ═══════════════════════════════════════════════════════════════════════════
# CHART 2: Historical weekly moves with breakeven overlay
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 5))
fig.patch.set_facecolor(DARK_BG)

moves = weekly_returns.values * 100
colors = [GREEN if abs(m) > (STRADDLE_COST / SPOT * 100) else RED for m in moves]
dates = weekly_returns.index

ax.bar(range(len(moves)), moves, color=colors, width=0.8, alpha=0.8, edgecolor="none")

# Breakeven band
be_pct = STRADDLE_COST / SPOT * 100
ax.axhline(y=be_pct, color=YELLOW, linestyle="--", linewidth=1.5, alpha=0.7)
ax.axhline(y=-be_pct, color=YELLOW, linestyle="--", linewidth=1.5, alpha=0.7)
ax.axhline(y=0, color=TEXT_COLOR, linewidth=0.5, alpha=0.3)

# Fill the "loss zone"
ax.axhspan(-be_pct, be_pct, color=RED, alpha=0.08)

# Stats
profitable_weeks = sum(1 for m in moves if abs(m) > be_pct)
total_weeks = len(moves)
win_rate = profitable_weeks / total_weeks

ax.text(len(moves) - 1, max(moves) - 3,
        f"Profitable: {profitable_weeks}/{total_weeks} weeks ({win_rate:.0%})",
        fontsize=11, color=GREEN, ha="right", fontweight="bold")
ax.text(len(moves) - 1, max(moves) - 7,
        f"Loss zone: {total_weeks - profitable_weeks}/{total_weeks} weeks ({1-win_rate:.0%})",
        fontsize=11, color=RED, ha="right", fontweight="bold")

# X axis — show months
month_ticks = []
month_labels = []
for i, d in enumerate(dates):
    if i == 0 or d.month != dates[i-1].month:
        month_ticks.append(i)
        month_labels.append(d.strftime("%b '%y"))
ax.set_xticks(month_ticks)
ax.set_xticklabels(month_labels, rotation=45, ha="right")

ax.set_ylabel("Weekly Return (%)", color=TEXT_COLOR, fontsize=10)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))

# Annotations
ax.annotate("Breakeven +7.1%", xy=(len(moves)+0.5, be_pct), fontsize=8, color=YELLOW, va="center")
ax.annotate("Breakeven -7.1%", xy=(len(moves)+0.5, -be_pct), fontsize=8, color=YELLOW, va="center")

style_ax(ax, "Every UNG Week in the Past Year — Green = Your Straddle Would Have Profited")
plt.tight_layout()
plt.savefig(f"{OUT}/ung_weekly_history.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()
print("  Chart 2: Weekly history")

# ═══════════════════════════════════════════════════════════════════════════
# CHART 3: Probability distribution of outcomes
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 5))
fig.patch.set_facecolor(DARK_BG)

# Simulate 10,000 outcomes using historical weekly return distribution
np.random.seed(42)
simulated_returns = np.random.choice(weekly_returns.values, size=10000, replace=True)
simulated_prices = SPOT * (1 + simulated_returns)
simulated_pnl = (np.maximum(STRIKE - simulated_prices, 0) + np.maximum(simulated_prices - STRIKE, 0) - STRADDLE_COST) * 100 * CONTRACTS

# Histogram
bins = np.linspace(-TOTAL_COST - 200, 8000, 80)
n, bin_edges, patches = ax.hist(simulated_pnl, bins=bins, density=True, edgecolor="none", alpha=0.8)
for patch, left_edge in zip(patches, bin_edges[:-1]):
    if left_edge >= 0:
        patch.set_facecolor(GREEN)
    else:
        patch.set_facecolor(RED)

ax.axvline(x=0, color=YELLOW, linewidth=2, linestyle="--", alpha=0.8)

# Stats
prob_profit = (simulated_pnl > 0).mean()
avg_profit_when_win = simulated_pnl[simulated_pnl > 0].mean()
avg_loss_when_lose = simulated_pnl[simulated_pnl <= 0].mean()
expected_value = simulated_pnl.mean()
median_pnl = np.median(simulated_pnl)
p90_pnl = np.percentile(simulated_pnl, 90)
p10_pnl = np.percentile(simulated_pnl, 10)

stats_text = (
    f"Win probability: {prob_profit:.0%}\n"
    f"Expected value: ${expected_value:+,.0f}\n"
    f"Median outcome: ${median_pnl:+,.0f}\n"
    f"Avg win: +${avg_profit_when_win:,.0f}\n"
    f"Avg loss: ${avg_loss_when_lose:,.0f}\n"
    f"Best 10%: > +${p90_pnl:,.0f}\n"
    f"Worst 10%: < ${p10_pnl:,.0f}"
)
ax.text(0.97, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
        color=TEXT_COLOR, ha="right", va="top", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD_BG, edgecolor=GRID_COLOR))

ax.set_xlabel("Profit / Loss ($)", color=TEXT_COLOR, fontsize=11)
ax.set_ylabel("Probability Density", color=TEXT_COLOR, fontsize=10)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:+,.0f}"))
style_ax(ax, "Simulated P&L Distribution (10,000 Trials Based on Historical Weekly Returns)")
plt.tight_layout()
plt.savefig(f"{OUT}/ung_pnl_distribution.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()
print("  Chart 3: P&L distribution")

# ═══════════════════════════════════════════════════════════════════════════
# CHART 4: Theta decay — what your straddle is worth each day
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor(DARK_BG)

# Simplified BS straddle value over time (ATM approximation)
# Straddle ≈ 2 * S * σ * sqrt(T / 2π)
sigma = 0.65  # ~65% IV from the chain
days = np.array([6, 5, 4, 3, 2, 1, 0.5, 0.1])
day_labels = ["Wed\n(today)", "Thu", "Fri", "Mon", "Tue\n(expiry-1)", "Wed\n(expiry)", "", ""]
straddle_values = 2 * SPOT * sigma * np.sqrt((days / 365) / (2 * np.pi))

# Only show first 6 meaningful days
days_plot = days[:6]
values_plot = straddle_values[:6]
labels_plot = day_labels[:6]

ax.plot(range(len(days_plot)), values_plot, color=RED, linewidth=3, marker="o", markersize=10, zorder=5)

for i, (d, v) in enumerate(zip(days_plot, values_plot)):
    ax.annotate(f"${v:.2f}\n(${v*100*CONTRACTS:,.0f})",
                xy=(i, v), textcoords="offset points", xytext=(0, 18),
                fontsize=9, color=TEXT_COLOR, ha="center", fontweight="bold")

# Your entry line
ax.axhline(y=STRADDLE_COST, color=GREEN, linestyle="--", linewidth=1.5, alpha=0.5)
ax.text(0.1, STRADDLE_COST + 0.02, f"Your entry: ${STRADDLE_COST}", color=GREEN, fontsize=10)

ax.set_xticks(range(len(labels_plot)))
ax.set_xticklabels(labels_plot)
ax.set_ylabel("Straddle Value (per share)", color=TEXT_COLOR, fontsize=10)
ax.set_ylim(0, 1.2)
style_ax(ax, "Theta Decay — Your Straddle Loses Value Every Day UNG Stays Flat")

# Add warning
ax.text(0.5, 0.15, "IF UNG DOESN'T MOVE, this is what happens to your $1,955",
        transform=ax.transAxes, fontsize=11, color=RED, ha="center", alpha=0.7, fontweight="bold")

plt.tight_layout()
plt.savefig(f"{OUT}/ung_theta_decay.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()
print("  Chart 4: Theta decay")

print(f"\nAll charts saved to {OUT}/")
print("Done!")
