# Internal architecture audit — `/home/user/ai-hedge-fund`

Read-only. No files changed. Baseline confirmed: `430 passed, 38 skipped in 10.39s` (all 38 skips are live-API tests gated on `FINANCIAL_DATASETS_API_KEY`).

---

## Verdict

The core is better than the docs deserve: `run_cycle` really is one function, `backtest_fund` really does loop it, and the seams (`AlphaModel`/`DataClient`/`Broker`/`FundSpec`) are cut in the right places and are genuinely swappable. But the claim "one code path by design — what you backtest is what trades" is currently true of a system that only has one clock and one broker: `SimBroker` is the only `Broker` implementation, so "backtest," "run today," and "paper" are the same simulated fill at the same close, and the divergence the claim guards against has not been tested yet — it will appear the day a second broker exists. Meanwhile ~1,449 LOC of simulation lives *outside* `run_cycle` (the per-model `BacktestEngine` and the whole event-study package) against ~766 LOC that runs through it, so "one path" describes the newest path, not the repository. The ledger — the piece the roadmap calls the current focus — has two defects that silently destroy the exact property it exists to create (`latest_run` orders by mtime, not `as_of`; a spec-schema change makes old receipts unreadable and the failure is swallowed into a silent capital reset). And "portfolio construction" and "risk" are accurate names for about 15% of what those words mean: there is no covariance, no volatility target, no drawdown control, no liquidity model, and no transaction costs reachable from a mandate at all.

**Salvageable with changes**, and most of the changes are small. Nothing here is structurally wrong-shaped; the debt is concentrated in (a) the ledger's read half, (b) the data protocol's point-in-time contract, and (c) a portfolio stage whose normalization throws away the only information the scalar contract preserved.

---

## Findings

### CRITICAL

**C1 — `latest_run` resumes by file mtime, not by `as_of`. A fund can time-travel into its own future book.**
`hedge_fund/ledger.py:53-57` sorts receipts by `p.stat().st_mtime`. `hedge_fund/run.py:143-144` and `hedge_fund/tui/app.py:1273-1275` both call it *before* `args.date` is considered, and nothing compares `prior.as_of` to the cycle's `as_of`. Verified empirically: writing a 2026-09-20 receipt then a 2020-01-02 receipt makes `latest_run` return the 2020 book; the reverse order makes a 2020 run resume a 2026 book.

Why it matters: this is the single mechanism that turns NAV into a track record. A user who backfills a date, re-runs a cycle, or copies a receipt between machines (mtime is not preserved by most copies) gets a book from the wrong point in time, and `run.py:146-149` prints a reassuring "resuming … from its {as_of} book" line while doing it. There is no idempotency key either, so the scheduler the roadmap wants will double-trade any re-fired tick.

Fix (small): sort by `(record.as_of, mtime)` after parsing, and refuse to resume when `prior.as_of >= as_of` unless `--fresh`. Add an `as_of` uniqueness check so re-running a date replaces rather than compounds.

**C2 — A `FundSpec` schema change makes every prior receipt unreadable, and the failure is silently converted into a capital reset.**
`CycleRecord` embeds a full `FundSpec` (`hedge_fund/pipeline/models.py:43`), `FundSpec` is `extra="forbid"` (`hedge_fund/fund/spec.py:109`), and `latest_run` catches `ValueError` and moves on (`hedge_fund/ledger.py:60-62`). `CycleRecord` has no `schema_version`.

This is not hypothetical — `load_spec` carries an explicit workaround for exactly this, popping a removed `universe` key (`hedge_fund/fund/spec.py:164-168`), which proves such specs exist in users' `~/.hedge-fund/`. There is no equivalent pop on the receipt path. Verified: a receipt whose embedded spec carries `universe` raises `extra_forbidden`, `latest_run` returns `None`, and the fund restarts at mandate capital with **no message** (`run.py:146` only prints on the success branch). The entire performance history vanishes and the run looks normal.

Fix: add `schema_version` to `CycleRecord`; make the receipt's embedded spec a forward-compatible dict or a `extra="allow"` audit copy; and make an unreadable *newest* receipt loud (warn/raise) rather than fall through to the next-oldest — falling through is worse than failing, because resuming a stale book re-executes trades that already happened.

