# Outside-View Assessment: `virattt/ai-hedge-fund` (v2 `hedge_fund` engine)

*Read-only. No files changed. Based on `VISION.md`, `ROADMAP.md`, a structural skim of `hedge_fund/` sufficient to ground comparisons, and ~20 web searches/fetches. The internal code audit is another agent's job; where I cite code it is only to check a design claim against reality.*

---

## Verdict

Architecturally, this is **number six replicating number five — and the number five is QuantConnect LEAN, almost line for line.** LEAN's Algorithm Framework has shipped since ~2018 with exactly this pipeline: Universe Selection → **Alpha Model** emitting **`Insight`(direction, magnitude, *confidence*)** → **Portfolio Construction** emitting **`PortfolioTarget`** → **Risk Management** (clamps targets) → **Execution**. LEAN even ships a `ConfidenceWeightedPortfolioConstructionModel` and an `InsightWeightingPortfolioConstructionModel` — i.e. the project's "conviction-weighted blending" is a stock LEAN component with a different variable name. The second headline principle, "one engine, three modes — only the clock and the broker change," is verbatim the converged answer of both LEAN and NautilusTrader; Nautilus was *founded* on it (shared `NautilusKernel` between `BacktestEngine` and `LiveNode`, substitution at the data/execution-client boundary). So neither of the two load-bearing design ideas in `VISION.md` is new.

There **is** one genuinely non-derivative element — the **natural-language thesis as a first-class, persisted, replayable artifact attached to every signal and every fill** — but it is currently an explainability/UX asset, not an alpha or validity asset, and the project has not yet built the one thing that would make it rigorous (forward scoring of theses against realized outcomes, which LEAN *does* have for numeric insights via Direction/Magnitude/Estimated-Alpha scoring).

The deeper problem is not derivativeness, it's **a structural contradiction the design has not noticed**: the stated moat is point-in-time honesty, but the dominant leakage channel for LLM-persona alpha models is not the data pipeline at all — it is *the model weights*. Reproductions show FinMem's total return collapsing by roughly 70% once the backtest window crosses the model's pretraining cutoff. No amount of as-of filing-date plumbing fixes that. And the roadmap's planned rescue — CPCV/PBO as a "validation gate" — provably does not catch leakage: a deliberately leaky oracle posting **Sharpe 35 passes Deflated Sharpe and PBO completely** (Gençay 2026).

Fair counterweight: measured against the *published LLM-trading literature*, this project's stated intentions are already above median. A 2026 survey of 77 agentic-trading studies found that of the 19 that actually emit tradable actions and close the loop, **2/19 used time-consistent splits, 1/19 modeled transaction costs, 1/19 handled survivorship, and 0/19 reached the top reproducibility tier**. `VISION.md` names all three. That is genuinely creditable — and also a very low bar.

---

## Comparison table

