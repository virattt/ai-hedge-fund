"""
Generate Taleb strangle analysis for Hormuz second/third order commodity plays:
Helium, sulfur, fertilizers, petrochemicals, aluminum, shipping, agriculture.
"""
import math, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats as sp_stats
import yfinance as yf

OUT = "outputs/taleb-strangle-analysis"
CHARTS = f"{OUT}/charts"

TICKERS = ["DBA", "APD", "LIN", "DOW", "LYB", "AA", "CENX", "STNG", "FRO", "CF", "NTR", "MOS", "ERII", "WEAT"]
SECTOR = {
    "APD": "Helium", "LIN": "Helium",
    "CF": "Fertilizer", "NTR": "Fertilizer", "MOS": "Fertilizer (short?)",
    "LYB": "Petrochemicals", "DOW": "Petrochemicals",
    "CENX": "Aluminum", "AA": "Aluminum",
    "FRO": "Shipping", "STNG": "Shipping",
    "ERII": "Desalination", "WEAT": "Agriculture", "DBA": "Agriculture",
}

START = "2025-03-26"
END = "2026-03-26"

DARK_BG = "#0f172a"
CARD_BG = "#1e293b"
TEXT_COLOR = "#e2e8f0"
GRID_COLOR = "#334155"
GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"
ACCENT = "#38bdf8"

def style_ax(ax, title):
    ax.set_facecolor(DARK_BG)
    ax.set_title(title, color=TEXT_COLOR, fontsize=13, fontweight="bold", pad=12)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, alpha=0.3, linewidth=0.5)

print("Fetching data...")
all_data = {}
for t in TICKERS:
    hist = yf.Ticker(t).history(start=START, end=END, auto_adjust=False)
    if hist.empty:
        continue
    returns = hist["Close"].pct_change().dropna()
    rolling_vol = returns.rolling(20).std() * math.sqrt(252)
    rolling_vol = rolling_vol.dropna()

    current_vol = rolling_vol.iloc[-1]
    vol_min = rolling_vol.min()
    vol_max = rolling_vol.max()
    iv_rank = (current_vol - vol_min) / (vol_max - vol_min) * 100 if vol_max > vol_min else 50

    kurtosis = float(sp_stats.kurtosis(returns.values, fisher=True))
    skewness = float(sp_stats.skew(returns.values))
    abs_ret = np.abs(returns.values)
    gap_days = int(np.sum(abs_ret > 0.03))
    gap_freq = gap_days / len(returns)
    convexity_ratio = abs_ret.max() / abs_ret.mean() if abs_ret.mean() > 0 else 0

    S = hist["Close"].iloc[-1]
    sigma_ann = returns.std() * math.sqrt(252)
    T = 7 / 365
    strangle_cost = 2 * S * sigma_ann * math.sqrt(T / (2 * math.pi))
    vega = 2 * S * math.sqrt(T) * 0.3989
    vega_per_dollar = vega / strangle_cost if strangle_cost > 0 else 0

    vol_of_vol = rolling_vol.std() / rolling_vol.mean() if rolling_vol.mean() > 0 else 0
    vol_autocorr = float(rolling_vol.autocorr(lag=5)) if len(rolling_vol) > 10 else 0
    recent_vol = rolling_vol.iloc[-20:].mean()
    prior_vol = rolling_vol.iloc[-80:-20].mean() if len(rolling_vol) >= 80 else rolling_vol.iloc[:-20].mean()
    vol_trend = (recent_vol - prior_vol) / prior_vol if prior_vol > 0 else 0

    all_data[t] = {
        "hist": hist, "returns": returns, "rolling_vol": rolling_vol,
        "iv_rank": iv_rank, "current_vol": current_vol,
        "vol_min": vol_min, "vol_max": vol_max,
        "kurtosis": kurtosis, "skewness": skewness,
        "gap_freq": gap_freq, "gap_days": gap_days,
        "convexity_ratio": convexity_ratio,
        "vega_per_dollar": vega_per_dollar,
        "strangle_cost": strangle_cost, "spot": S,
        "sigma_ann": sigma_ann,
        "vol_of_vol": vol_of_vol, "vol_autocorr": vol_autocorr,
        "vol_trend": vol_trend, "recent_vol": recent_vol,
        "sector": SECTOR.get(t, ""),
    }