**C3 — Three of the eight `DataClient` methods have no as-of parameter; the one that has one ignores it.**
`hedge_fund/data/protocol.py:78-86`: `get_company_facts(ticker)`, `get_earnings(ticker)`, `get_earnings_history(ticker, limit)` take no date. The protocol docstring pins point-in-time behavior for `get_financial_metrics` only (`protocol.py:42-44`). Worse, `get_market_cap(ticker, end_date)` (`hedge_fund/data/client.py:207-215`) accepts `end_date` and then returns `company_facts.market_cap` — today's number — falling back to filed metrics only when facts are absent. A PIT-looking signature over a non-PIT implementation is the worst possible shape: `features/snapshot.py:139-142` avoids it with a comment explaining why, which means the author knew and left the trap armed for the next contributor.

Concrete live consequence via PEAD (`hedge_fund/signals/pead.py:105`): `get_earnings_history(ticker, limit=8)` is anchored on *now*, not on `as_of`. The client-side filter at `pead.py:55` then correctly drops future filings — but the 8-row window was already truncated to the eight most recent filings in existence. Backtest any date more than ~2 years back and `past` is empty, so PEAD returns neutral for the entire early history and only starts firing near the present. A long PEAD backtest doesn't produce a wrong answer; it produces a quietly empty one. `CachedDataClient` compounds it: the cache key is `(ticker, limit)` with no date and no TTL (`hedge_fund/data/cached.py:85-90`), so the eight filings are frozen at whenever you first ran, and identical code gives different backtests on different machines — which also falsifies the byte-identical determinism claim at `run_cycle.py:12-15`.