| Dimension | **ai-hedge-fund (v2)** | **QuantConnect LEAN** | **NautilusTrader** | **Zipline-reloaded** | **backtrader** | **vectorbt** | **Lumibot** |
|---|---|---|---|---|---|---|---|
| Backtest paradigm | Event-ish daily loop (`run_cycle` over history) | Event-driven, tick→bar, multi-asset | Event-driven, **nanosecond**, dual `ts_event`/`ts_init` timestamps, deterministic replay | Event-driven daily bars | Event-driven bars | **Vectorized** (NumPy arrays) | Event-driven, deployment-oriented |
| Pipeline decomposition | data → AlphaModel(`Signal`) → portfolio → risk → execution → ledger | **Universe → Alpha(`Insight`) → PortfolioConstruction(`PortfolioTarget`) → Risk → Execution** | Strategy → OrderFactory → RiskEngine → ExecEngine → Portfolio/Cache | Pipeline (factor) + `handle_data` | `Strategy.next()` | Array ops | Strategy + broker abstraction |
| Conviction→weight blending | conviction-weighted (ships) | `ConfidenceWeighted…` / `InsightWeighting…` PCMs (ships) | user-supplied | user-supplied | user-supplied | user-supplied | user-supplied |
| Backtest↔live parity | Claimed by design; **paper and live brokers both ⬜ unbuilt** — parity is untested at the only boundary that matters | Shipped; ~a dozen broker adapters; order events async in live, sync in backtest (documented divergence) | Founding rationale; shared kernel; explicitly warns parity still depends on adapter + data fidelity | Weak (Zipline is research-first) | Broker integrations exist | None (research only) | **This is its whole pitch** |
| Fill / cost model | **Fills 100% at the order's reference price. Commission only. `sim.py`: "slippage stays a future addition."** No spread, no partial fills, no queue, no market impact, no capacity | Configurable fill/slippage/fee models, tick-level | `SimulatedExchange` with fill models, latency, fee tiers, order-book matching | Basic slippage/commission models | Slippage + commission schemes | Weak by construction (vectorized) | Basic |
| Universe / survivorship | **Tickers are a run-time input** (`normalize_universe`), not PIT index membership → survivorship + self-selection by construction | Universe Selection Model with PIT constituent data (incl. delisted) | Instrument catalogue, venue-driven | Bundles incl. survivorship-aware options | User's CSVs | User's arrays | User's list |
| PIT fundamentals | 🚧 in progress; **single vendor**, `BASE_URL = "https://api.financialdatasets.ai"` hardcoded | PIT datasets + vendor marketplace (Morningstar, Brain, etc.) | Data-agnostic, adapter-based | PIT pipeline is a documented design goal | User's problem | User's problem | User's problem |
| Overfitting controls | `hedge_fund/validation/__init__.py` is a **5-line stub**; CPCV/PBO ⬜ | Built-in walk-forward optimization + parameter optimizer + **insight scoring/alpha attribution** | Not opinionated (you bring your own) | None | None | Parameter sweeps (makes overfitting *easier*, not harder) | None |
| Signal attribution | ⬜ none — theses are stored but never scored against outcomes | Direction Score, Magnitude Score, Estimated Alpha Value per Insight | none | none | none | none | none |
| Reproducibility of a run | **Non-deterministic by construction** (LLM sampling); no seeding/variance discipline evident | Deterministic | Deterministic replay is an explicit architectural constraint | Deterministic | Deterministic | Deterministic | Deterministic |
| Multi-strategy / capital allocator | Pods + static slices ✅; pluggable CIO 🚧; risk-parity/dynamic/LLM-CIO ⬜ | Not first-class — you build it | Multiple strategies per engine; allocator is yours | No | No | No | No |
| NL rationale persisted per decision | ✅ **unique among these** | No | No | No | No | No | No |

**Where it agrees with the field:** pluggable staged pipeline, one code path for backtest/live, hard risk gates downstream of signal generation, deterministic sizing. All correct, all settled 5–8 years ago.

**Where it diverges and looks naive:** the fill model. `SimBroker` filling every order completely at the order's own reference price with zero spread is below backtrader's 2015-era default, let alone LEAN's or Nautilus's. For a daily-rebalanced multi-name book this is the single largest source of phantom return after universe selection. Realistic retail equity friction is **15–25bp round-trip**; the *Alpha Illusion* reproduction found TradingAgents' portfolio Sharpe fell from **0.43 gross to 0.22 net** and QuantAgent's from **−0.96 to −1.15** once commissions, token costs, spreads and impact were applied — both then underperforming buy-and-hold. Across five leading LLM trading systems, **35 of 40 friction-component cells were unmodeled**.

---

## Standard-practice gaps, ranked by damage to trustworthiness

**1. Survivorship / self-selected universe (most damaging, cheapest to fix).**
The mandate deliberately does *not* own a universe — tickers arrive at run time. In practice a human types a list of companies that exist and are interesting *today*. That is textbook survivorship plus selection bias, and it applies to every backtest the system produces, including honest-PIT ones. Documented magnitudes: 7.4% vs 9.0% annualized over 1926–2001 in survivorship-free vs biased datasets; a documented single-decision case worth ~8pp/yr of "ghost alpha"; Kothari–Shanken–Sloan found Compustat-excluded shares returned **9–10pp lower** than included ones. This gap alone can manufacture the entire apparent edge. FINSABER (KDD 2026) rebuilt exactly this — 100+ S&P 500 symbols over 2004–2024 **including delisted names** — and found FinMem and FinAgent produce **no statistically significant alpha** and fail to beat buy-and-hold risk-adjusted.

