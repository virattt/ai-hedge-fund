"""
Generate Taleb strangle report for LNG/Hormuz supply chain plays.
"""
import math, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats as sp_stats
import yfinance as yf

OUT = "outputs/taleb-strangle-analysis/lng-hormuz"

with open("outputs/taleb-strangle-analysis/lng_hormuz_data.json") as f:
    summary = json.load(f)

TICKERS = list(summary.keys())
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

# Fetch price history for charts
print("Fetching data for charts...")
hist_data = {}
for t in TICKERS:
    try:
        hist = yf.Ticker(t).history(start=START, end=END, auto_adjust=False)
        if not hist.empty:
            returns = hist['Close'].pct_change().dropna()
            rolling_vol = returns.rolling(20).std() * math.sqrt(252)
            hist_data[t] = {'hist': hist, 'returns': returns, 'rolling_vol': rolling_vol.dropna()}
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# CHART 1: Composite ranking
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor(DARK_BG)

sorted_t = sorted(TICKERS, key=lambda t: summary[t]['composite'], reverse=True)
vals = [summary[t]['composite'] for t in sorted_t]
labels = [f"{t}\n{summary[t]['desc'][:25]}" for t in sorted_t]
colors = []
for i, t in enumerate(sorted_t):
    iv = summary[t]['iv_rank']
    if i == 0: colors.append("#ffd700")
    elif i == 1: colors.append("#c0c0c0")
    elif iv < 30: colors.append(GREEN)
    elif iv < 55: colors.append(YELLOW)
    else: colors.append(GRID_COLOR)

bars = ax.barh(labels, vals, color=colors, height=0.6, alpha=0.9)
for bar, val, t in zip(bars, vals, sorted_t):
    d = summary[t]
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            f"{val:.1f}/50 | IV:{d['iv_rank']:.0f}% | Win:{d['win_rate']:.0%} | ROI:{d['avg_roi']:+.0f}%",
            va="center", ha="left", color=TEXT_COLOR, fontsize=9, fontweight="bold")

ax.set_xlim(0, 55)
style_ax(ax, "LNG/Hormuz Supply Chain — Strangle Attractiveness Ranking")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUT}/composite_ranking.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 2: IV Rank bars
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor(DARK_BG)

iv_order = sorted(TICKERS, key=lambda t: summary[t]['iv_rank'])
iv_vals = [summary[t]['iv_rank'] for t in iv_order]
iv_colors = [GREEN if v < 30 else YELLOW if v < 55 else RED for v in iv_vals]
iv_labels = [f"{t}" for t in iv_order]

bars = ax.barh(iv_labels, iv_vals, color=iv_colors, height=0.6, alpha=0.9)
for bar, val in zip(bars, iv_vals):
    ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height()/2,
            f"{val:.0f}%", va="center", ha="left", color=TEXT_COLOR, fontsize=11, fontweight="bold")

ax.axvline(x=30, color=GREEN, linestyle="--", alpha=0.5)
ax.axvline(x=55, color=YELLOW, linestyle="--", alpha=0.5)
ax.set_xlim(0, 110)
style_ax(ax, "IV Rank — Where Is Vol Cheap?")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(f"{OUT}/iv_rank.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 3: Rolling vol — UNG vs BOIL vs others
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(14, 6))
fig.patch.set_facecolor(DARK_BG)

palette = {"UNG": "#22c55e", "BOIL": "#38bdf8", "NEXT": "#f59e0b", "LNG": "#a78bfa", "EWJ": "#f472b6", "COPX": "#ef4444", "EWY": "#06b6d4"}
for t in ['UNG', 'BOIL', 'NEXT', 'LNG', 'EWJ']:
    if t in hist_data:
        rv = hist_data[t]['rolling_vol']
        ax.plot(rv.index, rv.values * 100, label=t, color=palette.get(t, GRID_COLOR), linewidth=1.5, alpha=0.85)

