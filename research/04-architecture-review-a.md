# Adversarial premise review — `/home/user/ai-hedge-fund`

## Verdict

**Partially sound, with one load-bearing claim that is false as stated and one that is unprovable today.** The engineering spine is genuinely good: `run_cycle` really is one code path, `SimBroker` really is deterministic, the data layer really does filter on `filing_date` rather than `report_period`, and the failure contract (fail-loud on data, abstain on LLM) is the right one. Those are not the problem. The problem is that the project extends the phrase "point-in-time" from the data layer to the *whole system* and then sells "backtestable LLM analysts" on the strength of it. A PIT data layer constrains the prompt; it does nothing to the weights, and `DEFAULT_MODEL = "claude-opus-5"` has a training cutoff after essentially every date you could backtest — so **every LLM backtest this repo can run today is, by construction, in-sample for the model**. The literature says the resulting inflation is material and measurable rather than infinite (~30% of the LLM signal's in-sample predictive effect is attributable to memorization in the one study that isolates it), but "bounded" is not "absent," and the repo currently has no way to measure its own exposure. Separately, "given the same orders, a backtest replays to the same book" is true and is also a sleight of hand: the *orders* come from unseeded frontier-model sampling behind a floating model alias, so a fund-level backtest is not reproducible next month except by replaying a local cache directory that is not part of the result artifact. The honest version of this project is smaller and better: an LLM-powered **feature/extraction layer** feeding a conventional quant stack, plus a forward-only paper track that is the only place LLM *judgment* is allowed to claim a track record.

---

## The strongest argument AGAINST the premise

Lay it out in five steps; each one is individually defensible and they compound.

**1. The thing being backtested is not a function of the information set.** A backtest is a claim of the form: *this decision rule, applied to information available at time t, would have produced these returns.* `BuffettAgent.predict()` is not a function of the snapshot alone. It is a function of (snapshot, θ), where θ is a 10^12-parameter object fit on text through May 2026. The snapshot is PIT; θ is not; and the output depends on both. The repo's own guard is a prompt line — *"Treat the most recent filing date shown as the present day; do not use any knowledge of anything that happened after it"* — which is precisely the mitigation [Sarkar & Vafa](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678) tested and found insufficient: asked to predict 2020 risk factors from 2019 earnings calls, models were **3.6× more likely** to name "Pandemic" or "Disease Outbreak." An instruction not to know something is not a mechanism for not knowing it.

**2. The prompt hands the model the exact identifying pair it needs.** `snapshot.render()` deliberately omits `as_of` and the docstring credits this with keeping "the LLM from anchoring on a calendar date it could associate with post-date world events." That rationale does not survive contact with the rendered text: line 1 is `Company: AAPL | Sector: ... `, and every row of the history table prints its `filed` date. Ticker + most-recent-filing-date pins the as-of window to within one quarter. This is the *opposite* of [Glasserman & Lin's](https://arxiv.org/abs/2309.17322) de-biasing procedure, which works by stripping the company identifier — and even that only partly works, since Sarkar & Vafa and Lopez-Lira et al. find LLMs see through anonymization in longer documents. The date-free `as_of` buys a cache hit; it buys approximately zero leakage protection.

**3. The magnitude is not negligible and the repo cannot measure it.** [Gao, Jiang & Yan](https://arxiv.org/html/2512.23847) construct a "Lookahead Propensity" — how confidently a model calls up/down given *only* firm name, ticker and date, with zero contemporaneous information — and find that a one-SD increase in LAP raises the marginal effect of the LLM signal by about **32% of the standalone effect** (t = 3.64) for next-day returns, with the interaction **collapsing to insignificance after the training cutoff**. That is the shape of the problem in one number: roughly a third of the apparent edge is memory, and it evaporates out of sample. Nothing in `hedge_fund/` computes LAP, tests pre- vs post-cutoff subsamples, or records the served model version.

**4. The universe is a bigger leak than the data layer, and it is outside the data layer on purpose.** `FundSpec` deliberately does not carry a universe; `run.py` takes `--tickers` from the operator at runtime, today, in 2026. Any human typing a ticker list is typing survivors. `backtest_fund` then builds its trading grid from the *benchmark's* bars, so delisted names simply become `TickerSkip`s and disappear. The VISION says "No lookahead, ever." The single largest lookahead in equity backtesting — universe selection — is architecturally exempted with the comment "the universe is the study's input, not the mandate's." That is a defensible engineering choice and an indefensible thing to say "no lookahead, ever" over.

**5. The valuation personas are structurally unable to do the job their prompt assigns them.** `market_cap` and `price_to_earnings_ratio` in the snapshot come from the `FinancialMetrics` rows — filing-stamped, frozen between filings (the render even labels it "Market cap (latest filed)"). The Buffett system prompt asks for step 5, *"is the price (market cap, P/E) sensible,"* and the confidence rubric treats "a great business at a clearly excessive price" as a distinct neutral case. The agent cannot see the price. Combined with `content_hash` excluding `as_of`, the LLM sleeve's conviction is **literally a step function that changes only when a new filing lands** — a 40% drawdown between 10-Qs produces an identical `Signal.value`. So the claimed alpha model is "a quarterly, price-insensitive nonlinear score over 14 accounting ratios, expensively computed." That may still be a fine factor. It is not what the persona narrative says it is.

---

## The strongest argument FOR the premise (steelmanned)

I think there is a real case here, and it is stronger than the critique usually allows.

**LLM-derived text signals demonstrably carry out-of-sample alpha.** This is not speculation any more. [Supply-chain propagation of LLM-embedded textual signals](https://arxiv.org/pdf/2606.29290) yields a long-short book at annualized **Sharpe 0.86** and **FF5 alpha of 7.27%/yr**, surviving out-of-sample tests, placebos, sector-neutralization and subsamples. [From Text to Alpha](https://arxiv.org/html/2510.03195v5) reports more than 2× baseline alpha from LLM-extracted disclosure signals over 5,615 firm-quarters. The premise "language models can be alpha models" is empirically supported.

**And the contamination may be smaller than the alarm suggests.** [He, Lv, Manela & Wu's ChronoBERT](https://arxiv.org/html/2502.21206v1) pretrains chronologically-consistent models with hard annual cutoffs — the gold-standard control — and finds the long-short Sharpe from a *clean* model (4.80) essentially matches an unconstrained Llama 3.1 (4.90). For text→signal extraction, lookahead bias was worth roughly **2% of Sharpe**, i.e. nothing. Glasserman & Lin likewise found the "distraction effect" (general knowledge of the firm muddying sentiment measurement) mattered *more* than lookahead. If this project's LLM layer is, in effect, an extraction/scoring function over a PIT payload — and mechanically, as argued above, it *is* — then it lives much closer to the ChronoBERT regime than to the Gao-Jiang-Yan regime.

**The architecture is the part most projects get wrong, and this one got it right.** "The LLM never touches the trade" is enforced, not aspirational: `apply_limits` is pure arithmetic after `blend_signals`, clamps are recorded as `ClampEvent`s, `build_orders` is a pure diff, and `SimBroker` is genuinely deterministic (sells-then-buys, alphabetical, floor-toward-zero). Abstention is handled correctly and non-obviously — `blend_signals` drops abstained signals from *both* numerator and denominator, so "no opinion" cannot masquerade as "opinion: neutral," which is a mistake almost every comparable repo makes. The PIT data layer filters on `filing_date` server-side and explicitly refuses `company_facts.market_cap` because it is latest-only. Whoever wrote this understood what a backtest is. That earns the project the right to be criticized at the level of its premise rather than its code.

**And the one-code-path claim is true where it counts.** Both the backtest loop and run-today call the same `run_cycle`. That eliminates an entire class of silent research/production divergence that kills real funds. The claim only over-reaches when "one code path" is stretched into "therefore the backtest is meaningful."

---

## Findings, by severity

### 1. Pretraining leakage is unbounded *in the current configuration* because no model with a pre-test cutoff is reachable — **Critical** (confidence: very high)
`DEFAULT_MODEL = "claude-opus-5"`; every provider in `hedge_fund/llm/api_models.json` is a current frontier model. There is no configuration of this repo in which the test window post-dates the model's cutoff. The prompt-level mitigation is the one the literature specifically rejects. The mitigations that actually work, and their cost:

| Mitigation | Works? | What it costs the pitch |
|---|---|---|
| Model cutoff < test window (old open-weights, or ChronoBERT-style) | **Yes** — the only true fix | Kills the frontier-reasoning value prop; a 2021-cutoff 7B model is not "Buffett reasoning" |
| Anonymize ticker/sector + strip `filed` dates from the render | Partial (Glasserman & Lin); leaks through in long docs | Cheap. Costs almost nothing. **Do this first.** |
| Restrict the LLM to *extracting/summarizing* PIT text, judgment done by fitted code | **Yes**, and it is where the published alpha actually is | Kills the persona narrative; the LLM becomes a feature extractor |
| Forward-only paper trading | **Yes**, definitionally | Costs years. This is the honest track record and there is no shortcut |
| LAP-style contamination measurement (name+ticker+date only, measure P(up)+P(down)) | Measures, doesn't fix | ~$20 of tokens. **Do this second.** |
| Pre/post-cutoff subsample split | Measures, doesn't fix | Free once you log the served model |

**What would change my mind:** a LAP audit over this universe showing near-zero directional commitment on date-only queries, *plus* a pre/post-cutoff split where the LLM sleeve's excess return is statistically indistinguishable across regimes.

### 2. "One code path — what you backtest is what trades" is architecturally true and epistemically misleading — **Critical** (confidence: high)
Code-path identity guarantees the *mechanics* transfer. It guarantees nothing about the *signal*, which is the only thing in dispute. The slogan invites exactly the inference it doesn't support. Worse, the prompt cache is keyed identically in backtest and live mode (`prompt_key(agent, model, system, user)`, `as_of`-free), so a live "run it as of today" tick will happily replay a cached judgment generated during a backtest months earlier. That is literal path identity and it is not a good thing.
**Changes my mind:** rephrasing to "one execution path" plus a stated separation between mechanical fidelity and signal validity. That's a docs fix, not a code fix.

### 3. A fund-level backtest is not reproducible — **High** (confidence: high)
- No `temperature`/`seed` is set anywhere (`grep` confirms); Opus 5 rejects sampling params outright, so you get provider-default stochastic decoding with no seed facility.
- `claude-opus-5` is a floating alias. `PromptCache` keys on that **string**, not the served version. A provider-side update changes new answers while old entries replay forever under the same key — silent drift with no fingerprint.
- `run_cycle`'s docstring is candid ("a cold LLM cache makes an agent's first live call nondeterministic; the prompt cache makes every replay exact"), but the guarantee then rests entirely on `~/.hedge-fund/cache/llm/`, an untracked local directory. `FundBacktestResult` calls itself "the receipts file" and serializes `prompt_key` — but **not the prompt or the response**. The receipts file does not contain the receipts.

**What a backtest result from this system actually means:** *"One particular sequence of sampled model outputs, from an unversioned model, over this snapshot grid, produced this curve."* It is an anecdote with a Sharpe ratio attached, not an estimator.
**Honest reporting:** (a) pin `anthropic-version` and log `response.model` + `usage` per call into the record; (b) ship the prompt-cache tarball, or its Merkle root, *inside* `FundBacktestResult`; (c) report LLM-sleeve results as a **distribution over ≥5 independent re-samples**, not a point estimate — median and IQR of Sharpe/excess return. If the IQR spans zero, say so.

### 4. The economics permit exactly enough search to overfit, and not enough to validate — **High** (confidence: medium-high on the numbers, high on the conclusion)
Because `content_hash` excludes `as_of`, distinct LLM calls = **tickers × personas × (filings in window + 1)**, *not* × rebalances. That is a genuinely clever cost design and it is why this is affordable at all.

Per call: rendered snapshot (20 ttm rows × 14 fields) + persona prompt ≈ **1.3–1.5K input**; JSON thesis plus adaptive thinking (on by default for Opus 5 when `thinking` is omitted, as `make_llm` does) ≈ **~1.5K output**. At [Opus 5 pricing of $5/$25 per MTok](https://www.anthropic.com/pricing) → **≈ $0.045/call**.

| Study | Calls | Cost | Serial wall-clock @20s | At current max parallelism* |
|---|---|---|---|---|
| 25 names, 5 personas, 1yr | ~625 | ~$28 | ~3.5 h | ~40 min |
| 100 names, 5 personas, 5yr | ~10,500 | ~$470 | ~58 h | ~12 h |
| 500 names, 5 personas, 10yr | ~102,500 | ~$4,600 | ~570 h | ~115 h |

*`run_cycle` and `backtest_fund` are fully serial (`for strategy → for ticker → for model`). The only concurrency in the repo is `tui/app.py`'s `_warm_agents`, capped at `min(8, n_agents)` — it parallelizes **across personas**, not across tickers. So five personas ⇒ ~5× max speedup, and adding a sixth persona is free wall-clock while adding tickers is linear.

The structural finding: **folds are free, hypotheses are not.** CPCV/PBO re-folds over an unchanged config hit the cache and cost $0 — so the validation gate is economically fine. But the cache key includes `system` and `model`, so *any* prompt edit or model swap invalidates 100% of it. A 20-variant persona sweep on the mid-size study is ~$9.4K and, at current parallelism, months. Meanwhile [Bailey & López de Prado](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) show that on five years of daily data, roughly **45 trials** is already enough for the selected strategy's out-of-sample Sharpe to be expected ≤ 0. So the budget comfortably funds the number of trials that guarantees overfitting, while the latency prevents running enough of them to estimate the deflation. And `hedge_fund/validation/` is a 122-byte docstring: CPCV and PBO — the gate VISION says nothing gets capital without — do not exist.
**Changes my mind:** parallelize per-ticker and move to the Batch API (50% off, 24h turnaround is irrelevant for backtests) plus `effort: "low"` or Sonnet 5 — that's a realistic 10–20× cost reduction and 20×+ throughput, which genuinely changes the calculus. Worth doing regardless.

### 5. Persona framing is, on this architecture, most likely theater — **High** (confidence: medium-high)
The prior is bad: [Zheng et al.](https://aclanthology.org/2024.findings-emnlp.888/) tested 162 personas across 4 model families and 2,410 questions and found system-prompt personas **do not improve performance** vs. no persona — and notably *revised the abstract from the opposite claim*. And the architecture here strips out everything that could make a persona more than flavor: every persona sees the identical `build_snapshot()` payload (the base class default; none of the five override `build_snapshot` or `build_user_prompt`), so Druckenmiller — a macro trader — is reasoning over the same 14 accounting ratios as Graham, with no prices, no macro, no news. Five personas over one payload is five draws from a correlated scoring function, and `blend_signals` averages them, which will mostly cancel idiosyncrasy and leave a common fundamentals factor. That said — the *checklists* differ substantively (Buffett's prompt encodes ROE durability, margin trend, leverage, BVPS compounding), and a checklist is real structure, not a name. The open question is whether the edge lives in the checklist or the name.

**The discriminating experiment, which this system can almost run today.** Every ingredient exists: `PromptCache` persists the exact prompt/response, `Signal.metadata` carries `confidence`, `snapshot_hash` and `prompt_key`, and `CycleRecord` keeps everything.
1. **Cross-persona correlation.** Over the (ticker, snapshot_hash) grid, compute the 5×5 correlation of `Signal.value`. ρ > 0.8 ⇒ one factor wearing five hats.
2. **Reducibility.** Regress each persona's conviction on the snapshot's numeric fields (ridge, then a small GBM). R² > 0.8 ⇒ the persona is a deterministic function of 14 ratios and a 30-line `QuantModel` replicates it for $0 and 0 ms. **This is the single highest-value experiment in the whole project** and it costs one afternoon against an already-warm cache.
3. **Placebo persona.** Keep the checklist verbatim, swap "You are Warren Buffett" for a fictitious name and for "You are a disciplined value investor." If convictions and P&L are indistinguishable, the name is decoration.
4. **Ablation cross.** name-only vs checklist-only vs both. Separates brand from method.
What's missing to run it: nothing but ~200 lines in `hedge_fund/validation/` and a way to iterate the cache. It is not blocked.

### 6. Survivorship / universe selection is exempted by design — **High** (confidence: high)
Covered in step 4 above. The fix is a PIT index-membership source (CRSP, or a stored historical S&P constituent file) and making the universe a function of `as_of`. Until then, no fund-level backtest number should be quoted without "over a hand-picked, survivorship-selected universe" attached.

### 7. Zero-cost, zero-impact execution at the decision price — **Medium** (confidence: high)
`SimBroker` fills 100% of every order exactly at `order.price`, which is the same `as_of` close that priced the decision. `Commission` defaults to `0.0/0.0`; slippage is an acknowledged TODO. That is a market-on-close order that always fills at the print with no impact. For a weekly-rebalanced, conviction-weighted book over liquid mega-caps this is a modest optimism; for anything else it is not, and at weekly cadence the turnover drag is real. The repo is honest about this in comments, but `FundBacktestResult.metrics` reports `sharpe_ratio` and `excess_return_pct` with no cost haircut.

### 8. The PEAD baseline — the one clean comparator — is silently broken on older windows — **Medium** (confidence: medium-high)
`get_earnings_history(ticker, limit=12)` takes **no `end_date`**; it fetches the latest 12 filings *as of now* and `PEADModel` then filters client-side to `filing_date <= as_of`. Backtest 2018 and `past` is empty for most names ⇒ a non-abstaining `0.0` neutral that, per `blend_signals`, is a *real vote that dilutes* rather than an abstention. So your quant control quietly becomes a conviction-dampener on historical windows. This matters disproportionately because PEAD is the only thing you can currently compare the personas against.

### 9. Excellent design choices worth protecting — (no severity; stated so they don't get refactored away)
Abstain-vs-neutral discipline in `blend_signals`; fail-loud on unpriceable held positions in `_mark_prices`; the refusal to use `get_market_cap()` in `build_snapshot` because `company_facts` is latest-only; clamps-never-redistribute in `apply_limits`; `Commission` defaulting to zero specifically so old backtests replay to the cent. These are the instincts of someone who has thought about this properly. Keep them.

---

## The honest redesign

### Keep
- `run_cycle` / `AlphaModel` / `Signal` / `Broker` / `DataClient` — the whole interface spine. This is the asset.
- The PIT data layer and its `filing_date` discipline.
- `SimBroker`, `apply_limits`, `build_orders`, `blend_signals` — deterministic, pure, correct.
- The `CycleRecord` receipt and the prompt cache *as an audit log*. Its cost-saving role is a bonus; its real job is provenance.

### Cut (or demote)
- **"No lookahead, ever" as a global claim.** Replace with a scoped one: *"The data layer is point-in-time. The model weights are not — see LEAKAGE.md."* Then write LEAKAGE.md and put the LAP number in it.
- **"What you backtest is what trades"** → *"One execution path."* Say plainly that mechanical fidelity ≠ signal validity.
- **Quoting a headline Sharpe for an LLM sleeve at all** until #3 (re-sample distribution) and #6 (PIT universe) are done. Report excess return over the fundamentals-only quant baseline, with an IQR, or report nothing.
- **Persona *count* as a roadmap goal.** Shipping Cathie Wood, Burry, Ackman, Damodaran, Fisher, Pabrai, Taleb and Jhunjhunwala over the *same 14-ratio snapshot* multiplies cost and correlation without adding information. Ship experiment #5.2 first; let the answer decide whether persona #6 is a contribution or a liability.
- **Persona valuation language** while the snapshot has no price. Either feed the personas a PIT price/valuation block (which reintroduces per-date LLM calls and blows up the cost model — a real tradeoff, make it consciously), or rewrite the prompts to admit they are scoring business quality, not price.

### Build instead — where LLMs actually earn their keep in a quant stack
Ordered by defensibility, best first. The through-line: **LLMs are extraordinary at turning unstructured text into structured facts, and unremarkable at rendering the judgment that a fitted model should render.** Every published result above lives on the extraction side.

1. **`LLMExtractor`, a new layer below `AlphaModel`.** Point it at PIT primary documents — 10-K Item 1A/7, 8-Ks, call transcripts — and have it emit *typed features*, never convictions: `guidance_direction`, `segment_margin_commentary`, `litigation_severity`, `going_concern_flag`, `supply_chain_exposure`, `capex_intent`. Cache by `(doc_hash, extractor_version, model)`. These features then feed ordinary fitted models. This is where the 0.86 Sharpe / 7.27% FF5 alpha in the literature actually comes from, it is far more leakage-robust (extracting what a document says is not forecasting), and it is cheap because documents are immutable.
2. **A fitted combiner instead of `blend_signals`' fixed weights.** Once features are numeric and PIT, use cross-sectional ranking + a purged-CV-fitted model. The LLM stops voting; it supplies regressors.
3. **`hedge_fund/validation/` for real.** CPCV with purging and embargo, PBO, Deflated Sharpe with an honest trial count. The VISION already promises this and it is 122 bytes of docstring. Nothing else on the roadmap matters as much — without it, every number the system produces is unfalsifiable.
4. **A leakage-audit module.** `hedge_fund/leakage/`: LAP scoring (name+ticker+date-only query, measure P(up)+P(down)); pre/post-cutoff subsample split reported as a first-class metric on every LLM backtest; an anonymization toggle that strips ticker, sector and `filed` dates from `render()` so you can A/B the distraction effect the way Glasserman & Lin did.
5. **A forward-only paper track, as a separate artifact class.** The ledger's read half (already the current focus) plus a scheduler, and a hard rule: **an LLM-judgment strategy may only report a track record from forward paper trading.** Backtests of LLM judgment are for debugging plumbing, not for evidence. This costs years, which is exactly why it is the honest version.
6. **Post-hoc narration, kept and correctly labeled.** Having the LLM explain a position the quant stack took is genuinely valuable for a research tool and carries no leakage risk — because it makes no claim about the future. `Signal.reasoning` is already the right hook; just stop letting the narration drive the trade.
7. **Hypothesis generation, human-gated.** "Read these 200 filings and propose 10 testable cross-sectional hypotheses" is a great LLM task. Each proposal then goes through #3 with its trial count logged. That, not `LLMAgent`, is what "the fund runs its own lab" should mean — and the trial counter is what keeps Level 2 from being an overfitting machine.

**If you do exactly three things:** run experiment #5.2 (regress persona conviction on the snapshot's own numbers — it may end the debate in an afternoon); write the LAP audit; and build `validation/` for real. Everything else can wait.

---

## Sources

- [Sarkar & Vafa — Lookahead Bias in Pretrained Language Models (SSRN 4754678 / ICML 2025)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678)
- [Gao, Jiang & Yan — Detecting Lookahead Bias in LLM Forecasts (arXiv 2512.23847)](https://arxiv.org/html/2512.23847)
- [Glasserman & Lin — Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis (arXiv 2309.17322)](https://arxiv.org/abs/2309.17322)
- [He, Lv, Manela & Wu — Chronologically Consistent Large Language Models / ChronoBERT (arXiv 2502.21206)](https://arxiv.org/html/2502.21206v1)
- [Look-Ahead-Bench: a Standardized Benchmark of Look-ahead Bias in Point-in-Time LLMs for Finance (arXiv 2601.13770)](https://arxiv.org/pdf/2601.13770)
- [Evaluating LLMs in Finance Requires Explicit Bias Consideration (arXiv 2602.14233)](https://arxiv.org/html/2602.14233v1)
- [Supply Chain Propagation of Textual Signals: LLM Embeddings and Cross-Sectional Return Predictability (arXiv 2606.29290)](https://arxiv.org/pdf/2606.29290)
- [From Text to Alpha: Can LLMs Track Evolving Signals in Corporate Disclosures? (arXiv 2510.03195)](https://arxiv.org/html/2510.03195v5)
- [Zheng et al. — When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of LLMs (EMNLP Findings 2024)](https://aclanthology.org/2024.findings-emnlp.888/)
- [Bailey & López de Prado — The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality (SSRN 2460551)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [TradingAgents: Multi-Agents LLM Financial Trading Framework (arXiv 2412.20138)](https://arxiv.org/html/2412.20138) — the claimed-outperformance side
- [Anthropic API pricing](https://www.anthropic.com/pricing) — Opus 5 $5/$25 per MTok, Sonnet 5 $2/$10, Haiku 4.5 $1/$5; Batch API 50% off, cached input reads ~0.1×

**Key files behind the findings (all absolute):** `/home/user/ai-hedge-fund/hedge_fund/features/snapshot.py` (date-free render that still prints `filed` dates; filing-stamped `market_cap`; `content_hash` excluding `as_of`), `/home/user/ai-hedge-fund/hedge_fund/signals/llm_agent.py` (cache-keyed predict), `/home/user/ai-hedge-fund/hedge_fund/llm/client.py:39` (`DEFAULT_MODEL = "claude-opus-5"`; no temperature/seed), `/home/user/ai-hedge-fund/hedge_fund/llm/cache.py` (keys on the model *alias* string), `/home/user/ai-hedge-fund/hedge_fund/backtesting/fund.py` (serial loop; benchmark-derived grid), `/home/user/ai-hedge-fund/hedge_fund/pipeline/run_cycle.py` (serial strategy×ticker×model loops), `/home/user/ai-hedge-fund/hedge_fund/brokers/sim.py` + `/home/user/ai-hedge-fund/hedge_fund/brokers/models.py` (fill-at-mark, zero default commission), `/home/user/ai-hedge-fund/hedge_fund/signals/pead.py` (`get_earnings_history` with no `end_date`), `/home/user/ai-hedge-fund/hedge_fund/validation/__init__.py` (122 bytes, docstring only), `/home/user/ai-hedge-fund/hedge_fund/fund/spec.py:105` + `/home/user/ai-hedge-fund/hedge_fund/run.py:112` (universe as runtime input).

No files were modified.