**2. LLM training-data contamination — and the fact that the project's stated moat doesn't address it.**
`VISION.md`'s first non-negotiable is "no lookahead, ever," implemented as as-of data queries. But for LLM personas the leak is in the weights. GPT-4o recalls S&P 500 closing prices and WSJ headline dates within its training window with errors below 1%, and error jumps sharply post-cutoff. The *Alpha Illusion* reproduction quantifies the trading consequence: **FinMem's total return fell ~71.85%** (an adjacent summary reports 51.48% for that figure and attributes 71.85% elsewhere — treat the exact split as uncertain, the direction and order of magnitude are not) once the window crossed the cutoff. **Any backtest this project runs before the model's cutoff is contaminated regardless of how perfect its filing-date logic is.** I saw no evidence of a declared per-model knowledge cutoff, no pre/post-cutoff split in reporting, and no contamination labeling. This is the most important thing missing from the *design*, not just the code.

**3. Point-in-time fundamentals still 🚧, on a single undocumented-vintage vendor.**
Restatement magnitude is not a rounding error: using Compustat Snapshot, the same firm-fiscal-period observation is revised **at least 5 times on average**, with statement items moving by **9% of total assets**; across 35 accounting anomalies, roughly **half yield materially different inferences across data vintages**. financialdatasets.ai advertises SEC-verified values across 27,000+ tickers and 30+ years, US-only — but I could find **no public documentation of as-filed vs. restated storage, data vintages, amendment (10-K/A) handling, or delisted-ticker retention**. That is not proof of absence, but for a system whose headline claim is PIT honesty, the truth of that claim is currently unverifiable from outside and is delegated wholesale to one vendor.

**4. No multiple-testing correction, and the planned one is insufficient.**
CPCV and PBO are ⬜; `validation/` is a stub. Worth building — CPCV demonstrably lowers PBO and raises DSR versus k-fold and walk-forward. But two caveats the roadmap should absorb: (a) **DSR/PBO do not detect leakage** — Gençay's leaky oracle at **Sharpe 35 passes both cleanly**, so the validation gate cannot be the safety net for gaps 1–3; and (b) the Level-2 "fund runs its own lab" vision makes this *worse*, because automated strategy search inflates the effective number of trials that DSR must deflate by, and nothing in the design tracks search intensity.

**5. Execution realism.** See table. Fill-at-reference-price with no spread is the design's weakest concrete component and is trivially improvable (spread + volume-participation cap + a square-root impact term would cost a day and change every backtest number).

**6. No signal attribution.** The theses are the differentiator and they are never graded. LEAN scores every Insight for directional accuracy and estimated alpha value; this project stores richer artifacts and does nothing with them. Biggest missed opportunity in the codebase.

**7. Non-determinism + cost make the validation gate economically incoherent.** CPCV needs many paths over many backtests; each backtest here is *N tickers × M personas × T days* LLM calls, non-deterministic across runs. A statistically meaningful CPCV/PBO run on an LLM-per-tick architecture is likely to be unaffordable. This is an architectural tension, not an implementation detail, and it is the strongest argument for the redesign in the last section.

**8. Walk-forward analysis absent as a first-class concept.** LEAN ships scheduled WFO. Here the backtest is a single pass over history.

---

## Evidence on LLM stock-picking efficacy

**What is actually known (and it is not encouraging):**

