# LLM/Agent Trading Systems: Landscape Survey & Build Recommendations

*All repo stats pulled live from the GitHub API on 2026-09-20. Licences verified by fetching LICENSE files directly — several are misreported in secondary sources.*

---

## VERDICT

This genre is enormous by stars and nearly empty by engineering. The two biggest projects in it — TradingAgents (107.6k★) and virattt/ai-hedge-fund (63.5k★) — are both LLM-persona-debate demos whose own maintainers ship disclaimers saying they don't trade, and TradingAgents has spent its entire 2026 release cycle (v0.3.1 → v0.5.0) patching look-ahead bias bugs it shipped with, which is the strongest available proof that nobody in this genre had a validation layer either. The serious engineering is all in the *non-LLM* layer: Nautilus Trader, Hummingbot, Lean, ccxt, and the Hyperliquid node itself — and the correct move is to steal execution and data plumbing from those while writing your own signal and validation layers, because the LLM-agent repos have nothing reusable below the prompt. The AI4Finance ecosystem is a research-paper factory whose one genuinely reusable artifact is FinNLP's scraper catalogue (the "social one") and FinRL-Meta's data→environment pipeline (the "data one"); FinRL and FinGPT themselves are Jupyter-notebook estates you should read and not import. On the crypto side, ElizaOS/ai16z is economically dead (founder declared it so in Aug 2026 after a class-action settlement; token −97%) and GOAT SDK is formally **archived** — both are traps for anyone picking a 2024-era crypto agent framework today. The genuinely missing thing, and the one your asset stack uniquely enables, is a **point-in-time cross-venue perp feature store** that versions Nansen's smart-money labels as-of the date they were assigned, joins them to HIP-3 equity/commodity perp basis and funding, and is fed by your own builder-code order flow — because Nansen labels are point-in-time-unsafe by construction and *every* backtest built on today's label set is contaminated in exactly the same way your prior review flagged for the LLM. Also note a fact that changes your strategic picture: FOMO added perps in June 2026 routed through Hyperliquid + Trade.xyz, and Trade.xyz is the dominant HIP-3 builder — so your social data and your perp venue are the same value chain, not two separate assets.

---

## 1. THE AI4FINANCE ECOSYSTEM

Sorting out your half-memory: **FinNLP is "the social one," FinRL-Meta is "the data one."** They are different things and neither is what the ecosystem's star counts suggest.