ax.set_ylabel("20-Day Realised Volatility (%)", color=TEXT_COLOR, fontsize=10)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.legend(loc="upper left", fontsize=9, facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
style_ax(ax, "Rolling 20-Day Realised Vol — LNG Supply Chain")
plt.tight_layout()
plt.savefig(f"{OUT}/rolling_vol.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 4: UNG vs BOIL head-to-head
# ═══════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.patch.set_facecolor(DARK_BG)

for ax, t, color in zip(axes, ['UNG', 'BOIL'], [GREEN, ACCENT]):
    if t not in hist_data:
        continue
    rets = hist_data[t]['returns'].values
    ax.hist(rets, bins=60, density=True, color=color, alpha=0.7, edgecolor="none")
    x_range = np.linspace(rets.min(), rets.max(), 200)
    normal_pdf = sp_stats.norm.pdf(x_range, rets.mean(), rets.std())
    ax.plot(x_range, normal_pdf, color=RED, linewidth=2, linestyle="--", label="Normal", alpha=0.8)
    kurt = sp_stats.kurtosis(rets, fisher=True)
    style_ax(ax, f"{t} — Kurt: {kurt:.1f} | Gap: {(np.abs(rets)>0.03).mean():.0%}")
    ax.legend(fontsize=8, facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

plt.suptitle("Return Distributions — UNG vs BOIL (2x Leveraged)", color=TEXT_COLOR, fontsize=13, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(f"{OUT}/ung_vs_boil.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 5: Scatter — IV rank vs win rate, sized by ROI
# ═══════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12, 7))
fig.patch.set_facecolor(DARK_BG)

sector_colors = {
    "UNG": "#22c55e", "BOIL": "#38bdf8", "NEXT": "#f59e0b",
    "LNG": "#a78bfa", "EWJ": "#f472b6", "EWY": "#06b6d4", "COPX": "#ef4444",
}

for t in TICKERS:
    d = summary[t]
    c = sector_colors.get(t, GRID_COLOR)
    size = max(100, 200 + d['avg_roi'] * 5)
    ax.scatter(d['iv_rank'], d['win_rate'] * 100, s=size, c=c, alpha=0.85,
              edgecolors="white", linewidth=1.5, zorder=5)
    ax.annotate(f"{t}\nROI:{d['avg_roi']:+.0f}%", (d['iv_rank'], d['win_rate'] * 100),
                textcoords="offset points", xytext=(12, 5),
                fontsize=10, fontweight="bold", color=TEXT_COLOR)

ax.axvline(x=30, color=GREEN, linestyle=":", alpha=0.4)
ax.axhline(y=30, color=GREEN, linestyle=":", alpha=0.4)
ax.text(10, 45, "SWEET\nSPOT", fontsize=14, color=GREEN, alpha=0.3, ha="center", fontweight="bold")
ax.text(80, 10, "AVOID", fontsize=14, color=RED, alpha=0.3, ha="center", fontweight="bold")

ax.set_xlabel("IV Rank (%) — Lower = Cheaper Vol", color=TEXT_COLOR, fontsize=11)
ax.set_ylabel("Historical Win Rate (%)", color=TEXT_COLOR, fontsize=11)
style_ax(ax, "Cheap Vol + High Win Rate = The Play")
plt.tight_layout()
plt.savefig(f"{OUT}/iv_vs_winrate.png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close()

print("Charts saved.")

# ═══════════════════════════════════════════════════════════════════════════
# Generate markdown
# ═══════════════════════════════════════════════════════════════════════════
print("Writing report...")

md = """# LNG & Hormuz Supply Chain: Taleb Strangle Analysis
### Long Vega Opportunities Across the Natural Gas / Energy Import Chain | March 26, 2026

---

## The Thesis

Qatar = 20% of global LNG. All flows through Hormuz. The Navy escort pledge calmed the market, but TotalEnergies CEO says LNG goes "very high" by summer. If escorts fail or escalation widens, the cascade hits:

1. **Direct:** UNG, BOIL (nat gas price)
2. **Replacement suppliers:** LNG, NEXT (US LNG exporters surge on panic buying)
3. **Victims:** EWJ, EWY (Japan/Korea import 90% of energy, ~40% through Hormuz)
4. **Third order:** COPX (Asia manufacturing disruption → copper demand destruction)

---

## The Ranking: Two Plays, Five Pretenders

![Composite Ranking](composite_ranking.png)

"""

for t in sorted_t:
    d = summary[t]
    if d['iv_rank'] < 30:
        signal = "**BUY VOL**"
    elif d['iv_rank'] < 55:
        signal = "NEUTRAL"
    else:
        signal = "SELL VOL"
    md += f"| {t} | {d['desc'][:30]} | {signal} | IV:{d['iv_rank']:.0f}% | Win:{d['win_rate']:.0%} | ROI:{d['avg_roi']:+.0f}% | ${d['real_cost']:.0f}/ct |\n"

md += f"""
---

## Factor 1: Where Is Vol Cheap?

![IV Rank](iv_rank.png)

**Only two tickers have cheap vol: UNG (15%) and BOIL (21%).** Everything else is mid-range to expensive.

This is the critical finding: the market has already repriced vol on the LNG supply chain. Cheniere (LNG) is at 67% IV rank — already up 12.7% since Mar 13. EWY is at 97% — essentially peak vol. COPX at 69%.

The only places the market *hasn't* repriced: the nat gas instruments themselves, because they've been *falling* (UNG -6.2% since Mar 13) while IV has contracted from the Feb spike. Counter-intuitive but perfect for strangles — the underlying dropped, vol dropped, but the catalyst risk is higher than ever.

---

## Factor 2: UNG vs BOIL — The Real Question

![UNG vs BOIL](ung_vs_boil.png)

BOIL is ProShares 2x leveraged natural gas. It scores almost identically to UNG (37.2 vs 37.4). Here's the comparison:

| | UNG | BOIL |
|---|---|---|
| IV Rank | 15% | 21% |
| HV30 | 44% | 88% |
| Kurtosis | 7.1 | **8.9** |
| Gap frequency | 39% | **63%** |
| Win rate | 41% | 42% |
| Avg ROI | +4% | +4% |
| Straddle cost | **$85/ct** | $217/ct |
| Breakeven | **7.2%** | 13.1% |
| UNG correlation | 1.00 | 0.99 |

**BOIL has fatter tails (8.9 kurtosis) and more gap days (63%!!)** but requires a 13.1% move to break even vs UNG's 7.2%. The 2x leverage amplifies both the move AND the premium, so the ROI ends up identical (+4%).

**The practical difference:** BOIL costs $217/contract vs UNG's $85. On your $1,500/week Kelly budget:
- UNG: 17 contracts — more granular position management
- BOIL: 6 contracts — fewer but each one is a bigger leveraged bet

**Recommendation:** Stick with UNG. The lower breakeven (7.2% vs 13.1%) means more weeks end profitable. BOIL's fatter tails help on the huge moves, but the extra leverage doesn't improve risk-adjusted returns.

---

## Factor 3: Rolling Vol — The Regime

![Rolling Vol](rolling_vol.png)

Key observations:
- **UNG and BOIL** peaked at 145%/281% in Feb, now at 50%/100%. Post-spike contraction = cheap strangles.
- **NEXT** has elevated vol (~72%) and already rallied +27% since Mar 13 — the market found it.
- **LNG (Cheniere)** vol expanded +82% — expensive entry.
- **EWJ** vol is mid-range, trending up.

---

## Factor 4: Win Rate vs Cheap Vol

![IV vs Win Rate](iv_vs_winrate.png)

UNG and BOIL sit alone in the top-left sweet spot: cheap vol AND high win rates. Everything else clusters in the bottom-right: expensive vol, low win rates, negative ROI.

---

## Your Answer: IV30 of 55% on UNG

You asked about UNG's IV30 being at 55%. Here's the breakdown:

| Metric | Value | What It Means |
|--------|-------|---------------|
| IV (from options chain) | **60%** | What the market is charging for options |
| HV30 (30-day realized) | **44%** | What UNG actually did over the last 30 days |
| HV20 (20-day realized) | **50%** | More recent window |
| Annual σ (1-year) | **64%** | Full-year realized vol |
| IV Rank (1-year range) | **15%** | Where current vol sits vs its own history |

**Yes, IV at 55-60% sounds high in absolute terms.** But for UNG it's near the floor. The 1-year range is 33%-145%. You're at the 15th percentile. The market is charging you "calm UNG" premiums during a period with an active Hormuz crisis catalyst.

The IV-HV spread is +15% (IV 60% vs HV30 44%), meaning the market is pricing in *some* premium over realized vol. But that spread was +50% during the Feb peak. The premium has compressed massively.

---

## What About the Other Tickers?

### NEXT (NextDecade) — Interesting But Late
- Already up **+27.2%** since Mar 13 — the market found this play
- IV rank 52% — mid-range, not cheap
- Only monthly options (April 17) — 21-day expiry
- Win rate only 21%, ROI -40%
- **Verdict:** The thesis is right (US LNG replacement supplier) but the timing is wrong. Come back if it pulls back and vol drops.

### LNG (Cheniere) — Too Expensive
- Up **+12.7%** since Mar 13
- IV rank 67% — expensive
- $1,460/contract — over budget for 1 straddle
- Win rate 18%, ROI -36%
- **Verdict:** The obvious play. Market already in it. Vol priced.

### EWJ / EWY (Japan/Korea) — The Under-Discussed Victims
- The thesis is strong: 90% energy imported, 40% through Hormuz
- But EWJ IV rank is 57%, EWY is 97% (!!). Vol is priced.
- Win rates: 14% / 11%. Negative ROI.
- **Verdict:** Great thesis, terrible strangles. The options market sees it.

### COPX (Copper) — Third Order, Expensive
- IV rank 69%, win rate 14%, ROI -48%
- **Verdict:** Too many steps removed and vol already priced.

---

## The Bottom Line

**UNG is still the only trade.** After analyzing 7 tickers across the entire LNG/Hormuz supply chain, nothing else comes close:

| | UNG | Best Alternative (BOIL) | Average of Others |
|---|---|---|---|
| IV Rank | 15% | 21% | 68% |
| Win Rate | 41% | 42% | 16% |
| Avg ROI | +4% | +4% | -44% |
| Composite | 37.4 | 37.2 | 21.4 |

The supply chain plays (LNG, NEXT, EWJ, EWY) have the right thesis but the market already repriced their vol. The only places with cheap vol are the nat gas instruments — and UNG is the most liquid, cheapest-to-trade version.

**Your Kelly strategy: $1,500/week on UNG weekly straddles. Repeat until Hormuz resolves or vol gets expensive (IV rank > 50%).**

---

*Generated by the Nassim Taleb Antifragile Volatility Agent. Not financial advice.*
"""

with open(f"{OUT}/lng_hormuz_analysis.md", "w") as f:
    f.write(md)

print(f"Report: {OUT}/lng_hormuz_analysis.md")
print("Done!")