- **FINSABER (KDD 2026, Datasets & Benchmarks, Oral)** — the most rigorous negative result available. 2004–2024, 100+ S&P 500 symbols including delisted. Prior LLM advantages "deteriorate significantly" under broader cross-section and longer horizon; FinMem and FinAgent show **no statistically significant alpha** and do not beat buy-and-hold risk-adjusted. Failure mode is regime-shaped: **too conservative in bull markets** (underperform passive), **too aggressive in bear markets** (heavy losses). Authors' prescription — trend detection and regime-aware risk controls, *not* more framework complexity — is a direct rebuke of the "add more personas" contribution model in this roadmap.
- **The Alpha Illusion (arXiv 2605.16895, May 2026)** — one-year reproduction of TradingAgents and QuantAgent (Jan 2025–Jan 2026, 5 tickers) with real friction. Sharpe 0.43→0.22 net; 35/40 friction cells unmodeled across six systems; at typical headline Sharpes (1.5–3.3) over 90–250-day windows, **95% CIs exceed the reported system differentials** — i.e. most published rankings between LLM trading systems are statistically meaningless. Not peer-reviewed; authors concede their P1–P6 protocol is necessary-not-sufficient and that prototypes needn't meet it if they avoid deployment language. That caveat applies here: this project *does* say "educational only."
- **Agentic-trading survey (arXiv 2605.19337, 2026)** — 77 studies, 19 closing the loop. Time-consistent splits **2/19**; transaction-cost models **1/19**; survivorship handling **1/19**; top reproducibility tier **0/19**. Conclusion: "A trading agent can appear architecturally sophisticated while still being empirically weak."
- **Memorization (arXiv 2504.14765)** — frontier LLMs recall index closes within their training window to <1% error. Foundational to gap #2.
- **Leakage-safe evaluation (arXiv 2608.27734, Aug 2026)** — the Sharpe-35 leaky oracle passing DSR and PBO. One paper, one author, not peer-reviewed; one public critique disputes an adjacent claim about certifying passive benchmarks. Treat the headline demonstration as a strong warning, not settled fact.
- **GuruAgents (arXiv 2510.01664)** — the closest direct prior art to *this project's* specific idea: prompt-encoded Graham/Buffett/Greenblatt/Piotroski personas with a deterministic reasoning pipeline, backtested on NASDAQ-100 constituents Q4 2023–Q2 2025. Buffett agent: **42.2% CAGR**, beating benchmarks. **Do not weight this much**: ~7 quarters, index constituents (survivorship), and the entire window sits inside the training data of the models then in use. It is the best evidence *for* persona agents and it is exactly the shape of result FINSABER and Alpha Illusion showed evaporates.
- **Alpha mining (AlphaAgent KDD 2025; QuantaAlpha; AlphaMemo; R&D-Agent-Quant; Alpha-GPT)** — the more promising branch. These use the LLM to *generate factor/strategy definitions* which are then evaluated deterministically and cheaply, with explicit regularization against alpha decay. This matters for §5.

**Net:** there is no credible published evidence that LLM-driven stock picking produces real out-of-sample alpha. Every positive result I found either sits inside a pretraining window, uses a survivorship-contaminated universe, omits costs, or covers too short a window for the Sharpe estimate to separate from zero — usually several of these. The negative results are the ones with the careful methodology. Evidence is thin in one direction only: nobody has run a *properly* leakage-safe, post-cutoff, cost-inclusive, survivorship-free multi-year test of persona agents and found alpha, but that's partly because almost nobody has run one at all.

---

## Where this project is genuinely ahead or differentiated

Being fair:

1. **The persisted natural-language thesis per signal, per cycle, replayable.** No comparable open-source engine does this — LEAN persists numeric Insights, Nautilus persists events, neither persists a rationale. It aligns with what regulated algo trading actually requires (MiFID II RTS 6-style decision logs: inputs, model output with confidence, approver, execution, post-trade outcome). **This is the real differentiator and it is currently half-built**, because it captures 1–3 of those 5 elements and never grades the thesis against outcome.
2. **Stated methodological ambition above the field's revealed standard.** PIT honesty, no-LLM-touches-the-trade (deterministic sizing, hard risk gates — correct and unusual for this genre), CPCV/PBO as a promotion gate, paper-before-live, human-approved promotion. Against 2/19, 1/19, 1/19, 0/19 in the survey, naming these is not nothing.
3. **Three-level plugin taxonomy (allocator → strategy → analyst) with a multi-pod book netted into one risk stage.** LEAN has no first-class capital allocator above the framework; you build it. This is a mild genuine gap in the incumbents. But the value lives entirely in the dynamic allocator, which is ⬜, and the structure itself is just the multi-manager pod model imported from Millennium/Balyasny.
4. **Honest self-labeling.** "Educational use only," and `ROADMAP.md` marks the hard parts 🚧/⬜ rather than claiming them. That is more integrity than most of the published literature.