| Repo | ★ | Forks | Licence | Last push | What it actually is |
|---|---|---|---|---|---|
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 21,270 | 3,014 | MIT | active | **Jupyter Notebook repo.** A collection of LoRA fine-tunes (Llama-2/ChatGLM) for financial *sentiment classification*, plus benchmarks. Not a system. |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 16,333 | 3,507 | MIT | active | **Jupyter Notebook repo.** Deep-RL trading pipeline (gym envs + stable-baselines/ElegantRL). 312 open issues. Demo-grade. |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 8,033 | 1,357 | Apache-2.0 | active | 4-layer agent platform producing **equity research reports**, not trades. Framework churn: AutoGen → OpenAI Agents SDK → PydanticAI → DeepSeek-Harness. |
| [ElegantRL](https://github.com/AI4Finance-Foundation/ElegantRL) | 4,365 | 980 | — | active | Massively-parallel PyTorch DRL. The most *engineering-shaped* thing in the org. |
| [FinRL-Trading / "FinRL-X"](https://github.com/AI4Finance-Foundation/FinRL-Trading) | 3,727 | 1,095 | MIT | active | Ensemble DRL strategy from the NeurIPS 2018 lineage; recently rebranded "AI-native modular infra." |
| [FinRL-Meta](https://github.com/AI4Finance-Foundation/FinRL-Meta) | 1,940 | 751 | MIT | active | **"the data one."** Automatic pipeline: real-market data → standardised gym-style market environments. Includes price/volume *and* social sentiment, ESG, Google Trends. |
| [FinNLP](https://github.com/AI4Finance-Foundation/FinNLP) | 1,487 | 276 | MIT | active | **"the social one."** "Democratizing Internet-scale financial data" — a catalogue of scrapers/adapters for news, Twitter, Reddit, StockTwits, Chinese sources. |
| [FinRL_Crypto](https://github.com/AI4Finance-Foundation/FinRL_Crypto) | 201 | 88 | — | active | Crypto variant. Small, but its walk-forward/cross-validation notebooks are the only place in the org that takes overfitting seriously. |

**FinGPT-Forecaster** is not a repo — it's [a subdirectory of FinGPT](https://github.com/AI4Finance-Foundation/FinGPT/tree/master/fingpt/FinGPT_Forecaster) plus a [HuggingFace Space](https://huggingface.co/spaces/FinGPT/FinGPT-Forecaster). Llama-2-7b-chat + LoRA fine-tuned on a year of DOW30 news→weekly-move pairs. It is the single most contaminated artifact in the ecosystem: a 2023 base model fine-tuned to predict 2022-2023 moves it has already read about. Do not use it as a template for anything.

**Solved well:** FinNLP genuinely mapped the financial-social-data surface; that catalogue saved someone months of source discovery. FinRL-Meta's "data → standardised environment" contract is the right *shape* for a feature store.

**Reusable piece:** FinNLP's source adapters (as a reference list, not a dependency — they rot). FinRL-Meta's environment schema as a design pattern. ElegantRL if you ever want RL sizing.

**What they got wrong — do not repeat:** (a) Notebooks as the delivery artifact, which makes reproducibility structurally impossible; (b) evaluation is always a single backtest with a Sharpe number and no out-of-sample or walk-forward discipline; (c) they cite each other's results rather than replicating them. The whole org is optimised for paper throughput, and it shows in the issue counts.

---

## 2. MICROSOFT QLIB — AND WHERE IT SITS

[microsoft/qlib](https://github.com/microsoft/qlib) — **48,677★, 7,703 forks, MIT, pushed 2026-09-17.** Active, real engineering, 476 open issues (large but healthy for the size).

Qlib is in a different category from everything above. It is a *quant research platform*: point-in-time-correct data layer with an expression engine, a model zoo (LightGBM/LSTM/Transformer/TFT), a workflow/experiment-tracking system (`qrun`), nested backtesting with realistic execution, and an RL order-execution module. It is the only project in this survey whose **data layer is designed around avoiding look-ahead bias as a first-class concern** rather than as a bug to be patched later.

Companion: [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) — **14,686★, 1,922 forks.** This is where "LLM meets quant" is actually done properly. The [R&D-Agent-Quant paper (arXiv:2505.15155, NeurIPS 2025)](https://arxiv.org/html/2505.15155v2) has the LLM *write factor and model code* which is then evaluated by Qlib's backtester — the LLM never sees prices, it proposes hypotheses and a `Co-STEER` code agent implements them, with a multi-armed-bandit scheduler over research directions. Claimed ~2× annualised return vs classical factor libraries using 70% fewer factors. There is no separate `RD-Agent-Quant` repo; it ships inside RD-Agent.

**Where it sits:** Qlib is to AI4Finance what Postgres is to a CSV folder. Qlib+RD-Agent is the *only* architecture in this entire survey that solves the contamination problem structurally — by demoting the LLM from forecaster to code-generator and keeping a deterministic, PIT-correct evaluator in the loop.

**What to steal:** the RD-Agent architecture, wholesale, as a *pattern*. LLM proposes → deterministic engine evaluates → feedback loop. This is the answer to the "empty validation layer" finding in your prior review.

**What's wrong for you:** Qlib is equities/China-A-share shaped. Its data layer assumes daily bars, calendars, and adjusted prices. Perps have no calendar, no dividends, 24/7 sessions, funding accruals, and mark-vs-index divergence. Forking Qlib's storage for perps is more work than writing a perp-native store. Steal the *ideas*, not the code.

---

## 3. LLM MULTI-AGENT TRADING FRAMEWORKS

### Runnable systems

| Repo | ★ | Licence | Verdict |
|---|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | **107,624** (20,591 forks) | Apache-2.0 | Runnable, LangGraph-based, analyst/bull-bear/trader/risk/PM debate. **Real engineering *now*, demo when it got famous.** |
| [HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader) | **22,399** (3,412 forks) | MIT | "100% fully-automated agent-native trading." Skills + FastAPI + React. Paper trading ($100k) plus live broker connectors (Binance/Coinbase/IBKR). Created Oct 2025, exploded fast. **No stated look-ahead discipline.** |
| [NoFxAiOS/nofx](https://github.com/NoFxAiOS/nofx) | 12,922 | — | Go, self-hosted LLM trading terminal with **hard-coded risk limits** across nine venues incl. Hyperliquid. The risk-limit-as-code design is the good part. |
| [pipiku915/FinMem-LLM-StockTrading](https://github.com/pipiku915/FinMem-LLM-StockTrading) | 959 | — | Research artifact. Layered memory (short/mid/long) + character/risk-profile design. The **memory architecture is the reusable idea**; the trading results are not. |
| [RndmVariableQ/AlphaAgent](https://github.com/RndmVariableQ/AlphaAgent) | 414 | — | Autonomous alpha mining, A-shares. Research artifact but with real backtest plumbing. Notably has **explicit anti-overfitting regularisation on formula complexity** — rare and worth reading. |

### Research artifacts only

- **Alpha-GPT** — no canonical open repo from the original authors. What's on GitHub under that name is unrelated hobby code. Evidence thin; treat as paper-only.
- **QuantAgent** ("Price-Driven Multi-Agent LLMs for High-Frequency Trading") — [Y-Research-SBU/QuantAgent](https://github.com/Y-Research-SBU/QuantAgent) exists as the official repo but is small and paper-shaped. The HFT framing is not credible at LLM latencies.
- **FinAgent** (the multimodal foundation agent paper) — no maintained public repo I could find under the original authors. GitHub `FinAgent` hits are unrelated. **Evidence thin.**
- **StockAgent** — LLM agents in a simulated market for studying trading *behaviour*, not generating alpha. Not a system.
- **R&D-Agent-Quant** — see §2. Lives inside microsoft/RD-Agent.

### The single most important finding in this cluster

TradingAgents' release history is a public record of the contamination problem:
- **v0.3.1** (Jul 2026) — "Alpha Vantage look-ahead filtering"
- **v0.4.0** (Aug 2026) — "look-ahead / point-in-time fixes across FRED macro, social sentiment, and the decision-log memory"
- **v0.5.0** (Sep 2026) — "point-in-time integrity across every dated path, SEC EDGAR fundamentals served as filed"
- [PR #1163](https://github.com/TauricResearch/TradingAgents/pull/1163): *"stop snapshot fundamentals leaking future data into backtests"* — yfinance `.info` and Alpha Vantage `OVERVIEW` are **live quote snapshots describing today**, and were being served as if they described a historical date.

That last one is the kind of bug that inflates a backtest by hundreds of basis points and is invisible unless you're looking for it. A 107k-star project shipped it for eighteen months. **Assume your own data adapters have the same class of bug until you've written a test that proves otherwise.**

Also worth knowing: the decision-log memory leak. If your agents write reflections to a memory store and read them back during a backtest, you have created a time machine. This is a design pattern *every* persona-debate repo uses, including yours.

**Evaluation layer (tiny but the only honest work in the genre):**
- [ulab-uiuc/live-trade-bench](https://github.com/ulab-uiuc/live-trade-bench) — 165★. Live-market evaluation explicitly positioned against backtest-only benchmarks.
- [Yanlewen/TradeTrap](https://github.com/Yanlewen/TradeTrap) — 83★. *"Are LLM-based Trading Agents Truly Reliable and Faithful?"* Adversarial reliability probes.
- Academic: [Look-Ahead-Bench (arXiv:2601.13770)](https://arxiv.org/pdf/2601.13770), [Detecting Lookahead Bias in LLM Forecasts (arXiv:2512.23847)](https://arxiv.org/html/2512.23847v2) — introduces **Lookahead Propensity (LAP)**, a per-(entity, date) estimate of how much the model has memorised the outcome. [FinCAD / "Summoning the Oracle to Slay It" (arXiv:2605.24564)](https://arxiv.org/abs/2605.24564) — inference-time context-aware decoding that suppresses memorised outcomes without retraining.

**GPT-4o can recall exact S&P 500 closes to <1% error inside its training window.** That is the whole argument against equity-persona backtests in one sentence — and it is also the argument *for* your perp pivot, since funding rates and perp microstructure are far less represented in pretraining corpora than daily equity closes.

**What this cluster got wrong — do not repeat:**
1. LLM-as-forecaster instead of LLM-as-code-generator. Contamination is unfixable in the first design and irrelevant in the second.
2. Agent-debate as the core abstraction. More agents = more tokens, more latency, more variance, and no demonstrated improvement in risk-adjusted return. Nobody has published an ablation showing the bull/bear debate beats a single well-prompted call.
3. Memory stores that leak future information into backtests.
4. Reporting a single backtest Sharpe as the result.

---

## 4. THE "AI HEDGE FUND" GENRE

| Repo | ★ | Forks | Licence | Verdict |
|---|---|---|---|---|
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | **63,555** | 11,143 | MIT | Upstream has moved on: there's now an `aihf` CLI, YAML "mandates," and the README reframes investor agents as *"pluggable, backtestable alpha models."* Still equities-only via financialdatasets.ai. README still says: *"the system does not actually make any trades."* |
| [51bitquant/ai-hedge-fund-crypto](https://github.com/51bitquant/ai-hedge-fund-crypto) | 623 | 154 | — | **The furthest-travelled fork.** Crypto, multi-timeframe, strategy ensembling, LangChain. Still signal-only. |
| [kyky2347/ALTA](https://github.com/kyky2347/ALTA) | 564 | 70 | — | "Autonomous LLM Trading Asterism." Evidence-first research, **auditable console, Shadow simulation, explicitly authorized broker execution.** Created Aug 2026. The audit/shadow framing is the most mature governance story in the genre — worth reading even if you don't fork it. |
| [Drakkar-Software/OctoBot-AI](https://github.com/Drakkar-Software/OctoBot-AI) | 11 | 1 | — | "A complete Crypto AI Hedge Fund Team framework." Tiny, but it's backed by [OctoBot](https://github.com/Drakkar-Software/OctoBot) (6,590★) which has **real exchange execution including Hyperliquid**. This is the genre's only entry with a credible execution layer behind it. |
| [wquguru/nof0](https://github.com/wquguru/nof0) | 2,751 | 426 | MIT | Open-source clone of the Alpha Arena concept. Go backend + Next.js. **Trades live on Hyperliquid with real capital**, $10k per agent. Explicitly *"a live competition arena, not a backtesting tool."* |
| [HammerGPT/Hyper-Alpha-Arena](https://github.com/HammerGPT/Hyper-Alpha-Arena) | 1,174 | 283 | — | Hyperliquid + Binance Futures AI trading. Mines/validates **86 factors with IC/ICIR and decay analysis** — actual factor hygiene, rare here. |

**Who has gone furthest past the demo stage?** Nobody in the fork tree. The honest answer is that the genre's most advanced artifact is not a repo at all — it's **[nof1.ai's Alpha Arena](https://nof1.ai/)**: six frontier LLMs, $10k real capital each, identical prompts and data, trading crypto perps on Hyperliquid. Season 1 (Oct 17 – Nov 3, 2025) was won by Qwen 3 Max at +22.3%, with DeepSeek Chat V3.1 close behind. Season 2 adds human traders as a control arm and "more rigorous statistical methods."

Alpha Arena matters for three reasons: (a) it is the only large-N evaluation of LLM traders with no backtest at all, so contamination is structurally impossible; (b) the winners were *not* the models with the best reasoning benchmarks, which should make you sceptical of "use a better model" as a strategy; (c) two weeks and six samples is not statistical significance, and they say so. **Treat the leaderboard as evidence that LLMs can be wired to a perp venue, not evidence that they have edge.**

---

## 5. CRYPTO / MEMECOIN AGENT TRADING

### Avoid

- **[goat-sdk/goat](https://github.com/goat-sdk/goat)** — 1,008★. Repo description is literally *"[Archived] Read-only historical snapshot. No issues, PRs, or updates."* Dead.
- **[elizaOS/eliza](https://github.com/elizaOS/eliza)** — 19,375★, 5,747 forks, MIT, **1,375 open issues.** Code still moves, but the project's economics collapsed: the founder [declared ai16z/ELIZAOS "dead" on Aug 5, 2026](https://www.coindesk.com/markets/2026/08/05/ai-agent-token-once-worth-usd2-4-billion-ends-with-founder-calling-it-dead) after settling a class action; token down ~97% from a $2.4bn peak. Do not build a business on a framework whose sponsor just litigated itself out of existence.
- **Virtuals Protocol** — [game-python](https://github.com/game-by-virtuals/game-python) 100★, [game-node](https://github.com/game-by-virtuals/game-node) 93★; `Virtual-Protocol/openclaw-acp` and `acp-node` are both **archived/deprecated**. VIRTUAL down ~89% from its $4.6bn peak. The SDKs never got traction even at the top of the hype cycle — 100 stars on the flagship SDK of a multi-billion-dollar protocol tells you everything.

### Real execution infrastructure worth reusing

| Repo | ★ | Licence | Use it for |
|---|---|---|---|
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 54,547 | **GPL-3.0** | Mature bot: hyperopt, walk-forward, dry-run, FreqAI. **Copyleft — a derivative trading system must be released under GPL-3.0 if you distribute it.** Fine if you never ship binaries; a landmine if you sell a product. |
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | 44,047 | MIT | 100+ exchange unified API. Use as a *reference* for normalisation schemas even where you write your own adapters. |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 29,145 | **LGPL-3.0** | **Rust-native, deterministic, event-driven engine with backtest/live parity by construction.** The single best execution core in open source. LGPL = you may link and stay proprietary; modifications to Nautilus itself must be published. |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 20,073 | Apache-2.0 | Market making. Strategy V2 controllers + executors are a genuinely good abstraction. **Hyperliquid perpetual connector works for live/testnet, but [backtesting on `hyperliquid_perpetual` is broken/limited](https://github.com/hummingbot/hummingbot/issues/7887).** |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | 8,536 | **MIT** | Cleanest strategy DSL of the crypto bots, permissive licence. Weaker venue coverage than Freqtrade. |
| [Drakkar-Software/OctoBot](https://github.com/Drakkar-Software/OctoBot) | 6,590 | — | Binance + Hyperliquid + 15 venues, paper trading, TradingView signals. |
| [enarjord/passivbot](https://github.com/enarjord/passivbot) | 2,104 | **Unlicense (public domain)** | Perp grid/DCA across Bybit/Bitget/OKX/Binance/**Hyperliquid**. Most permissive licence in the survey. Its **optimiser and backtester are Rust and genuinely fast.** |
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | 21,684 | Apache-2.0 | You already know this one — your fork is architecturally a Lean clone. Worth acknowledging rather than re-deriving. |

### Memecoin sniper / copy-trade genre

- [chainstacklabs/pumpfun-bonkfun-bot](https://github.com/chainstacklabs/pumpfun-bonkfun-bot) — 999★. *"not relying on any 3rd party APIs"* — direct bonding-curve interaction. The only one in the genre written by people who publish under a company name and maintain it.
- [coffellas-cto/Solana-Copy-Trading-Bot](https://github.com/coffellas-cto/Solana-Copy-Trading-Bot) — 409★, Rust, Jito/Nozomi/ZeroSlot integration.
- [GMGNAI/gmgn-skills](https://github.com/GMGNAI/gmgn-skills) — official GMGN OpenAPI agent skills: token/wallet/market queries + on-chain execution across Solana, BSC, Base. Market orders, limit orders, TP/SL, smart-money positions, KOL holdings, **insider and bundled-wallet exposure flags**. This is the right integration point for your GMGN leg — don't scrape the site.
- [buddies2705/awesome-memecoin-trading](https://github.com/buddies2705/awesome-memecoin-trading) — 295-entry index of the genre. Useful map, 12★, take the curation with salt.

**Blunt assessment of this genre:** the vast majority of "sniper bot" repos are lead-gen for Telegram services, with keyword-stuffed descriptions and no real code. A handful are real. The real ones solve *latency and transaction landing* (Jito bundles, gRPC/Geyser streams, ZeroSlot), which is a completely different engineering problem from anything in the LLM-agent world. **There is no LLM in the loop at memecoin-sniping latency and there cannot be.**

---

## 6. PERP-SPECIFIC OPEN SOURCE

### Infrastructure (the actually valuable tier)

| Repo | ★ | Licence | Note |
|---|---|---|---|
| [hyperliquid-dex/hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) | 1,831 | MIT | Official. Covers orders, account, market data, WS. 103 open issues. |
| [hyperliquid-dex/node](https://github.com/hyperliquid-dex/node) | 502 | — | **Non-validating node.** `--write-fills`, `--write-raw-book-diffs`, `--write-order-statuses`. ~100 GB/day. |
| [hyperliquid-dex/order_book_server](https://github.com/hyperliquid-dex/order_book_server) | 161 | — | **L4 book with per-order user addresses and order IDs.** Snapshot + order-status stream = real-time L4 reconstruction. |
| [hyperliquid-dex/hyperliquid-rust-sdk](https://github.com/hyperliquid-dex/hyperliquid-rust-sdk) | 473 | — | Official Rust. |
| [ControlCplusControlV/ferrofluid](https://github.com/ControlCplusControlV/ferrofluid) | 130 | — | *"An actually good Hyperliquid Rust SDK."* Community rewrite; the name is the review of the official one. |
| [infinitefield/hypersdk](https://github.com/infinitefield/hypersdk) | 217 | — | Alternative Rust SDK. |
| [nktkas/hyperliquid](https://github.com/nktkas/hyperliquid) | 442 | — | Best-maintained TS SDK (all JS runtimes). |
| [moondevonyt/Hyperliquid-Data-Layer-API](https://github.com/moondevonyt/Hyperliquid-Data-Layer-API) | 128 | — | Attempt at a Hyperliquid data layer. Early, but the *only* project framing HL data as a product. |

### Strategies / bots

- [discountry/ritmex-bot](https://github.com/discountry/ritmex-bot) — **567★, the largest Aster-tagged repo on GitHub.** TypeScript perp-DEX bot (Aster/BNB). This is effectively the Aster reference implementation in OSS.
- [Gajesh2007/ai-trading-agent](https://github.com/Gajesh2007/ai-trading-agent) — 547★, AI trading agent on Hyperliquid.
- [sanketagarwal/hyperliquid-trading-agent](https://github.com/sanketagarwal/hyperliquid-trading-agent) — 409★.
- [moss-site/moss-trade-bot-skills](https://github.com/moss-site/moss-trade-bot-skills) — 385★. Claims *"bit-exact between backtest and live execution"* — but the README qualifies it as **"simulated Hyperliquid perpetuals."** The claim is about determinism, not live fills. Still, backtest/live bit-parity is the right goal and almost nobody else states it.
- [Superior-Trade/superior-skills](https://github.com/Superior-Trade/superior-skills) (212★) + [trading-terminal](https://github.com/Superior-Trade/trading-terminal) (150★) — natural-language strategy → backtest → deploy on Hyperliquid/Lighter/Polymarket. **Uses Freqtrade for Hyperliquid and Nautilus for Polymarket/Lighter.** Important caveat: **it's a SaaS.** Requires `SUPERIOR_TRADE_API_KEY`; the repo is a skill library + docs layer over a hosted runtime. No licence stated. Read the architecture, don't depend on the service.
- [second-state/fintool](https://github.com/second-state/fintool) — 315★, Rust CLI per exchange (hyperliquid/binance/coinbase/okx/polymarket). Clean CLI-as-tool-surface design for agents.
- [alsk1992/CloddsBot](https://github.com/alsk1992/CloddsBot) — 2,795★. Polymarket + Kalshi + Binance + Hyperliquid + Solana + 5 EVMs, "scans for edge." Ambitious scope; scope is also the warning.

### Funding-rate arb / basis / liquidation hunting — **the gap**

This is close to empty in open source.
- [djienne/DELTA_NEUTRAL_VOLUME_BOT_ASTER_PERP_SPOT](https://github.com/djienne/DELTA_NEUTRAL_VOLUME_BOT_ASTER_PERP_SPOT) — 6★. Delta-neutral funding capture on Aster spot+perp.
- [ALLmightyn/FundingArbitrageBot](https://github.com/ALLmightyn/FundingArbitrageBot) — 0★, Hyperliquid + Lighter, claims mainnet.
- [donnywin85/perp-funding-collector](https://github.com/donnywin85/perp-funding-collector) — 0★. **Append-only funding-rate collector across Hyperliquid, dYdX v4, Aster, Paradex, Lighter, per-hour normalised, $2M OI floor at the sensor.** Zero stars, stdlib-only, and it is the single most correctly-designed artifact I found in this whole cluster. Read it.
- **Liquidation hunting: nothing.** Zero results. Either it's all private (likely) or nobody's tried.

**Every serious funding-arb repo I found has ≤6 stars.** That is a strong signal that the people doing this profitably are not publishing.

---

# SYNTHESIS

## What is genuinely missing

### 1. A point-in-time cross-venue perp feature store with *versioned labels*

This is the big one, and it is the perp restatement of the exact flaw your prior review found.

Nansen's smart-money labels are **point-in-time-unsafe by construction.** `smart-money/*` endpoints resolve against *"Smart Traders (30D, 90D, 180D, all-time)"* — a set that is recomputed continuously. A wallet is on today's list *because* it made money over the last 180 days. If you backtest "follow smart money" using today's label set against last year's trades, you have built a machine that follows wallets selected for having been right. That is survivorship bias with a REST API in front of it, and it will produce a spectacular backtest and lose money live.

Nobody has published a versioned-snapshot discipline for on-chain labels. The fix is unglamorous and nobody has done it: snapshot `smart-money/holdings`, `perp-leaderboard`, and `profiler/address/labels` on a schedule, store them immutably keyed by observation timestamp, and make every backtest read the snapshot *as of* the simulated date. Your Nansen credits are the input; the store is the asset. You'd also want the same discipline for FOMO leaderboard membership.

The store should join, on `(instrument, timestamp)`:
- funding rate, OI, mark-vs-index basis (from your funding collector)
- L4 microstructure from your HL node (`node_fills`, `raw_book_diffs`, `order_statuses`)
- Nansen perp positioning — `smart-money/perp-trades`, `profiler/perp-positions`, `tgm/perp-screener`, `perp-leaderboard` — **as of the snapshot date**
- FOMO social/copy-flow
- your own builder-routed flow

Nothing in open source does this. Qlib does PIT for equities. FinRL-Meta does data→env without PIT. Nobody does PIT for perps, and nobody at all does PIT for on-chain labels.

### 2. Builder-code order flow as a licensed private dataset

You have a structural asset almost nobody in OSS has and I found **no public write-up of anyone treating it as a data asset** (evidence genuinely thin here — flagging that).

Builder codes on Hyperliquid let you earn up to 0.1% on perps routed through your interface; [>$40M has flowed to builders and ~40% of HL DAUs now trade via third-party frontends](https://www.dwellir.com/blog/hyperliquid-builder-codes). Aster Code is the equivalent (100 ASTER deposit, agent-wallet approval, daily settlement). Users explicitly sign an EIP-712 `approveBuilderFee` authorising your builder address and max rate.

Two consequences most people miss:
- **The revenue is uncorrelated with your PnL.** It funds the research loop regardless of whether the strategies work. That inverts the failure mode of every project in this survey, which dies when the strategy dies.
- **You see routed order flow before it reaches the book.** That is a legitimate, consented, non-public dataset. It needs an explicit ethics/consent boundary written down before you touch it — trading against your own users' flow is where this becomes a problem, and you should decide that line deliberately rather than discover it later.

### 3. HIP-3 tokenized-perp basis, which literally nobody has built

As of 2026-09-18 Hyperliquid lists **286 perps: 178 native crypto + 108 HIP-3 builder markets from trade.xyz** covering equities (NVDA, TSLA, GOOGL, AMZN), a licensed S&P 500 perp, a synthetic Nasdaq index (XYZ100), pre-IPO (SpaceX), FX, and COMEX-benchmarked gold/silver.

That creates instrument pairs that did not exist eighteen months ago: **an NVDA perp with a funding leg, versus actual NVDA; a gold perp versus COMEX front-month.** The basis is driven by crypto-native funding dynamics on one side and equity-market mechanics on the other, and those two worlds have almost no shared participants. I searched and found **zero** open-source projects trading HIP-3 equity/commodity perp basis. This is the cleanest unexploited structural trade your venue access enables, and it does not need an LLM at all.

### 4. A negative-result registry

Every repo here publishes the backtest that worked. There is no artifact anywhere that records *"here is the strategy, here is the live PnL, here is the date we killed it and why."* The nearest things are live-trade-bench (165★) and TradeTrap (83★).

Your existing ledger work — the commits carrying the fund's book between runs and picking the resumed book by as-of date rather than mtime — is already the seed of this. That as-of-date-not-mtime instinct is exactly the discipline the rest of this genre lacks. Generalise it into a strategy lifecycle ledger and it becomes the thing that separates you from 63,000 stars' worth of demos.

### 5. The FOMO/Hyperliquid connection you may not have priced in

FOMO is a Solana-based social copy-trading app (500k+ traders) that **added perps in June 2026 routed through Hyperliquid and Trade.xyz**, and Trade.xyz is the dominant HIP-3 builder. It raised $75M Series B at $550M (Index Ventures, USV) and its daily protocol revenue has at times exceeded Hyperliquid's.

So your "social data" and your "perp venue" are not two separate assets — they're upstream and downstream of the same flow. FOMO social signal is **leading indicator for order flow into the exact HIP-3 markets you can trade**. That is a far more defensible framing than "memecoin sentiment," and it is the one thing on your asset list that nobody else can replicate.

---

## Build vs fork vs steal

| Subsystem | Verdict | What, specifically |
|---|---|---|
| **Data ingest — venue** | **Fork + own** | Fork [`donnywin85/perp-funding-collector`](https://github.com/donnywin85/perp-funding-collector) as your funding/OI sensor template (append-only, OI floor at the sensor — correct design). Own the HL node pipeline: [`hyperliquid-dex/node`](https://github.com/hyperliquid-dex/node) + [`order_book_server`](https://github.com/hyperliquid-dex/order_book_server). Budget ~100 GB/day and an archival tier from day one. |
| **Data ingest — labels/social** | **Build** | Nansen + FOMO + GMGN snapshotting with immutable as-of versioning. **This does not exist anywhere and it is your moat.** Use [`GMGNAI/gmgn-skills`](https://github.com/GMGNAI/gmgn-skills) as the GMGN client rather than scraping. |
| **Venue adapters** | **Library** | [`hyperliquid-python-sdk`](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) (MIT) for Python; [`ferrofluid`](https://github.com/ControlCplusControlV/ferrofluid) or [`infinitefield/hypersdk`](https://github.com/infinitefield/hypersdk) if you go Rust. [`nktkas/hyperliquid`](https://github.com/nktkas/hyperliquid) for TS. Aster: [`discountry/ritmex-bot`](https://github.com/discountry/ritmex-bot) is the de-facto reference. |
| **Feature store** | **Build** | Perp-native, PIT-correct, label-versioned. Steal Qlib's *expression engine + calendar-free PIT contract* as a design, not as code. Timescale/DuckDB + Parquet is enough; don't over-engineer. |
| **Signal generation** | **Steal the architecture, write the code** | Copy [`microsoft/RD-Agent`](https://github.com/microsoft/RD-Agent)'s pattern exactly: **LLM proposes hypotheses and writes factor/strategy code; a deterministic engine evaluates it; feedback drives the next iteration; the LLM never sees prices.** This structurally eliminates the contamination channel your prior review found. Read [`RndmVariableQ/AlphaAgent`](https://github.com/RndmVariableQ/AlphaAgent) for its complexity-regularisation on mined formulas. |
| **Backtester** | **Fork Nautilus** | [`nautechsystems/nautilus_trader`](https://github.com/nautechsystems/nautilus_trader), **LGPL-3.0** — link it, keep your strategies proprietary, publish any changes to Nautilus itself. It is the only engine with backtest/live parity by construction and native perp semantics. **Do not use vectorbt** — [it is Apache-2.0 **plus Commons Clause**](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md), which forbids selling anything whose value derives substantially from it. **Do not fork Freqtrade** (GPL-3.0) unless you're happy publishing your whole stack. |
| **Execution** | **Library, then own** | Start on the SDKs directly. Adopt Nautilus's execution layer when you need multi-venue. [`hummingbot`](https://github.com/hummingbot/hummingbot) (Apache-2.0) Strategy V2 *executors* are worth reading for the maker-side abstraction — but note its Hyperliquid **backtest** path is broken, so don't rely on it for validation. |
| **Risk** | **Build — and put it outside the LLM** | Steal the *idea* from [`NoFxAiOS/nofx`](https://github.com/NoFxAiOS/nofx): hard risk limits enforced in code, not in prompts. Non-negotiable for perps: per-instrument leverage caps, portfolio margin-usage ceiling, funding-cost budget per position, liquidation-distance floor, and a kill switch that no agent can reach. ADL and liquidation are venue actions you don't control — model them. |
| **Ledger / accounting** | **Build — you already are** | Keep going. Perps need funding accrual, realised/unrealised split, mark-vs-entry, cross-margin attribution, and **builder-fee revenue as a separate uncorrelated income line**. Nothing off-the-shelf handles builder revenue. [`ranaroussi/quantstats`](https://github.com/ranaroussi/quantstats) for tear sheets only — it does not understand funding. |
| **UI** | **Fork** | [`kyky2347/ALTA`](https://github.com/kyky2347/ALTA)'s auditable operator console is the best governance UI in the genre. [`wquguru/nof0`](https://github.com/wquguru/nof0) (MIT, Next.js) if you want the arena/leaderboard shape. Don't write a charting stack — embed TradingView. |
| **Evaluation** | **Build, seed from two repos** | [`ulab-uiuc/live-trade-bench`](https://github.com/ulab-uiuc/live-trade-bench) for the live-eval harness shape; [`Yanlewen/TradeTrap`](https://github.com/Yanlewen/TradeTrap) for adversarial reliability probes. Add LAP-style contamination scoring ([arXiv:2512.23847](https://arxiv.org/html/2512.23847v2)) to every LLM component you keep. |

---

## The honest warning list

**On backtests in this genre specifically**

1. **Snapshot endpoints masquerading as historical data.** yfinance `.info`, Alpha Vantage `OVERVIEW`, *and every Nansen `smart-money/*` call* describe **today**. TradingAgents shipped this bug for eighteen months at 100k+ stars. Write a test that asserts every dated fetch returns data whose publication timestamp precedes the simulated date, and run it in CI.

2. **Agent memory is a time machine.** If your personas write reflections to a store and read them back, a later backtest date can read a reflection written from a *future* run. This leak is invisible and inflates everything.

3. **LLM pretraining contamination doesn't go away by prompting.** GPT-4o recalls S&P 500 closes to <1% error inside its window. "Pretend you don't know" does not work. The only two real mitigations are architectural (RD-Agent: LLM writes code, never sees prices) or decoding-level (FinCAD). Prefer the first.

4. **Nansen label survivorship is the perp-native version of the same disease.** Covered above. This will be the bug that gets you if you skip the versioned snapshot store.

**On memecoin and social-signal strategies — the specific ways they die live**

5. **Base rates are catastrophic and the backtest never sees the failures.** [0.63% of pump.fun tokens graduate](https://arxiv.org/pdf/2607.02823) (4,338 of 655,770 in Sep–Oct 2025); ~95% are scams or rugs. Any dataset assembled from tokens that still have price history is 100% survivorship-biased. You must explicitly include the tokens that went to zero and stopped reporting.

6. **Your "smart money" is often a bundler cohort.** [Research identifies 1,012 persistent wallet cohorts (2–12 wallets each) that systematically co-fire as early buyers across 160,000+ launches.](https://arxiv.org/pdf/2607.02823) A high-win-rate wallet cluster can be the launch team, not alpha. GMGN exposes bundled-wallet and insider flags — use them as filters, and treat any signal that doesn't survive them as noise.

7. **Copy-trade signal decays before you can act on it.** By the time a leaderboard wallet's position appears in your polling loop, the copy flow has already moved the price; the entry you mirror is strictly worse than the original, and the copy flow itself is the thing moving it. [Academic work on crowding finds public crowding signals are incorporated into prices fast enough to offer no trading advantage — their value is regime detection, not alpha.](https://arxiv.org/pdf/2512.11913) Size the *decay*, not the signal.

8. **Backtests on memecoins ignore the costs that actually kill you.** Sandwich attacks, priority fees, Jito tips, failed-transaction burn, and thin-book slippage. A strategy with a 15% modelled edge and 20% realised round-trip cost is a money incinerator that backtests beautifully.

9. **There is no LLM in the loop at sniping latency.** If your thesis needs sub-second reaction to a launch, the LLM is decoration. Be honest about which of your strategies are LLM-driven and which are not, and don't let the LLM's presence in the repo imply it's in the critical path.

**On perps specifically**

10. **Funding is the whole trade and most backtesters ignore it.** A 20% annualised "return" is nothing if funding cost you 25%. Model funding accrual per 8h (or per hour, per venue), not as an afterthought.

11. **You do not control liquidation or ADL.** Both are venue-side. Backtests that assume you exit at your stop are lying. Model liquidation distance as a hard constraint, not a risk metric.

12. **Backtest/live divergence is the default, not the exception.** Nautilus and (claimed) moss-trade-bot-skills are the only projects that treat bit-parity as a design goal. If your backtester and live path are different code, they will disagree, and you will find out with money on.

**On project selection**

13. **Star count is anti-correlated with engineering quality here.** 107k stars = a persona-debate demo with eighteen months of look-ahead bugs. 0 stars = the only correctly-designed funding collector I found. The people making money on funding arb are not publishing; every serious funding-arb repo has ≤6 stars.

14. **Check whether the project's sponsor still exists.** ElizaOS/ai16z: founder declared it dead Aug 2026 after a class-action settlement, token −97%. GOAT SDK: archived. Virtuals' flagship SDKs: 100 and 93 stars, with two of its repos deprecated. The 2024 crypto-agent framework cohort is a graveyard, and its repos still look alive on GitHub.

15. **Licence traps.** vectorbt = Apache-2.0 **+ Commons Clause** (cannot sell software deriving substantial value from it). Freqtrade = GPL-3.0. Nautilus = LGPL-3.0 (fine — link freely, publish only your Nautilus changes). Jesse, ccxt, hyperliquid SDKs, nof0 = MIT. passivbot = Unlicense. Check these before you fork, not after.

---

## Sources

- [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) · [FinGPT_Forecaster](https://github.com/AI4Finance-Foundation/FinGPT/tree/master/fingpt/FinGPT_Forecaster) · [HF Space](https://huggingface.co/spaces/FinGPT/FinGPT-Forecaster)
- [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) · [FinRL-Meta](https://github.com/AI4Finance-Foundation/FinRL-Meta) · [FinNLP](https://github.com/AI4Finance-Foundation/FinNLP) · [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) · [ElegantRL](https://github.com/AI4Finance-Foundation/ElegantRL) · [FinRL-Trading](https://github.com/AI4Finance-Foundation/FinRL-Trading) · [FinRL_Crypto](https://github.com/AI4Finance-Foundation/FinRL_Crypto)
- [FinRL-Meta paper (arXiv:2211.03107)](https://arxiv.org/pdf/2211.03107) · [Dynamic Datasets and Market Environments (arXiv:2304.13174)](https://arxiv.org/pdf/2304.13174) · [FinGPT paper (arXiv:2306.06031)](https://arxiv.org/html/2306.06031v2)
- [microsoft/qlib](https://github.com/microsoft/qlib) · [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent) · [R&D-Agent-Quant (arXiv:2505.15155)](https://arxiv.org/html/2505.15155v2) · [NeurIPS 2025 poster](https://neurips.cc/virtual/2025/poster/121804)
- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) · [paper (arXiv:2412.20138)](https://arxiv.org/pdf/2412.20138) · [PR #1163 — snapshot fundamentals leaking future data](https://github.com/TauricResearch/TradingAgents/pull/1163) · [Issue #969 — backtesting support](https://github.com/TauricResearch/TradingAgents/issues/969)
- [HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader) · [pipiku915/FinMem-LLM-StockTrading](https://github.com/pipiku915/FinMem-LLM-StockTrading) · [RndmVariableQ/AlphaAgent](https://github.com/RndmVariableQ/AlphaAgent) · [Y-Research-SBU/QuantAgent](https://github.com/Y-Research-SBU/QuantAgent)
- [LLMQuant/awesome-trading-agents](https://github.com/LLMQuant/awesome-trading-agents) · [Sasha-Cui/Awesome-Applied-Agents-for-Investment](https://github.com/Sasha-Cui/Awesome-Applied-Agents-for-Investment/)
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) · [51bitquant/ai-hedge-fund-crypto](https://github.com/51bitquant/ai-hedge-fund-crypto) · [kyky2347/ALTA](https://github.com/kyky2347/ALTA) · [Drakkar-Software/OctoBot-AI](https://github.com/Drakkar-Software/OctoBot-AI)
- [nof1.ai Alpha Arena](https://nof1.ai/) · [Season 1 results](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/) · [Alpha Arena explained](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained) · [wquguru/nof0](https://github.com/wquguru/nof0) · [HammerGPT/Hyper-Alpha-Arena](https://github.com/HammerGPT/Hyper-Alpha-Arena)
- [elizaOS/eliza](https://github.com/elizaOS/eliza) · [ai16z declared dead (CoinDesk)](https://www.coindesk.com/markets/2026/08/05/ai-agent-token-once-worth-usd2-4-billion-ends-with-founder-calling-it-dead) · [Motley Fool analysis](https://www.fool.com/investing/2026/08/20/an-ai-agent-token-once-worth-24-billion-is-now-wor/) · [goat-sdk/goat (archived)](https://github.com/goat-sdk/goat) · [game-by-virtuals/game-python](https://github.com/game-by-virtuals/game-python) · [Virtual-Protocol/openclaw-acp (deprecated)](https://github.com/Virtual-Protocol/openclaw-acp)
- [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) · [ccxt/ccxt](https://github.com/ccxt/ccxt) · [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) · [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) · [jesse-ai/jesse](https://github.com/jesse-ai/jesse) · [polakowo/vectorbt](https://github.com/polakowo/vectorbt) · [QuantConnect/Lean](https://github.com/QuantConnect/Lean) · [enarjord/passivbot](https://github.com/enarjord/passivbot) · [Drakkar-Software/OctoBot](https://github.com/Drakkar-Software/OctoBot)
- [Hummingbot Hyperliquid connector](https://hummingbot.org/exchanges/hyperliquid/) · [Hyperliquid backtesting issue #7887](https://github.com/hummingbot/hummingbot/issues/7887) · [Strategy V2 framework](https://hummingbot.org/blog/how-to-configure-a-v2-strategy-controller-in-hummingbot/)
- [hyperliquid-dex/node](https://github.com/hyperliquid-dex/node) · [order_book_server](https://github.com/hyperliquid-dex/order_book_server) · [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) · [hyperliquid-rust-sdk](https://github.com/hyperliquid-dex/hyperliquid-rust-sdk) · [ferrofluid](https://github.com/ControlCplusControlV/ferrofluid) · [infinitefield/hypersdk](https://github.com/infinitefield/hypersdk) · [nktkas/hyperliquid](https://github.com/nktkas/hyperliquid)
- [Hyperliquid L1 data schemas](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/l1-data-schemas) · [Foundation non-validating node](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/foundation-non-validating-node) · [Historical data](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data) · [L4 order book (QuickNode)](https://www.quicknode.com/docs/hyperliquid/datasets/l4-book)
- [Hyperliquid builder codes docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) · [Builder codes revenue analysis (Dwellir)](https://www.dwellir.com/blog/hyperliquid-builder-codes) · [Build with builder codes](https://www.dwellir.com/blog/build-hyperliquid-trading-app-builder-codes)
- [HIP-3 docs](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals) · [What is HIP-3 (Nansen)](https://nansen.ai/post/what-is-hip-3-hyperliquid) · [HIP-3 & HIP-4 tokenized stocks (CoinGecko)](https://www.coingecko.com/learn/hyperliquid-hip3-hip4-tokenized-stocks-and-prediction-markets) · [Hyperliquid markets list](https://hyperliquidguide.com/markets)
- [Aster Code builder program](https://docs.asterdex.com/program-and-rewards/aster-code) · [Aster API docs](https://docs.asterdex.com/product/aster-perpetuals/api/how-to-create-an-api) · [discountry/ritmex-bot](https://github.com/discountry/ritmex-bot) · [buddies2705/awesome-perp-dex](https://github.com/buddies2705/awesome-perp-dex)
- [Nansen API endpoints overview](https://docs.nansen.ai/api/overview) · [Smart Money](https://docs.nansen.ai/api/smart-money) · [Token God Mode flows](https://docs.nansen.ai/api/token-god-mode/flows) · [Nansen API](https://nansen.ai/api)
- [fomo.family](https://fomo.family/blog) · [Fomo (platform) — Wikipedia](https://en.wikipedia.org/wiki/Fomo_(platform)) · [Fomo app explained (Datawallet)](https://www.datawallet.com/crypto/fomo-app-explained) · [Fomo $75M Series B](https://bitcoinfoundation.org/news/crypto-companies-news/fomo-investments/) · [Fomo tops Hyperliquid in protocol revenue](https://solanacompass.com/news/fomo-tops-hyperliquid-in-24-hour-protocol-revenue-as-solana-copy-trading-app-extends-its-run)
- [GMGNAI/gmgn-skills](https://github.com/GMGNAI/gmgn-skills) · [GMGN smart money docs](https://docs.gmgn.ai/index/track-smart-money) · [GMGN copy trade docs](https://docs.gmgn.ai/index/copy-trade-copy-smart-money-automatically-earn-sol)
- [chainstacklabs/pumpfun-bonkfun-bot](https://github.com/chainstacklabs/pumpfun-bonkfun-bot) · [coffellas-cto/Solana-Copy-Trading-Bot](https://github.com/coffellas-cto/Solana-Copy-Trading-Bot) · [buddies2705/awesome-memecoin-trading](https://github.com/buddies2705/awesome-memecoin-trading)
- [donnywin85/perp-funding-collector](https://github.com/donnywin85/perp-funding-collector) · [djienne/DELTA_NEUTRAL_VOLUME_BOT_ASTER_PERP_SPOT](https://github.com/djienne/DELTA_NEUTRAL_VOLUME_BOT_ASTER_PERP_SPOT) · [ALLmightyn/FundingArbitrageBot](https://github.com/ALLmightyn/FundingArbitrageBot)
- [moss-site/moss-trade-bot-skills](https://github.com/moss-site/moss-trade-bot-skills) · [Superior-Trade/superior-skills](https://github.com/Superior-Trade/superior-skills) · [Superior-Trade/trading-terminal](https://github.com/Superior-Trade/trading-terminal) · [second-state/fintool](https://github.com/second-state/fintool) · [alsk1992/CloddsBot](https://github.com/alsk1992/CloddsBot) · [NoFxAiOS/nofx](https://github.com/NoFxAiOS/nofx)
- [ulab-uiuc/live-trade-bench](https://github.com/ulab-uiuc/live-trade-bench) · [Yanlewen/TradeTrap](https://github.com/Yanlewen/TradeTrap)
- [Detecting Lookahead Bias in LLM Forecasts (arXiv:2512.23847)](https://arxiv.org/html/2512.23847v2) · [Look-Ahead-Bench (arXiv:2601.13770)](https://arxiv.org/pdf/2601.13770) · [Summoning the Oracle to Slay It / FinCAD (arXiv:2605.24564)](https://arxiv.org/abs/2605.24564) · [DatedGPT (arXiv:2603.11838)](https://arxiv.org/html/2603.11838) · [Look-Ahead Bias in LLM Trading](https://paperswithbacktest.com/course/look-ahead-bias-llm-trading)
- [Pump.fun Graduation Regime Windows — survival analysis of 832,941 launches (arXiv:2607.02823)](https://arxiv.org/pdf/2607.02823) · [The Memecoin Phenomenon (arXiv:2512.11850)](https://arxiv.org/pdf/2512.11850) · [Catching the Rug (arXiv:2608.20271)](https://arxiv.org/html/2608.20271v1)
- [Not All Factors Crowd Equally: Modeling, Measuring, and Trading on Alpha Decay (arXiv:2512.11913)](https://arxiv.org/pdf/2512.11913) · [AI-Driven Alpha Decay (arXiv:2605.23905)](https://arxiv.org/pdf/2605.23905) · [LLMs and the Shortening Shelf Life of Copyable Alpha (IBKR)](https://ibkrcampus.com/campus/ibkr-quant-news/llms-and-the-shortening-shelf-life-of-copyable-alpha/)

---

**Flagged as thin evidence:** (a) no public write-up found of anyone treating builder-code routed flow as a research dataset — the strategic claim is mine, not sourced; (b) FinAgent and Alpha-GPT have no maintained canonical public repos I could locate; (c) zero open-source liquidation-hunting projects found, which is consistent with either "it's all private" or "nobody's tried" and I can't distinguish; (d) `moss-trade-bot-skills`' backtest/live bit-parity claim is unverified and self-reported against a *simulated* venue.

**No files were changed.**