Fix: put `as_of` in every `DataClient` method signature (it is the protocol's entire reason to exist), have `get_earnings_history` filter server-side on `filing_date_lte`, delete or correct `get_market_cap`, and key the cache on the as-of date. Add a mocked contract test per method mirroring `data/test_client_contract.py:109` — today only `get_financial_metrics` is pinned, and every test that would catch this is among the 38 skipped.

**C4 — Same-day execution against same-day filings.**
PEAD fires when `(as_of - filed).days <= self._signal_window_days` (`hedge_fund/signals/pead.py:64`), which includes **0**. `run_cycle` then marks and fills at `as_of`'s close (`run_cycle.py:164`, `execution.py:40`, `sim.py:72-120`). Earnings 8-Ks are overwhelmingly filed after the 4pm close. So the fund routinely buys at a price that printed *before* the announcement it is reacting to. The same applies to any fundamentals row whose `filing_date == as_of`.

Why it matters: this is the classic free-money leak, and it is worth more than every other modeled effect in the system combined — PEAD's entire claimed edge is the first days of drift. Roadmap marks PIT 🚧; this is the concrete thing that makes it 🚧.

Fix (small, high value): require `filed < as_of` in the signal window, or add a `decision_lag` / next-open fill to the execution stage. The seam already exists — `Order.price` is set by the caller (`brokers/models.py:46-48`), so a next-open mark is a `_mark_prices` change, not a pipeline change.

### MAJOR

**M1 — Conviction-weighted normalization destroys both magnitude and dispersion.**
`hedge_fund/portfolio/construction.py:83-87` normalizes by `sum(|conviction|)`. The docstring (lines 9-12) admits the "lone weak view gets the full gross target" wart. It is worse than admitted. Verified:
- Analysts at `+1.0` and `-0.99` on AAPL — near-total disagreement — produce a **100% of gross target** long in AAPL (blended conviction 0.005, but it is the only nonzero, so it gets everything).
- A single ticker with `market_neutral=True` demeans to exactly zero and can never trade — `fundamental-ls.yaml` is market-neutral, so a one-name run of the flagship pod is a silent no-op.

So the answer to "is scalar conviction in [-1,+1] a sufficient contract": the scalar is a defensible *minimum*, but the portfolio stage doesn't even use what the scalar carries. It uses only the cross-sectional ranking of the blended mean, and it throws away (a) absolute magnitude, (b) inter-analyst dispersion, (c) each analyst's own confidence — which `LLMAgent._to_signal` already folds irreversibly into `value = sign × confidence/100` (`signals/llm_agent.py:160`), so "neutral at 95% confidence" and "bullish at 0% confidence" are the same float, and one of them dilutes the blend while the abstain path (`llm_agent.py:180-188`) correctly doesn't.

Fix: keep `Signal.value` as the contract but add an optional `uncertainty`/`horizon` and *use* `confidence` separately from `sign`; normalize by `max(sum|c|, k)` rather than `sum|c|` so weak books stay small; size by conviction-over-dispersion rather than conviction-share. `Signal.components`/`metadata` (`models.py:26-27`) already give a place to carry it without breaking existing models.

**M2 — Transaction costs exist in the broker and are unreachable from a mandate.**
`Commission` is implemented and tested (`brokers/models.py:15-28`, `brokers/sim.py:102`), and `RECONCILIATION.md` lists it as closed. But grep shows it is constructed nowhere outside `SimBroker`'s `or Commission()` default: `backtesting/fund.py:102` is `SimBroker(cash=spec.capital)`, `run.py:144` and `ledger.py:66-86` pass `commission=None`, and `FundSpec` has no cost field at all. Slippage is a comment (`sim.py:6`). Every backtest and every resumed run therefore fills the entire order at the close for free.

This interacts badly with M4 and with the example mandate: `example.yaml` gives PEAD 40% of capital at `signal_window_days=4` on a *weekly* grid, so that sleeve's names are opened and fully liquidated a few times a year at up to 25% of NAV each — full round trips, priced at zero. A strategy that only looks good gross of costs is the normal failure mode of exactly this kind of system.

Fix: add `costs: {per_trade, per_share, slippage_bps}` to `FundSpec`, thread it into the three `SimBroker` construction sites. One afternoon.

**M3 — "Portfolio construction" and "risk" are accurate names for box-constraint arithmetic, not for either discipline.**
`risk/limits.py:57-113` is three clamps: per-name `|w|`, gross `sum|w|`, and a net-exposure cash floor. That is a *position limit* module, and a correct, idempotent, well-audited one (`ClampEvent` is a genuinely good idea). What is absent, and what any book actually runs on:
- **No covariance or correlation anywhere in the repo.** Five personas reading the same `FundamentalsSnapshot` will agree, so the "diversification" from having five analysts is nominal; a 10-name equal-conviction book of megacap tech is one bet. Per-name caps do nothing about this.
- **No volatility targeting and no vol scaling.** `gross_target` is a constant in the spec. A 0.25 cap means 0.25 of NAV whether the name is a utility or a 120-vol biotech.
- **No drawdown control / no kill switch.** `max_drawdown_pct` is *reported* (`backtesting/fund.py:184-191`) and never *acted on*. There is no `RiskLimits` field that can stop the fund.
- **Drawdown is measured on the rebalance grid only** (`fund.py:175`), so a weekly fund's reported max DD is blind to everything intra-week — it systematically understates the number the roadmap's "always-on" user cares most about.
- **No liquidity model.** `SimBroker` fills any size at the close (`sim.py:72`). No ADV cap, no participation limit, no market impact. `execution.py:8` names Almgren-Chriss as future work, which is honest but leaves sizing unconstrained by tradeability.
- **No margin.** `sim.py:9-12` admits cash may go negative. So the `min_cash_reserve_pct` reasoning at `limits.py:66-71` ("a short credits its proceeds, margin is not modeled, so a market-neutral book sits near 100% cash") is arithmetically consistent with the simulator and false about every real broker — and verified: a fully net-short book `{-0.5, -0.5}` with `min_cash_reserve_pct=0.5` is passed through completely unclamped. The cash floor cannot constrain a short book at all.

This is the gap I'd rank highest for the *stated goal* after the ledger bugs, because it is the one that cannot be fixed by a patch: covariance requires a returns panel, an estimator, and a decision about shrinkage, and none of the plumbing for it exists.

Fix: it needs a real stage, not a field. Minimum credible version: a `RiskModel` protocol alongside `Broker`/`DataClient` that takes `(weights, marks, price history)` and returns clamped weights + events, with an inverse-vol implementation first (cheap, uses data already fetched) and a covariance-aware one second.

**M4 — A held name absent from `--tickers` is silently liquidated.**
`run_cycle.py:87` seeds `netted` from `tradeable` only; `build_orders` (`execution.py:38`) then treats every held name with no target as target-zero. That is correct and well-documented *as a cycle contract* — but the universe is a per-run argument that lives nowhere durable (`FundSpec` is deliberately ticker-free, `spec.py:103-107`), while the *book* now persists across runs (`ledger.py`, `run.py:143`). Forget one ticker on the command line and the resumed fund closes that position at the next close, for free, and the receipt records it as an ordinary decision.

The TUI patches around this with `_last_universe` (`tui/app.py:583-590`); the CLI does not, and the scheduler the roadmap wants has nowhere to read it from. The mandate-is-the-desk argument is right in principle but the persistent book changed the stakes.

Fix: persist the universe with the book (it is already on `CycleRecord.universe`), default `--tickers` to the resumed receipt's universe, and require an explicit flag to trade a narrower set than you hold.

**M5 — The "one code path" claim, quantified.**
Shared through `run_cycle`: `run_cycle.py` 176 + `execution.py` 53 + `construction.py` 89 + `limits.py` 114 + `sim.py` 130 + `backtesting/fund.py` 204 = **766 LOC**, serving CLI single-cycle (`run.py:160`), CLI backtest (`run.py:130`), TUI run (`tui/app.py:1277`), TUI backtest (`tui/app.py:1830`). That part of the claim holds and is the repo's best structural property.

Outside it: `backtesting/engine.py` (299) + `backtesting/__main__.py` (190) — a per-model harness with its *own* sizing (equal-dollar, `engine.py:178`), its own entry/exit mechanics (fixed holding period, edge-triggered arming, `engine.py:127-153`), its own equity curve (trades concatenated across tickers as if sequential — `engine.py:206-221`, which makes its max-DD meaningless) and its own Sharpe (per-trade returns scaled by `sqrt(trades_per_year)`, `engine.py:262-263`, not comparable to `fund.py:177-181`'s per-period Sharpe). Plus `event_study/` (960 LOC) with its own data access. **1,449 LOC ≈ 1.9× the shared pipeline** produces performance numbers by other means. VISION.md:94 calls this "an older per-model harness … for single-model studies"; it is still exported from `backtesting/__init__.py:3` and still has a `__main__`.

Modes: 3 claimed, **1 broker implemented**. "Run today" is `SimBroker` at the as-of close — a one-day backtest, not paper trading. The claim's real test (does a `PaperBroker` fit behind the protocol without the pipeline noticing?) has not been run yet.

Smaller duplications of the same path: receipt writing is implemented twice — `ledger.save_run` with a filename-collision loop (`ledger.py:38-41`) and `tui/app.py:1283-1285` **without** it, so two TUI runs in the same second silently overwrite one another in the ledger the other half of the code treats as append-only. Broker resume is copy-pasted (`run.py:143-144` ≡ `tui/app.py:1273-1275`). The TUI prefetcher hand-mirrors `run_cycle`'s request pattern, importing the private `_MARK_LOOKBACK_DAYS` (`tui/app.py:73`) and hard-coding `limit=20` to match `build_snapshot`'s default (`tui/app.py:1866-1867`) — change either and the warm-cache promise silently breaks.

**M6 — Concurrency: non-atomic writes under an 8-thread fan-out.**
`PromptCache.put` (`llm/cache.py:44-48`) and `CachedDataClient._write` (`data/cached.py:129-131`) are bare `write_text`. `tui/app.py:1869-1872` and `:1899-1903` run 8 threads that hit both. Two threads writing the same key interleave into truncated JSON; both readers catch `JSONDecodeError` and return a miss (`cache.py:41-42`, `cached.py:126-127`), so the symptom is a repeated paid LLM call rather than a crash — benign today, expensive at scale, and the same pattern on `save_run` (`ledger.py:42`) would leave a truncated *receipt*, which C2's swallow-and-continue then turns into a silent resume from a stale book.

For the stated always-on goal, "no database, receipts only" is defensible for *audit* (append-only JSON with the full spec inline is genuinely good provenance) and indefensible for *state*. There is no index (every `latest_run` stats the whole glob; every history pane parses every file — `tui/app.py:456-466`), no transaction spanning "place orders → write receipt" (crash between them and the broker and the book disagree, which for a real broker is unrecoverable from receipts alone), no lock, and lifetime realized P&L requires re-parsing every receipt by design (`ledger.py:76-79`) where each receipt embeds the full spec plus every analyst's full thesis text. Minimum viable fix without a database: atomic `os.replace` writes everywhere, a `fcntl` lock per fund, an append-only index line per receipt (`{as_of, nav, cash, path}`), and a `schema_version`.

### MINOR

**m1 — `annualized_return_pct` can be fabricated.** `backtesting/fund.py:170`: `years = max(calendar_days / 365.25, 0.01)`. A 3-day backtest raises `(1+total)` to the 100th power. The TUI accepts arbitrary windows. Guard with a minimum window or return `None`.

**m2 — Sharpe has no risk-free rate** (`fund.py:177-181`). At current front-end yields this materially overstates the number the whole system is selected on. One field.

**m3 — The "date-free prompt" claim is false.** `features/snapshot.py:79-86` explains that `render()` excludes `as_of` partly to keep the LLM "from anchoring on a calendar date it could associate with post-date world events" — and then line 107 prints `report_period | filing_date` for every row. The model knows the date to the day. The cache-key rationale for excluding `as_of` is sound and worth keeping; the anti-anchoring rationale should be deleted rather than believed.

**m4 — `FundSpec.name` is unvalidated and used to build filenames** (`ledger.py:33`, `tui/app.py:1284`, `tui/app.py:578-579` globs). A name containing `/`, `..`, or glob metacharacters misroutes or mis-globs receipts. One validator.

**m5 — `_mark_prices` makes one 7-day price request per ticker per cycle** (`run_cycle.py:156-161`), each a distinct cache key. A 78-week weekly backtest over 10 names is 780 cold requests that collectively fetch a few years of data. Fetch the full window once per backtest and slice.

**m6 — `except Exception: pass` in both TUI warm paths** (`tui/app.py:1262`, `:1897`). Justified as best-effort, but it means the roster shows an analyst "done" whose call actually failed, and the user's first signal that something is wrong is an abstain in the final record.

---

## What the design gets right

These are real, and several are better than what most projects at this size do.

- **`run_cycle` is genuinely one function, and `backtest_fund` genuinely calls it.** `backtesting/fund.py:108` is the entire loop body. No re-implemented mechanics, no "research mode" branch, no `if backtest:` anywhere in the pipeline. That is the hard part of the claim and it is done.
- **Purity discipline at the seams.** `blend_signals`, `apply_limits`, `build_orders` are pure and take primitives; `run_cycle` is the only impure piece and says so (`run_cycle.py:10-11`). This is why the 19 `test_run_cycle` tests can be meaningful without network or mocks, and why swapping the broker is plausibly free.
- **`Broker` deliberately has no `equity()`** (`brokers/protocol.py:23-26`). Correct and non-obvious: marks are point-in-time knowledge the pipeline owns, and a broker that reported its own equity would let a live venue's marks silently replace the backtest's. Most people get this wrong.
- **Fail-loud data contract.** `FDClientError` vs. empty-list, with 404 as the only `None` (`data/client.py:253-302`), and the explicit reasoning that silent empties read as "no signal" and poison backtests. The `get_prices` pagination loop merging pages *below* the cache (`client.py:227-236`) so the cache never memoizes a truncated page is a detail that takes a real incident to learn.
- **Abstain ≠ neutral.** `construction.py:64-68` excludes abstained signals from numerator *and* denominator. This single line is the difference between "the LLM timed out" and "the LLM is bearish," and almost every comparable system conflates them.
- **A held name with no price raises rather than being skipped** (`run_cycle.py:165-169`). Refusing to compute a NAV you can't justify is the right instinct, and it's the instinct the rest of the roadmap should be built on.
- **`ClampEvent`** (`risk/limits.py:41-47`): every limit that fires is recorded with before/after and lands in the receipt. The clamp ordering is chosen so the pair is idempotent and documented why (`limits.py:60-71`), and the `1e-12` tolerance comment at `limits.py:103-107` is someone thinking about what a human reading the receipt will see.
- **`extra="forbid"` on every spec model** so YAML typos fail at load, not at trade time (`fund/spec.py:99-100`). The right default — it just needs to not apply to the archived audit copy (C2).
- **`CycleRecord` is self-contained and round-trips.** Embedding the full spec, every thesis, every clamp, every order and fill in one JSON is excellent provenance; `fund why AAPL` really is answerable from it alone. The problem is using it as *state*, not as a receipt.
- **Specs-are-data** (`fund/spec.py:16-18`): the TUI only composes the same YAML the CLI reads, so the human path and the machine path can't diverge in what they can express. That is the right way to keep a future strategy generator honest.
- **`Fund` constructs models once, not per cycle** (`fund/spec.py:178-188`) so prompt and earnings caches survive across ticks — a deliberate, correct decision about where state lives.
- **The prompt cache is a cache, a persistence record, and a debug trail at once** (`llm/cache.py:1-11`), including keeping unparseable responses. For a system whose analysts are nondeterministic, storing the exact prompt and the exact response behind every `Signal` is the only thing that makes replay meaningful.
- **`normalize_universe`** as the single entry-point normalizer (`fund/spec.py:143-157`) so what the engine trades can't drift by caller.
- **The docs are unusually candid.** VISION.md:92-95 volunteers that only two of three modes exist and that the legacy harness remains; the ROADMAP marks PIT 🚧 and validation ⬜ rather than claiming them. My criticisms above are mostly that specific claims overshoot, not that the project is misrepresenting itself wholesale.

---

## What the empty validation layer says about priorities

`hedge_fund/validation/__init__.py` is 122 bytes — a docstring naming CPCV and PBO, and nothing else. Against that: `tui/app.py` is **2,129 LOC, 26% of the non-test codebase**, larger than the entire pipeline + portfolio + risk + execution + brokers + ledger combined (766 LOC). The LLM layer has 65 tests.

The revealing detail isn't the ratio, it's `tui/app.py:402` + `:593-600`: the fund-picker screen renders each saved mandate with `_last_score` — its most recent backtest's total and excess return — as "a quiet scoreboard on each slot." The product surface for **selecting a mandate by in-sample backtest return** is built, polished, and on the landing screen. The surface that would tell you whether that return survives multiple testing is an empty file.

That is the whole priority statement. Every ingredient for overfitting is present and working — a strategy library (`hedge_fund/strategies/*.yaml`) whose combinations you are explicitly invited to try, a fast warm-cache backtester, a persisted leaderboard, and VISION.md's Level-2 goal of an agent that *generates* candidate strategies automatically. The thing that makes a research loop different from a random-search machine is the gate, and the gate is the one unbuilt component. VISION.md:161-164 promises "nothing it invents gets capital without passing the validation gate"; today that gate is a docstring, so the promise is currently enforced only by the fact that the strategy generator doesn't exist either.

This is also why C3/C4 matter more than they'd otherwise: a validation layer built on top of a backtester with same-day fills and undated earnings history would certify the leakage rather than catch it. The ordering I'd argue for is PIT correctness → transaction costs → validation gate, and *then* the scheduler — not the roadmap's ledger → paper broker → scheduler, which builds the always-on fund on numbers nothing has checked.

---

## Confidence, and what would change my mind

**C1 (mtime resume) — high confidence.** Reproduced directly: two receipts, newer `as_of` written first, `latest_run` returns the older one. I'd revise only if there's an intended invariant I missed that receipts are always written in `as_of` order — but `run.py --date` accepts any date and `--fresh` is the only escape hatch, so I don't think one exists.

**C2 (schema evolution → silent reset) — high confidence on the mechanism, medium on frequency.** Reproduced: a legacy `universe` key in the embedded spec raises `extra_forbidden` and `latest_run` returns `None` silently. What would change my mind: evidence that `~/.hedge-fund/mandates/` in the wild contains no pre-`universe`-removal receipts — but `load_spec`'s dedicated workaround at `spec.py:164-168` is strong evidence the opposite already happened once for mandates, and receipts got no such treatment. Even if no user is affected *today*, the next `FundSpec` field is a live grenade, and the failure mode (silent, looks-normal capital reset) is the worst available.

**C3 (protocol PIT) — high confidence on `get_market_cap` ignoring `end_date` (read the code) and on the three undated methods (read the protocol). Medium on the PEAD truncation severity**, because I can't call the live API: I'm inferring that `/earnings/?ticker=X&limit=8` returns the *most recent* 8 filings. If it instead returns the oldest, or if `_get`'s pagination loop (`client.py:244-250`) walks past the limit and returns the full history, the truncation symptom softens — though the undated cache key (`cached.py:85-90`) and the determinism claim are still broken either way. Running `pytest` with a real `FINANCIAL_DATASETS_API_KEY` (the 38 skipped tests) would settle it in a minute.

**C4 (same-day fills) — high confidence on the code path** (`pead.py:64` includes day 0; `run_cycle.py:164` marks at the as-of close; `sim.py:72` fills there). Medium on magnitude, which depends on what fraction of `filing_date` values in this provider's data are post-close same-day — that's an empirical question I can't answer offline. What would change my mind: if the provider's `filing_date` is already the *next* trading day for after-hours filings. Worth checking before anything else, because it's cheap to check and expensive to be wrong about.

**M3 (risk is aspirational) — high confidence, no empirical dependency.** This is an absence, and I grepped for it: no covariance, correlation, volatility target, drawdown limit, ADV, or margin anywhere in `hedge_fund/`. The only thing that would change my mind is a claim that "risk" here is scoped deliberately to position limits — which the code arguably supports (`limits.py` is titled "Risk limits," not "Risk model") but `VISION.md:46`'s "Chief risk officer → Risk model — hard limits the analysts cannot override" does not.