What is **not** differentiated, despite being presented as such: the pluggable alpha/portfolio/risk/execution decomposition (LEAN, ~2018), one-code-path parity (Nautilus's founding thesis), conviction-weighted construction (LEAN stock component), and investor personas (GuruAgents, TradingAgents, FinMem, FinAgent, and the original v1 of this same repo).

---

## What the non-derivative version would look like

Three moves, in order of how much they'd change the project's standing:

**A. Invert the LLM's role: generator, not scorer.** Today the LLM is in the per-tick hot path, which makes every backtest expensive, non-reproducible, contaminated, and impossible to run enough times for CPCV. Instead have personas emit **deterministic, auditable strategy/factor artifacts** — "Buffett-style screen v7: ROIC>15% for 5y, D/E<0.5, FCF yield>4%, weight ∝ ..." — which then run at zero marginal cost, identically every time, over any window including post-cutoff. This is the AlphaAgent/QuantaAlpha/Alpha-GPT line and it is the *only* design that reconciles LLM reasoning with the roadmap's own validation gate. The thesis differentiator survives intact: the thesis becomes the artifact's provenance record.

**B. Make contamination a first-class engine concept.** Every alpha model declares a `knowledge_cutoff`. The backtester refuses to report a headline number spanning it without splitting and labeling pre-cutoff results as contaminated; promotion requires post-cutoff evidence. **Nobody ships this** — it's precisely what Alpha Illusion's P1 and the Look-Ahead-Bench line are asking for, and it would be a real open-source first that no incumbent quant framework needs (because none of them have LLMs in the alpha path). This is the most defensible idea available to this project.

**C. Close the loop on theses.** Score every persisted thesis against the realized forward outcome — LEAN's Insight scoring, but for natural-language views — and let the allocator consume *that* track record. This turns the ledger from a UX feature into the system's actual learning signal and gives the "explainability" claim teeth.

Plus the cheap hygiene that should happen regardless: own a PIT universe with delisted names in the mandate (fixes gap 1); add spread + participation cap + impact to `SimBroker`; add a second data vendor behind `DataClient` and reconcile, storing vintages.

If the project does A+B+C it stops being a LEAN clone with LLMs bolted on and becomes *the reference implementation for evaluating LLM alpha honestly* — a position nobody currently occupies and which the 2026 critique literature is explicitly begging someone to take. If it doesn't, the shortest accurate description is: a well-organized re-implementation of QuantConnect's 2018 Algorithm Framework, with a weaker fill model, a survivorship-biased universe, one data vendor, and a contamination channel the design does not acknowledge — differentiated mainly by having 63k GitHub stars.

---

## Sources

- [QuantConnect LEAN — Algorithm Framework overview](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview)
- [LEAN — Alpha model key concepts (Insight: direction, magnitude, confidence)](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/alpha/key-concepts)
- [LEAN — `ConfidenceWeightedPortfolioConstructionModel`](https://github.com/QuantConnect/Lean/blob/master/Algorithm.Framework/Portfolio/ConfidenceWeightedPortfolioConstructionModel.py)
- [LEAN — Risk Management model key concepts](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/risk-management/key-concepts)
- [LEAN — Algorithm Scoring (insight direction/magnitude/estimated alpha)](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/alpha-creation/algorithm-scoring)
- [LEAN — Walk Forward Optimization](https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization)
- [LEAN — Algorithm Engine (event-driven, backtest/live parity)](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine)
- [NautilusTrader — Why NautilusTrader Exists (parity rationale)](https://nautilustrader.io/blog/why-nautilustrader-exists/)
- [NautilusTrader — Backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/)
- [NautilusTrader — Live trading concepts](https://nautilustrader.io/docs/latest/concepts/live/)
- [Backtrader vs NautilusTrader vs VectorBT vs Zipline-reloaded](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded)
- [The Python Backtesting Landscape (2026)](https://python.financial/)
- [Can LLM-based Financial Investing Strategies Outperform the Market in Long Run? (FINSABER, KDD 2026)](https://arxiv.org/abs/2505.07078)
- [FINSABER code/data](https://github.com/waylonli/FINSABER)
- [The Alpha Illusion: Reported Alpha from LLM Trading Agents Should Not Be Treated as Deployment Evidence](https://arxiv.org/html/2605.16895v1)
- [Agentic Trading: When LLM Agents Meet Financial Markets (survey, 77 studies)](https://arxiv.org/html/2605.19337v1)
- [What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery](https://arxiv.org/abs/2608.27734)
- [The Memorization Problem: Can We Trust LLMs' Economic Forecasts?](https://arxiv.org/html/2504.14765)
- [Assessing Look-Ahead Bias in Stock Return Predictions Generated By GPT Sentiment Analysis](https://arxiv.org/abs/2309.17322)
- [GuruAgents: Emulating Wise Investors with Prompt-Guided LLM Agents](https://arxiv.org/abs/2510.01664)
- [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/pdf/2412.20138)
- [AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration (KDD 2025)](https://dl.acm.org/doi/10.1145/3711896.3736838)
- [A survey on large language model-based alpha mining (FITEE)](https://link.springer.com/article/10.1631/FITEE.2500386)
- [Bailey & López de Prado — The Deflated Sharpe Ratio (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [Purged cross-validation (overview)](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [Backtest overfitting in the ML era: comparison of out-of-sample testing methods (CPCV vs WF vs k-fold)](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110)
- [Re-Adjusted Financial Statement Data: Challenges and Implications (Compustat Snapshot restatements)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5107985)
- [Point-in-Time Fundamentals and Look-Ahead Bias — The Retail Quant](https://theretailquant.cc/research-methods/point-in-time-fundamentals-are-a-data-model)
- [Vendor Backfill and History Rewrites, Explained](https://quantmemo.com/concepts/vendor-backfill-and-history-rewrites)
- [Survivorship Bias and Other Data Landmines](https://hmaquant.substack.com/p/survivorship-bias-and-other-data)
- [Dealing with Delistings: A Critical Aspect for Stock-Selection Research (Alpha Architect)](https://alphaarchitect.com/dealing-with-delistings-a-critical-aspect-for-stock-selection-research/)
- [The cross-section of stock returns and survivorship bias: evidence from delisted stocks](https://www.sciencedirect.com/science/article/abs/pii/S1062976996900216)
- [Market Structure Lens #1 — The Cost Layer: Why Most Backtests Are Quietly Lying to You](https://algorithmictoken.substack.com/p/market-structure-lens-1-the-cost)
- [Modelling Transaction Costs and Market Impact (BSIC)](https://bsic.it/backtesting-series-episode-5-transaction-cost-modelling/)
- [Financial Datasets — product/coverage](https://www.financialdatasets.ai/)
- [Financial Datasets — pricing](https://www.financialdatasets.ai/pricing)
- [Financial Data Providers: How to Evaluate Coverage, Freshness & Licensing](https://forage.ai/blog/financial-data-providers/)
- [MiFID II / MiFIR algorithmic trading obligations (Norton Rose Fulbright)](https://www.nortonrosefulbright.com/en/knowledge/publications/6d7b8497/mifid-ii-mifir-series)
- [ESMA MiFID II Review Report on Algorithmic Trading](https://www.esma.europa.eu/sites/default/files/library/esma70-156-4572_mifid_ii_final_report_on_algorithmic_trading.pdf)
- [virattt/ai-hedge-fund star history (63.4k stars, Sept 2026)](https://www.star-history.com/virattt/ai-hedge-fund/)

*Evidence-strength flags: the Alpha Illusion contamination figure appears as both 71.85% and 51.48% across sources — direction is robust, exact magnitude is not. The Sharpe-35 leaky-oracle result is a single non-peer-reviewed paper with a public critique of an adjacent claim. GuruAgents' 42.2% CAGR is a 7-quarter, in-training-window, index-constituent result and should be treated as near-zero evidence. financialdatasets.ai's PIT/vintage/delisting behavior is **undocumented publicly** — I could not confirm or refute it, which is itself the point.*