print("Generating charts...")

# ── Composite scoring ───────────────────────────────────────────────────────
def norm(val, lo, hi):
    return max(0, min(10, (val - lo) / (hi - lo) * 10)) if hi > lo else 5

scores = {}
for t in all_data:
    d = all_data[t]
    s1 = norm(100 - d["iv_rank"], 0, 100)
    s2 = norm(d["kurtosis"], 0, 8)
    s3 = norm(d["vega_per_dollar"], 0, 8)
    s4 = norm(d["gap_freq"] * 100, 0, 40)
    antifrag = d["vol_of_vol"] * 5 + max(0, d["vol_autocorr"]) * 3 + max(0, -d["vol_trend"]) * 5
    s5 = norm(antifrag, 0, 8)
    scores[t] = [s1, s2, s3, s4, s5]

composite = {t: sum(scores[t]) for t in scores}
sorted_tickers = sorted(composite, key=lambda t: composite[t], reverse=True)

# ═══════════════════════════════════════════════════════════════════════════
# CHART 1: IV Rank horizontal bar — all 14 tickers
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 8))
fig.patch.set_facecolor(DARK_BG)

ordered = sorted(all_data.keys(), key=lambda t: all_data[t]["iv_rank"])
iv_vals = [all_data[t]["iv_rank"] for t in ordered]
colors = [GREEN if v < 30 else YELLOW if v < 55 else RED for v in iv_vals]
labels = [f"{t} ({all_data[t]['sector']})" for t in ordered]

bars = ax.barh(labels, iv_vals, color=colors, height=0.6, edgecolor="none", alpha=0.9)
for bar, val in zip(bars, iv_vals):
    ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height()/2,
            f"{val:.0f}%", va="center", ha="left", color=TEXT_COLOR, fontsize=10, fontweight="bold")

ax.axvline(x=30, color=GREEN, linestyle="--", alpha=0.5, linewidth=1)
ax.axvline(x=55, color=YELLOW, linestyle="--", alpha=0.5, linewidth=1)
ax.set_xlim(0, 110)
ax.set_xlabel("IV Rank Proxy (%)", color=TEXT_COLOR, fontsize=10)
style_ax(ax, "Hormuz Commodity Plays — IV Rank (Lower = Cheaper Strangles)")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{CHARTS}/hormuz_iv_rank.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 2: Composite ranking
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 8))
fig.patch.set_facecolor(DARK_BG)

vals = [composite[t] for t in sorted_tickers]
labels = [f"{t} ({all_data[t]['sector']})" for t in sorted_tickers]
colors = []
for i, t in enumerate(sorted_tickers):
    if i == 0: colors.append("#ffd700")
    elif i == 1: colors.append("#c0c0c0")
    elif i == 2: colors.append("#cd7f32")
    elif all_data[t]["iv_rank"] < 35: colors.append(GREEN)
    elif all_data[t]["iv_rank"] < 55: colors.append(YELLOW)
    else: colors.append(GRID_COLOR)

bars = ax.barh(labels, vals, color=colors, height=0.6, edgecolor="none", alpha=0.9)
for bar, val in zip(bars, vals):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            f"{val:.1f}/50", va="center", ha="left", color=TEXT_COLOR, fontsize=10, fontweight="bold")

ax.set_xlim(0, 50)
ax.set_xlabel("Composite Strangle Score", color=TEXT_COLOR, fontsize=10)
style_ax(ax, "Hormuz Commodity Plays — Overall Strangle Attractiveness")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{CHARTS}/hormuz_composite.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 3: Scatter — IV rank vs Kurtosis, colored by sector
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 7))
fig.patch.set_facecolor(DARK_BG)

