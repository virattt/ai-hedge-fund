# ML and agentic methods for the perp system -- 2026-09-19

*Agent report, lightly condensed. "Fetched" means the agent retrieved the primary source on the date above; "snippet" means search-summary level only. Not re-verified by the orchestrating session.*

## VERDICT

Given short-and-growing history, small capital, non-colocated Python, hours-to-days holds, and a harness that has so far marked every tested signal NOT VALIDATED: **adopt almost nothing exotic yet.** Two things pay now: (1) **linear/ridge, then regularised GBDT, on cross-sectional panels of the already-evidenced signal families** (funding/basis carry, cross-sectional funding, momentum, whale-flow cohorts) as the estimator layer; (2) **the RD-Agent(Q) pattern** -- LLM proposes and codes factors, deterministic harness scores them, feedback loop iterates -- which is real, MIT-licensed, actively maintained, and matches the rule "LLM writes code, never reads prices". Sequence models, time-series foundation models, GNNs on wallet graphs, Hawkes processes and RL-for-alpha all have thin or contradictory evidence, the wrong horizon, or a documented failure mode that fits this project badly. RL's only defensible near-term role is a narrow sizing/bandit layer on top of an already-validated signal.

## 1. Model families at hours-to-days crypto/perp horizons

| Family | For | Against | Failure mode | Minimum history |
|---|---|---|---|---|
| **Linear / ridge factor models** | Used as baseline in crypto ML papers and sometimes wins; matches this project's prior that only simple structural signals replicated | Misses regime interactions (e.g. carry conditional on OI crowding) | Underfits, rarely worse than GBDT on short noisy data | Lowest bar of any family: weeks of cross-section if the target is an already-evidenced signal. **The default estimator today.** |
| **GBDT on cross-sectional panels** | XGBoost reported best among LASSO/Ridge/RF/GBM/FFN in a large-panel study (ScienceDirect S0927538X25003701 -- paywalled, abstract only) | A contradicting strand: OLS beats trees and nets OOS across 500+ coins (snippet only). **Unresolved contradiction; both papers paywalled (403).** | Crypto universes are a few hundred names; deep trees become lookup tables | Noise-mining before ~6-12 months of daily panel; less with heavy regularisation and shrinkage toward the linear factors |
| **Sequence models / TS foundation models** | LSTM+GBRT on 1,681 coins (snippet) | TimesFM-2.5, Moirai-2.0, Chronos-2 vs from-scratch baselines on 5 US equities: gains over random walk "small and sparse", significant in 2 of 10 cases; a plain iTransformer beat every pretrained model on META. Authors: "not universal engines for statistically reliable alpha generation." ([arXiv:2606.27100](https://arxiv.org/abs/2606.27100), fetched). **No crypto/perp TSFM evaluation found.** | Data-hungry; equities-only evidence | Zero-shot, so cheap to try as a *baseline* scored against random walk; never a primary signal |
| **Graph models on wallet/flow networks** | Active literature on link prediction and illicit-transaction detection | **No paper found showing a GNN on wallet flow producing validated forward-return alpha.** | One venue's fill graph is sparse and single-hop | Essentially no evidence for this use. Cohort/aggregate flow features are the cheaper, already-evidenced substitute |
| **Order-flow / Hawkes** | Several LOB papers ([arXiv:2312.16190](https://arxiv.org/abs/2312.16190), [arXiv:2408.03594](https://arxiv.org/html/2408.03594v1)) | All seconds-to-minutes microstructure; none at hours-to-days | Signal decays before a non-colocated loop can act | Horizon/infrastructure mismatch, not a data problem. Low priority unless fill quality becomes the bottleneck |

## 2. Reinforcement learning

**Confirmed (repos fetched / `gh api`):**
- `AI4Finance-Foundation/FinRL` -- MIT, 16,335 stars, pushed 2026-07-13. Its own README now points to **FinRL-X / FinRL-Trading** as the production-oriented successor: FinRL itself is positioned by its maintainers as legacy/research.
- `FinRL-Meta` -- MIT, 1,940 stars, pushed 2026-07-13.
- `ElegantRL` -- GitHub's licence badge reports NOASSERTION, but the fetched `LICENSE` file is **Apache-2.0**. 4,365 stars, pushed 2026-02-20.
- **FinRL-DeepSeek** ([arXiv:2502.07393](https://arxiv.org/abs/2502.07393)) -- risk-sensitive PPO with LLM news-sentiment signals, Nasdaq-100. Repo `benstaf/FinRL_DeepSeek` MIT but stale (last push 2025-04-08, 331 stars). Equities/news-dependent and feeds LLM output into decisions, which conflicts with this project's rule.

**Record (snippet level):** RL-for-alpha work is mostly RL as a *search heuristic over factor space*, not a trading policy. A repeatedly named failure mode is the **simulation-to-reality gap**: policies overfit the simulator, compounded by low signal-to-noise and non-stationarity. RL for **execution** (trade scheduling, order placement within a horizon) has the longer and more credible record -- a narrower, better-defined problem.

**Where it earns a place here:** not alpha. If at all, a constrained bandit/RL layer for sizing or entry timing on top of an already-validated signal, trained on this system's own fill-quality data, and only once that data exists.

## 3. Agentic / LLM research automation

**Confirmed (fetched):**
- **RD-Agent(Q)** -- Microsoft Research, NeurIPS 2025. Research stage (LLM forms hypotheses -> tasks) + development stage (Co-STEER code-gen, backtested on real markets) + feedback with a multi-armed-bandit scheduler for direction selection. Reported up to 2x annualised return vs classical factor libraries using 70% fewer factors. Repo `microsoft/RD-Agent`, **MIT**, 14,685 stars, pushed 2026-09-15. Built on `microsoft/qlib` (MIT, 48,678 stars, pushed 2026-09-17).
- **AlphaAgent** -- KDD 2025, [arXiv:2502.16789](https://arxiv.org/abs/2502.16789). Guardrails aimed at exactly the failure modes that matter: (1) **originality enforcement** via AST similarity against the existing factor library; (2) **hypothesis-factor alignment** -- an LLM checks the generated code matches its stated economic rationale; (3) **complexity control** via AST structural limits. CSI 500 + S&P 500, 2021-2024, IR 1.5 / 1.05 after costs. Equities only. Official repo and licence not located this pass.

**Failure modes across this literature:** alpha decay through crowding (unregularised LLM miners converge on the same obvious factor shapes); overfitting through search (the reason both frameworks carry bandit scheduling / AST constraints). **Lookahead via LLM pretraining was named in the brief but NOT independently sourced in this pass -- open item.**

**Takeaway:** the in-house harness already does AlphaAgent's job by hand. Adopting the RD-Agent(Q) loop on a small, tightly scoped search space is the highest-value agentic adoption.

## 4. Methods for this system's unusual data

- **Wallet-level order flow:** build cohort features (net positioning by labelled cohort, crowding indices, time-since-cohort-flip). Not GNN training data until fill volume makes a graph non-trivial; that threshold is unknown and must be estimated in-house.
- **Restated labels:** no crypto-specific paper or vendor doc found. The safe practice is ordinary point-in-time discipline: snapshot the label as of the decision date, never join current labels to historical flow, treat any backtest using today's labels on past flow as lookahead-contaminated by construction. (Synthesis, not a citation.)
- **HIP-3 equity perps vs the cash market:** **confirmed from Hyperliquid's docs** ([hyperps](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps), fetched): the oracle is an 8-hour EMA of the last day's minutely mark prices, clamped to 4x the trailing one-month average mark; mark is capped at 3x the 8-hour oracle EMA (or 1.5x the median external perp price where one exists). Off-hours the oracle has no external anchor and chases the perp's own mark, so lead-lag against cash is meaningful only while the cash market is feeding the oracle. **No empirical lead-lag study found** -- this is a "measure it on your own snapshots" item.

## 5. Validation

- **Deflated Sharpe Ratio** -- Bailey & Lopez de Prado (2014), SSRN 2460551. Deflates by the number of *configurations searched*, not CV folds.
- **CPCV** -- reference implementation `eslazarev/purged-cross-validation` (MIT, pushed 2026-09-04, only 35 stars): read it against the primary sources rather than trusting it.

Minimum bars for short history:
- **Log every configuration tried, from day one.** The deflation correction cannot be computed honestly later from an untracked search; an unlogged 90 days is unrecoverable.
- **Purging + embargo is mandatory** for any signal with overlapping-horizon labels (hours-to-days holds overlap across adjacent samples); plain k-fold leaks.
- **Walk-forward with embargo until there is enough history for non-degenerate CPCV paths** (several multiples of the holding period).
- At 30-90 days no CV machinery turns a lucky backtest into a validated one. The honest bar: does the signal replicate the *published* structural families on this system's own data.

## 6. Staged adoption keyed to data age

**~30 days.** Do: linear/ridge on the evidenced families; start the RD-Agent loop on a small, scoped search space with full trial logging; snapshot HIP-3 oracle/mark/basis by session (cash-hours vs off-hours) for later. Do not: GBDT, sequence models, TSFMs, GNNs, RL, Hawkes -- each attempt burns trial count against a deflation correction that is brutal at this sample size.

**~90 days.** Do: regularised GBDT as a *comparison* against the linear baseline, purged/embargoed; a TSFM as a zero-shot baseline scored against random walk (expect a loss or tie); first own study of HIP-3 off-hours vs cash-hours lead-lag. Do not: RL for alpha; GNN on the wallet graph.

**~1 year.** Do: CPCV; deflated Sharpe over the full logged trial history; reassess GBDT vs linear on a multi-regime sample; reassess whether the fill feed is dense enough for a cohort graph. Consider: a narrow bandit/RL sizing layer on a validated signal using own fill data. Still avoid: RL-for-alpha and LLM-reads-news-into-decisions patterns.

## 7. Open-source implementations (licence verified from source)

| Repo | Use | Licence | Maintained | Verdict |
|---|---|---|---|---|
| microsoft/RD-Agent | LLM factor/model R&D loop | MIT | pushed 2026-09-15 | Read and reference -- closest prior art |
| microsoft/qlib | Backtest/factor infra | MIT | pushed 2026-09-17 | Read for harness design |
| AI4Finance-Foundation/FinRL | RL-for-trading framework | MIT | yes; self-described legacy vs FinRL-X | Read for environment design only |
| AI4Finance-Foundation/FinRL-Meta | Environments/benchmarks | MIT | pushed 2026-07-13 | Same caveat |
| AI4Finance-Foundation/ElegantRL | Lightweight RL library | Apache-2.0 (badge wrong) | pushed 2026-02-20 | Usable for a later sizing layer |
| benstaf/FinRL_DeepSeek | LLM-sentiment RL | MIT | stale since 2025-04 | Avoid |
| eslazarev/purged-cross-validation | Purging/embargo/CPCV/DSR | MIT | pushed 2026-09-04, 35 stars | Reference only; verify its maths |
| AlphaAgent | LLM alpha mining guardrails | repo/licence not verified | -- | Read the paper for the guardrail design |

## Open items

1. GBDT-vs-linear contradiction on crypto cross-sections -- both papers paywalled; find working-paper versions.
2. TSFMs on crypto/perp data -- none found; may not exist yet.
3. LLM-pretraining lookahead in factor mining -- not sourced this pass; needs a dedicated search.
4. Empirical HIP-3-perp vs cash-equity lead-lag -- measure from own snapshots.
5. Fill-volume threshold at which a wallet graph becomes non-trivial -- estimate in-house.
6. AlphaAgent's official repo and licence.
7. Restated-label methodology -- no crypto-specific source; recommendation is general PIT practice.
