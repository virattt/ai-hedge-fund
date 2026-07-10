"""Market-hours daemon: watch loop + heavy at open + light/heavy escalation."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from colorama import Fore, Style, init

from integrations.alpaca.broker import AlpacaBroker
from integrations.alpaca.light_cycle import fetch_spy_price, snapshot_reference_prices
from integrations.alpaca.market_hours import (
    SESSION_CLOSE,
    is_regular_session,
    now_et,
    session_open_datetime,
    trading_date,
)
from integrations.alpaca.market_signals import MarketSignalEngine, WatchEvaluation
from integrations.alpaca.price_feed import PriceFeed
from integrations.alpaca.rate_limit import RateLimiter
from integrations.alpaca.run_cycle import CycleInputs, CycleResult, create_broker, run_cycle
from integrations.alpaca.session import SessionStore, TradingSessionState
from integrations.alpaca.strategy import CycleKind, SchedulerConfig, load_scheduler_config
from integrations.alpaca.triggers import TriggerMonitor

init(autoreset=True)
logger = logging.getLogger(__name__)


def _sleep_seconds(seconds: float) -> None:
    if seconds > 0:
        logger.debug("Sleeping %.1fs", seconds)
        time.sleep(seconds)


def _analysis_dates() -> tuple[str, str]:
    end = trading_date().isoformat()
    start = (trading_date() - timedelta(days=90)).isoformat()
    return start, end


def _should_run_heavy_open(now: datetime, session: TradingSessionState, config: SchedulerConfig) -> bool:
    if session.heavy_open_completed:
        return False
    open_at = session_open_datetime(now.date(), delay_minutes=config.open_delay_minutes)
    if now < open_at:
        return False
    # A crashed heavy-open attempt (e.g. data-provider 429) must not retry
    # in a hot loop — back off between attempts.
    if session.last_heavy_attempt_at:
        try:
            last = datetime.fromisoformat(session.last_heavy_attempt_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=now.tzinfo)
            if (now - last.astimezone(now.tzinfo)) < timedelta(minutes=config.heavy_open_retry_minutes):
                return False
        except (TypeError, ValueError):
            pass
    return True


def next_speculative_batch(
    universe: list[str],
    held: list[str],
    cursor: int,
    batch_size: int,
) -> tuple[list[str], int]:
    """Next rotating slice of non-held tickers, plus the advanced cursor.

    Held positions are excluded because every cycle already merges them in
    (see build_portfolio), so the batch budget goes entirely to speculative
    names.
    """
    held_set = {h.upper() for h in held}
    spec = [t.upper() for t in universe if t.upper() not in held_set]
    if not spec or batch_size <= 0:
        return [], cursor
    start = cursor % len(spec)
    batch = [spec[(start + i) % len(spec)] for i in range(min(batch_size, len(spec)))]
    return batch, (start + len(batch)) % len(spec)


def _should_run_scheduled_light(
    now: datetime,
    session: TradingSessionState,
    config: SchedulerConfig,
) -> bool:
    if not session.heavy_open_completed:
        return False
    if not session.last_light_at:
        return True
    try:
        last = datetime.fromisoformat(session.last_light_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=now.tzinfo)
        return (now - last.astimezone(now.tzinfo)) >= timedelta(minutes=config.light_interval_minutes)
    except (TypeError, ValueError):
        return True


def _light_cooldown_ok(session: TradingSessionState, config: SchedulerConfig) -> bool:
    if not session.last_light_at:
        return True
    try:
        last = datetime.fromisoformat(session.last_light_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=now_et().tzinfo)
        elapsed = now_et() - last.astimezone(now_et().tzinfo)
        return elapsed >= timedelta(minutes=config.light_promote_cooldown_minutes)
    except (TypeError, ValueError):
        return True


def _print_cycle_banner(kind: CycleKind, trigger_reason: str | None = None) -> None:
    label = kind.upper().replace("_", " ")
    colors = {
        "heavy": Fore.MAGENTA,
        "light": Fore.CYAN,
        "triggered_heavy": Fore.YELLOW,
        "watch": Fore.GREEN,
    }
    color = colors.get(kind, Fore.WHITE)
    print(f"\n{color}{Style.BRIGHT}=== {label} CYCLE ==={Style.RESET_ALL}")
    if trigger_reason:
        print(f"{Fore.YELLOW}Trigger: {trigger_reason}{Style.RESET_ALL}")


def _format_watch_line(sym: str, metrics: dict[str, float]) -> str:
    parts = [f"{sym} ${metrics.get('price', 0):.2f}"]
    if "vs_open_pct" in metrics:
        parts.append(f"open {metrics['vs_open_pct']:+.2f}%")
    if "vs_last_watch_pct" in metrics:
        parts.append(f"tick {metrics['vs_last_watch_pct']:+.2f}%")
    if "momentum_pct" in metrics:
        parts.append(f"mom {metrics['momentum_pct']:+.2f}%")
    return " | ".join(parts)


def _print_watch_status(
    evaluation: WatchEvaluation, *, limiter: RateLimiter, top_movers: int = 8
) -> None:
    """One compact block per tick: SPY, biggest movers, alerts. Printing all
    ~127 universe lines every minute buried the alerts."""
    symbols = {s: m for s, m in evaluation.metrics.items() if s != "SPY"}
    print(
        f"\n{Fore.GREEN}{Style.BRIGHT}--- WATCH ---{Style.RESET_ALL} "
        f"{now_et().strftime('%H:%M:%S')} ET | {len(symbols)} symbols"
    )
    spy = evaluation.metrics.get("SPY")
    if spy:
        print(f"  {_format_watch_line('SPY', spy)}")
    movers = sorted(
        symbols.items(),
        key=lambda kv: abs(kv[1].get("vs_open_pct", 0.0)),
        reverse=True,
    )[:top_movers]
    if movers:
        print(f"  {Fore.WHITE}Top movers vs open:{Style.RESET_ALL}")
        for sym, metrics in movers:
            print(f"    {_format_watch_line(sym, metrics)}")
    if evaluation.alerts:
        for alert in evaluation.alerts:
            print(f"  {Fore.YELLOW}▸ {alert}{Style.RESET_ALL}")
    else:
        print(f"  {Fore.WHITE}No alerts{Style.RESET_ALL}")
    promote = evaluation.promote.upper()
    pc = Fore.MAGENTA if evaluation.promote == "heavy" else Fore.CYAN if evaluation.promote == "light" else Fore.WHITE
    print(f"  Escalation: {pc}{promote}{Style.RESET_ALL} | API budget left ~{limiter.available}/min")


def run_scheduled_cycle(
    broker_name: str,
    *,
    base_inputs: CycleInputs,
    kind: CycleKind,
    analysts: list[str],
    trigger_reason: str | None = None,
    tickers: list[str] | None = None,
) -> CycleResult:
    _print_cycle_banner(kind, trigger_reason)
    start_date, end_date = _analysis_dates()
    inputs = CycleInputs(
        tickers=list(tickers) if tickers is not None else base_inputs.tickers,
        start_date=start_date,
        end_date=end_date,
        show_reasoning=base_inputs.show_reasoning,
        selected_analysts=analysts,
        model_name=base_inputs.model_name,
        model_provider=base_inputs.model_provider,
        margin_requirement=base_inputs.margin_requirement,
        initial_cash=base_inputs.initial_cash,
        execute=base_inputs.execute,
        save_ledger=base_inputs.save_ledger,
        cycle_kind=kind,
        trigger_reason=trigger_reason,
    )
    return run_cycle(broker_name, inputs)


def _update_session_after_heavy(
    session: TradingSessionState,
    result: CycleResult,
    *,
    triggered: bool,
) -> None:
    prices = snapshot_reference_prices(result.agent_result)
    spy = fetch_spy_price()
    if triggered:
        session.mark_trigger()
    else:
        session.mark_heavy(prices=prices, spy_price=spy)
    if prices and not session.open_reference_prices:
        session.open_reference_prices = prices
    if spy is not None and session.spy_open_price is None:
        session.spy_open_price = spy


class TradingDaemon:
    """
    Infinite watch loop during market hours:

    1. Poll live prices (one batched Alpaca call) — no LLM, no Finnhub fundamentals
    2. Run algorithmic signals (moves vs open, tick-to-tick, momentum, SPY)
    3. Optionally check news on an interval (rate-limited)
    4. Escalate to light (rule-based) or heavy (LLM) when thresholds fire
    5. Scheduled light refresh every N minutes regardless

    Lazy universe rotation: analysis cycles never run the full universe at
    once. Held positions are analyzed in every cycle (merged in by
    build_portfolio); speculative tickers rotate through cycles in slices of
    `batch_size`, so a 127-name universe is spread across the trading day.
    Triggered heavy cycles analyze only the alerting symbols plus holdings.
    """

    def __init__(
        self,
        broker_name: str,
        base_inputs: CycleInputs,
        config: SchedulerConfig | None = None,
    ) -> None:
        self._broker_name = broker_name
        self._base_inputs = base_inputs
        self._config = config or load_scheduler_config()
        self._sessions = SessionStore(self._config.session_dir)
        self._alpaca_limiter = RateLimiter(self._config.alpaca_data_calls_per_minute)
        self._news_limiter = RateLimiter(self._config.news_calls_per_minute)
        self._price_feed = PriceFeed(alpaca_limiter=self._alpaca_limiter)
        self._signals = MarketSignalEngine(self._config)
        self._triggers = TriggerMonitor(self._config, news_limiter=self._news_limiter)
        self._broker, self._alpaca_config = create_broker(
            broker_name,
            initial_cash=base_inputs.initial_cash,
            margin_requirement=base_inputs.margin_requirement,
            execute=base_inputs.execute,
        )

    def run_forever(self) -> None:
        cfg = self._config
        print(f"{Fore.GREEN}{Style.BRIGHT}Trading daemon started (US equities).{Style.RESET_ALL}")
        print(
            f"Watch: every {cfg.watch_interval_seconds}s (batch prices, no LLM) | "
            f"Heavy: {cfg.open_delay_minutes}m after 9:30 ET | "
            f"Light: every {cfg.light_interval_minutes}m or on signal | "
            f"Model: {cfg.heavy_model_provider}/{cfg.heavy_model_name}"
        )
        print(
            f"Rate limits: Alpaca ~{cfg.alpaca_data_calls_per_minute}/min | "
            f"News ~{cfg.news_calls_per_minute}/min"
        )
        if self._alpaca_config and self._alpaca_config.kill_switch:
            print(f"{Fore.RED}KILL SWITCH active — orders will not execute.{Style.RESET_ALL}")

        while True:
            try:
                self._tick()
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Daemon stopped by user.{Style.RESET_ALL}")
                return
            except Exception:
                logger.exception("Daemon tick failed — retrying in 30s")
                try:
                    _sleep_seconds(30)
                except KeyboardInterrupt:
                    print(f"\n{Fore.YELLOW}Daemon stopped by user.{Style.RESET_ALL}")
                    return

    def _market_open(self) -> bool:
        if isinstance(self._broker, AlpacaBroker):
            return self._broker.is_market_open()
        return is_regular_session()

    def _tick(self) -> None:
        if not self._market_open():
            self._maybe_run_eod_reports()
            self._sleep_until_closed()
            return

        now = now_et()
        session = self._sessions.load()
        if session.trading_day != trading_date().isoformat():
            session = session.for_today()

        tickers = self._base_inputs.tickers

        if _should_run_heavy_open(now, session, self._config):
            # Open cycle analyzes holdings (always merged in) plus one
            # speculative batch — never the entire universe at once.
            batch, session.batch_cursor = next_speculative_batch(
                tickers, self._held_tickers(), session.batch_cursor, self._config.batch_size
            )
            session.mark_heavy_attempt()
            self._sessions.save(session)
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._heavy_inputs(),
                kind="heavy",
                analysts=list(self._config.heavy_analysts),
                tickers=batch,
            )
            _update_session_after_heavy(session, result, triggered=False)
            self._sessions.save(session)
            _sleep_seconds(self._config.watch_interval_seconds)
            return

        snapshots = self._price_feed.fetch(tickers, include_spy=True)

        evaluation = self._signals.evaluate(tickers, session, snapshots)

        prices = {sym: snap.price for sym, snap in snapshots.items() if sym != "SPY"}
        if prices:
            # Tickers the open cycle didn't analyze get their first watch
            # price as the open reference so vs-open signals cover the
            # whole universe.
            session.seed_open_references(prices)
            session.mark_watch(prices)
        spy_snap = snapshots.get("SPY")
        if session.spy_open_price is None and spy_snap is not None:
            session.spy_open_price = spy_snap.price

        news_reason: str | None = None
        if self._signals.should_check_news(session) and evaluation.promote != "heavy":
            news = self._triggers.check_news(self._news_tickers(session), session)
            if news.fired:
                news_reason = "; ".join(news.reasons[:2])
                evaluation.add_alert(news_reason, level="heavy")
                for sym in news.symbols:
                    evaluation.add_symbol(sym, level="heavy")

        self._sessions.save(session)
        _print_watch_status(evaluation, limiter=self._alpaca_limiter)

        if evaluation.promote == "heavy":
            reason = "; ".join(evaluation.heavy_alerts[:3] or evaluation.alerts[:3])
            # Only re-analyze the symbols whose *heavy* signal fired, capped
            # at batch_size (holdings are merged in automatically). Light
            # tick-move symbols must not ride along into an LLM cycle, and a
            # market-wide alert (e.g. SPY move) re-analyzes holdings only.
            focus = evaluation.heavy_symbols[: self._config.batch_size]
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._heavy_inputs(),
                kind="triggered_heavy",
                analysts=list(self._config.heavy_analysts),
                trigger_reason=reason,
                tickers=focus,
            )
            _update_session_after_heavy(session, result, triggered=True)
            self._sessions.save(session)
            _sleep_seconds(self._config.watch_interval_seconds)
            return

        run_light = False
        light_reason = ""
        light_focus: list[str] | None = None
        if evaluation.promote == "light" and _light_cooldown_ok(session, self._config):
            run_light = True
            light_reason = "; ".join(evaluation.alerts[:2])
            # Alert symbols take up to half the batch; the rest continues the
            # universe rotation. With a large universe some ticker is almost
            # always alerting, so without this the rotation would starve and
            # non-held names would only ever be analyzed on alerts.
            half = max(1, self._config.batch_size // 2)
            alert_focus = (evaluation.light_symbols + evaluation.heavy_symbols)[:half]
            rotation, session.batch_cursor = next_speculative_batch(
                tickers,
                self._held_tickers() + alert_focus,
                session.batch_cursor,
                self._config.batch_size - len(alert_focus),
            )
            light_focus = list(dict.fromkeys(alert_focus + rotation))
        elif _should_run_scheduled_light(now, session, self._config) and _light_cooldown_ok(
            session, self._config
        ):
            run_light = True
            light_reason = "scheduled light refresh"
            light_focus, session.batch_cursor = next_speculative_batch(
                tickers, self._held_tickers(), session.batch_cursor, self._config.batch_size
            )

        if run_light:
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._base_inputs,
                kind="light",
                analysts=list(self._config.light_analysts),
                trigger_reason=light_reason or None,
                tickers=light_focus,
            )
            session.mark_light()
            self._sessions.save(session)
            print(f"\n{result.account_summary}")

        _sleep_seconds(self._config.watch_interval_seconds)

    def _maybe_run_eod_reports(self) -> None:
        """After the close, generate daily (+ weekly/monthly/yearly when the
        period ends) performance reports once per trading day."""
        if not self._config.eod_reports:
            return
        if not isinstance(self._broker, AlpacaBroker):
            return  # reports read fills/positions from the Alpaca API
        session = self._sessions.load()
        if session.trading_day != trading_date().isoformat() or session.eod_report_done:
            return
        if not (session.last_heavy_at or session.last_light_at):
            return  # nothing traded today (e.g. daemon started pre-open)
        if now_et().time() < SESSION_CLOSE:
            return

        # Mark first: a crash inside report generation must not re-run the
        # LLM advisory on every subsequent tick.
        session.eod_report_done = True
        self._sessions.save(session)
        try:
            from integrations.alpaca.reporting import run_end_of_day_reports

            print(f"\n{Fore.GREEN}{Style.BRIGHT}=== END-OF-DAY REPORTS ==={Style.RESET_ALL}")
            results = run_end_of_day_reports(
                model_name=self._config.heavy_model_name,
                model_provider=self._config.heavy_model_provider,
            )
            for report, path in results:
                print(f"  {report.period} report saved: {path}")
            if results:
                daily = results[0][0]
                print(f"\n{Fore.CYAN}Upgrade advisory (paste into Cursor):{Style.RESET_ALL}")
                print(daily.advisory)
        except Exception:
            logger.exception("End-of-day report generation failed")

    def _held_tickers(self) -> list[str]:
        try:
            return [p.ticker.upper() for p in self._broker.get_positions()]
        except Exception as exc:
            logger.warning("Could not fetch held positions: %s", exc)
            return []

    def _news_tickers(self, session: TradingSessionState) -> list[str]:
        """News checks cover holdings plus a rotating universe slice to
        respect Finnhub rate limits."""
        held = self._held_tickers()
        batch, session.news_cursor = next_speculative_batch(
            self._base_inputs.tickers, held, session.news_cursor, self._config.batch_size
        )
        return list(dict.fromkeys(held + batch))

    def _heavy_inputs(self) -> CycleInputs:
        return CycleInputs(
            tickers=self._base_inputs.tickers,
            start_date=self._base_inputs.start_date,
            end_date=self._base_inputs.end_date,
            show_reasoning=self._base_inputs.show_reasoning,
            selected_analysts=list(self._config.heavy_analysts),
            model_name=self._config.heavy_model_name,
            model_provider=self._config.heavy_model_provider,
            margin_requirement=self._base_inputs.margin_requirement,
            initial_cash=self._base_inputs.initial_cash,
            execute=self._base_inputs.execute,
            save_ledger=self._base_inputs.save_ledger,
        )

    def _sleep_until_closed(self) -> None:
        if isinstance(self._broker, AlpacaBroker):
            clock = self._broker.get_market_clock()
            if clock.next_open:
                try:
                    nxt = datetime.fromisoformat(clock.next_open.replace("Z", "+00:00"))
                    target = nxt.astimezone(now_et().tzinfo)
                    print(
                        f"{Fore.YELLOW}Market closed. Next open: "
                        f"{target.strftime('%Y-%m-%d %H:%M %Z')}{Style.RESET_ALL}"
                    )
                    _sleep_seconds((target - now_et()).total_seconds())
                    return
                except (TypeError, ValueError):
                    pass
        print(f"{Fore.YELLOW}Outside regular session. Waiting…{Style.RESET_ALL}")
        _sleep_seconds(self._config.watch_interval_seconds)


def run_daemon(
    broker_name: str,
    base_inputs: CycleInputs,
    config: SchedulerConfig | None = None,
) -> None:
    TradingDaemon(broker_name, base_inputs, config).run_forever()