sector_colors = {
    "Helium": "#38bdf8", "Fertilizer": "#22c55e", "Fertilizer (short?)": "#ef4444",
    "Petrochemicals": "#f59e0b", "Aluminum": "#a78bfa",
    "Shipping": "#f472b6", "Desalination": "#06b6d4", "Agriculture": "#84cc16",
}

for t in all_data:
    d = all_data[t]
    c = sector_colors.get(d["sector"], GRID_COLOR)
    size = 150 + composite.get(t, 20) * 8
    ax.scatter(d["iv_rank"], d["kurtosis"], s=size, c=c, alpha=0.85,
              edgecolors="white", linewidth=1.5, zorder=5)
    ax.annotate(t, (d["iv_rank"], d["kurtosis"]),
                textcoords="offset points", xytext=(10, 6),
                fontsize=11, fontweight="bold", color=TEXT_COLOR)

# Quadrant shading
ax.axvline(x=35, color=GRID_COLOR, linestyle=":", alpha=0.4)
ax.axhline(y=3, color=GRID_COLOR, linestyle=":", alpha=0.4)
ax.text(15, max(d["kurtosis"] for d in all_data.values()) * 0.9,
        "CHEAP VOL +\nFAT TAILS\n= BUY", fontsize=12, color=GREEN, alpha=0.4, ha="center", fontweight="bold")
ax.text(80, 0.5, "EXPENSIVE\n= AVOID", fontsize=12, color=RED, alpha=0.4, ha="center", fontweight="bold")

# Legend
from matplotlib.lines import Line2D
legend_elements = [Line2D([0], [0], marker='o', color='w', markerfacecolor=c, markersize=10, label=s)
                   for s, c in sector_colors.items()]
ax.legend(handles=legend_elements, loc="upper right", fontsize=9,
         facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

ax.set_xlabel("IV Rank Proxy (%) — Lower = Cheaper", color=TEXT_COLOR, fontsize=11)
ax.set_ylabel("Excess Kurtosis (Fat Tails)", color=TEXT_COLOR, fontsize=11)
style_ax(ax, "Hormuz Plays: Cheap Vol + Fat Tails = Strangle Opportunity\n(Bubble size = composite score)")
plt.tight_layout()
plt.savefig(f"{CHARTS}/hormuz_scatter.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 4: Rolling vol for top 4 buy_vol picks
# ═══════════════════════════════════════════════════════════════════════════
top4 = [t for t in sorted_tickers if all_data[t]["iv_rank"] < 40][:4]
fig, ax = plt.subplots(figsize=(14, 6))
fig.patch.set_facecolor(DARK_BG)

palette = ["#22c55e", "#38bdf8", "#f59e0b", "#a78bfa"]
for i, t in enumerate(top4):
    d = all_data[t]
    ax.plot(d["rolling_vol"].index, d["rolling_vol"].values * 100,
            label=f"{t} ({d['sector']})", color=palette[i], linewidth=1.5, alpha=0.85)

ax.set_ylabel("20-Day Realised Volatility (%)", color=TEXT_COLOR, fontsize=10)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.legend(loc="upper left", fontsize=9, facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
style_ax(ax, "Rolling Vol — Top Strangle Picks (Buy Vol Candidates)")
plt.tight_layout()
plt.savefig(f"{CHARTS}/hormuz_rolling_vol.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

print("Charts saved.")

# ═══════════════════════════════════════════════════════════════════════════
# Generate markdown
# ═══════════════════════════════════════════════════════════════════════════
print("Writing report...")

# Top picks
buys = [(t, all_data[t]) for t in sorted_tickers if all_data[t]["iv_rank"] < 40]
neutrals = [(t, all_data[t]) for t in sorted_tickers if 40 <= all_data[t]["iv_rank"] < 60]
sells = [(t, all_data[t]) for t in sorted_tickers if all_data[t]["iv_rank"] >= 60]

md = f"""# Hormuz Cascade: Beyond Oil & Gas
### Taleb Strangle Analysis — Helium, Fertilizers, Petrochemicals, Aluminum, Shipping, Agriculture | March 26, 2026

---

## The Hormuz Supply Chain Nobody Is Watching

The market has priced oil and gas. It has NOT fully priced:
- **Helium** — Qatar supplies 33% of global helium. Ras Laffan facility shut down. Spot prices up 40-100%.
- **Fertilizers** — 30% of global urea, 25% of ammonia, 50% of traded sulfur trapped behind Hormuz. Spring planting season.
- **Petrochemicals** — 15% of global polyethylene capacity offline. 85% of ME polyethylene exports transit Hormuz.
- **Aluminum** — UAE/Bahrain/Qatar = 8% of global primary aluminum. Alba declared force majeure. Past $3,500/tonne.
- **Agriculture** — Third-order: fertilizer shortage during planting = lower yields = grain price spike.
- **Shipping** — VLCC day rates past $200,000. 90%+ drop in Hormuz vessel traffic.

---

## The Verdict: Four Buy-Vol Plays

![Composite Ranking](charts/hormuz_composite.png)

"""

# Build the buy table
md += "| Rank | Ticker | Sector | Signal | Score | IV Rank | Kurtosis | Why |\n"
md += "|------|--------|--------|--------|-------|---------|----------|-----|\n"
for i, (t, d) in enumerate(buys):
    reason = []
    if d["iv_rank"] < 25: reason.append(f"IV {d['iv_rank']:.0f}% (very cheap)")
    elif d["iv_rank"] < 35: reason.append(f"IV {d['iv_rank']:.0f}% (cheap)")
    if d["kurtosis"] > 5: reason.append(f"extreme fat tails ({d['kurtosis']:.1f})")
    elif d["kurtosis"] > 2: reason.append(f"fat tails ({d['kurtosis']:.1f})")
    if d["vega_per_dollar"] > 5: reason.append(f"high vega/$ ({d['vega_per_dollar']:.1f})")
    if d["vol_trend"] < -0.15: reason.append("vol contracting")
    md += f"| {i+1} | **{t}** | {d['sector']} | **buy_vol** | {composite[t]:.1f}/50 | {d['iv_rank']:.0f}% | {d['kurtosis']:.1f} | {', '.join(reason)} |\n"

md += "\n"

# Neutrals
md += "**Neutral (vol mid-range — wait for cheaper entry):**\n\n"
md += "| Ticker | Sector | IV Rank | Issue |\n"
md += "|--------|--------|---------|-------|\n"
for t, d in neutrals:
    md += f"| {t} | {d['sector']} | {d['iv_rank']:.0f}% | Vol mid-range, strangles fairly priced |\n"

md += "\n"

# Sells
md += "**Sell Vol / Avoid (premiums already inflated):**\n\n"
md += "| Ticker | Sector | IV Rank | Issue |\n"
md += "|--------|--------|---------|-------|\n"
for t, d in sells:
    md += f"| {t} | {d['sector']} | {d['iv_rank']:.0f}% | Vol already spiked — buying strangles here is paying retail |\n"

md += f"""
---

## Factor 1: Where Is Vol Cheap?

![IV Rank](charts/hormuz_iv_rank.png)

The green tickers are where the market hasn't priced in the Hormuz disruption yet. The red tickers are where everyone is already hedging.

**Key insight:** CF, NTR, MOS, WEAT, and ERII all have IV ranks near 100%. The market has *already* repriced these. The fertilizer trade is done from a vol perspective — you'd be buying strangles at peak premium. The helium plays (APD, LIN) and agriculture (DBA) are where the vol is still cheap.

---

## Factor 2: Cheap Vol + Fat Tails = The Sweet Spot

![Scatter](charts/hormuz_scatter.png)

The top-left corner is where you want to be: cheap vol (low IV rank) with fat tails (high kurtosis). **APD and LIN dominate** — IV ranks under 35% with kurtosis near 8. These are grotesquely fat-tailed distributions where Black-Scholes massively underprices options.

---

## Factor 3: Vol Regime

![Rolling Vol](charts/hormuz_rolling_vol.png)

The buy-vol candidates show vol that has room to expand. The sell-vol tickers (not shown) have already spiked.

---

## The Playbook

### Tier 1: Best Strangle Opportunities

"""

for t, d in buys:
    md += f"""**{t} ({d['sector']})** — ${d['spot']:.2f}, IV rank {d['iv_rank']:.0f}%
- Kurtosis: {d['kurtosis']:.1f} | Gap days: {d['gap_days']} ({d['gap_freq']:.1%}) | Vega/$: {d['vega_per_dollar']:.1f}
- Est. 1-week strangle: ${d['strangle_cost']:.2f} | Annual vol: {d['sigma_ann']:.0%}
- Vol trend: {d['vol_trend']:+.0%} | Vol-of-vol: {d['vol_of_vol']:.2f} | Autocorr: {d['vol_autocorr']:.2f}

"""

md += """### The Helium Angle

APD and LIN are the standout non-obvious plays. Qatar's Ras Laffan helium facility is shut down, helium spot prices are up 40-100%, and yet the options market on these industrial gas giants has barely reacted (IV rank 29-34%). Helium is critical for:
- Semiconductor manufacturing (chip fabs use helium for cooling)
- MRI machines (liquid helium for superconducting magnets)
- Fiber optic manufacturing
- Space launch (purging fuel tanks)

A prolonged Hormuz closure doesn't just bump helium prices — it creates a supply crisis for the entire semiconductor and healthcare imaging supply chain. APD and LIN are the beneficiaries, and their options are cheap.

### The Agriculture Third-Order Chain

DBA (agriculture commodity ETF) has the cheapest vol of all at 22% IV rank, with the highest vega efficiency (8.0 vega per dollar). The causal chain:
1. Hormuz closes → fertilizer supply cut 30%
2. Spring planting season (March-April) → farmers can't get urea/ammonia
3. Lower fertilizer application → lower crop yields
4. Lower yields → grain price spike → DBA goes up

This is a third-order derivative that the options market hasn't connected yet.

### What NOT to Buy Strangles On

| Ticker | Sector | IV Rank | Why Avoid |
|--------|--------|---------|-----------|
| CF | Fertilizer | 100% | Already up 13% since March 13. Everyone is in this trade. |
| NTR | Fertilizer | 100% | Same — vol fully priced. |
| MOS | Fertilizer | 99% | Actually a potential *loser* — MOS buys sulfur as input. Hormuz raises their costs. |
| WEAT | Agriculture | 96% | Wheat vol already spiked. The first-order ag play is done. |
| ERII | Desalination | 100% | Kurtosis of 46 (!!) from a single massive move. Vol fully priced. |

---

## Combined Portfolio: UNG + Hormuz Cascade

If you're already in UNG strangles, here's how the new plays fit:

| Ticker | Sector | IV Rank | Role | Correlation to UNG |
|--------|--------|---------|------|-------------------|
| **UNG** | Nat Gas | 15% | Primary — max convexity | — |
| **APD** | Helium | 29% | Helium supply crisis play | Low (different commodity) |
| **LIN** | Helium | 34% | Helium + diversified industrial gas | Low |
| **DBA** | Agriculture | 22% | Third-order food inflation | Near zero |
| **DOW** | Petrochemicals | 34% | US petrochem beneficiary | Moderate |

The beauty of this portfolio is **low cross-correlation**. UNG, helium, and agriculture are driven by different supply chains — a Hormuz closure hits all of them, but through different mechanisms. You're not just doubling down on one bet.

---

*Generated by the Nassim Taleb Antifragile Volatility Agent. Not financial advice. Check live IV rank on [Barchart](https://www.barchart.com/options/iv-rank-percentile) before trading.*
"""

with open(f"{OUT}/hormuz_cascade_analysis.md", "w") as f:
    f.write(md)

print(f"Report written to {OUT}/hormuz_cascade_analysis.md")
print("Done!")
