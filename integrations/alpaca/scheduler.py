"""Market-hours daemon: heavy LLM at open, light refresh every N minutes, event triggers."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from colorama import Fore, Style, init

from integrations.alpaca.broker import AlpacaBroker
from integrations.alpaca.light_cycle import fetch_spy_price, snapshot_reference_prices
from integrations.alpaca.market_hours import (
    is_regular_session,
    next_light_tick,
    now_et,
    session_open_datetime,
    trading_date,
)
from integrations.alpaca.run_cycle import CycleInputs, CycleResult, create_broker, run_cycle
from integrations.alpaca.session import SessionStore, TradingSessionState
from integrations.alpaca.strategy import CycleKind, SchedulerConfig, load_scheduler_config
from integrations.alpaca.triggers import TriggerMonitor

init(autoreset=True)
logger = logging.getLogger(__name__)


def _sleep_until(target: datetime) -> None:
    seconds = (target - now_et()).total_seconds()
    if seconds > 0:
        logger.info("Sleeping %.0fs until %s ET", seconds, target.strftime("%H:%M:%S"))
        time.sleep(seconds)


def _analysis_dates() -> tuple[str, str]:
    end = trading_date().isoformat()
    start = (trading_date() - timedelta(days=90)).isoformat()
    return start, end


def _should_run_heavy_open(now: datetime, session: TradingSessionState, config: SchedulerConfig) -> bool:
    if session.heavy_open_completed:
        return False
    open_at = session_open_datetime(now.date(), delay_minutes=config.open_delay_minutes)
    return now >= open_at


def _should_run_light(
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


def _print_cycle_banner(kind: CycleKind, trigger_reason: str | None = None) -> None:
    label = kind.upper().replace("_", " ")
    color = Fore.MAGENTA if kind == "heavy" else Fore.CYAN if kind == "light" else Fore.YELLOW
    print(f"\n{color}{Style.BRIGHT}=== {label} CYCLE ==={Style.RESET_ALL}")
    if trigger_reason:
        print(f"{Fore.YELLOW}Trigger: {trigger_reason}{Style.RESET_ALL}")


def run_scheduled_cycle(
    broker_name: str,
    *,
    base_inputs: CycleInputs,
    kind: CycleKind,
    analysts: list[str],
    trigger_reason: str | None = None,
) -> CycleResult:
    _print_cycle_banner(kind, trigger_reason)
    start_date, end_date = _analysis_dates()
    inputs = CycleInputs(
        tickers=base_inputs.tickers,
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
    """Runs heavy-at-open + light refresh + trigger-promoted heavy cycles."""

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
        self._triggers = TriggerMonitor(self._config)
        self._broker, self._alpaca_config = create_broker(
            broker_name,
            initial_cash=base_inputs.initial_cash,
            margin_requirement=base_inputs.margin_requirement,
            execute=base_inputs.execute,
        )

    def run_forever(self) -> None:
        print(f"{Fore.GREEN}{Style.BRIGHT}Trading daemon started (US equities).{Style.RESET_ALL}")
        print(
            f"Heavy: {self._config.open_delay_minutes}m after 9:30 ET | "
            f"Light: every {self._config.light_interval_minutes}m | "
            f"Model: {self._config.heavy_model_provider}/{self._config.heavy_model_name}"
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
                logger.exception("Daemon tick failed — retrying in 60s")
                time.sleep(60)

    def _market_open(self) -> bool:
        if isinstance(self._broker, AlpacaBroker):
            return self._broker.is_market_open()
        return is_regular_session()

    def _tick(self) -> None:
        now = now_et()
        if not self._market_open():
            self._sleep_until_closed()
            return

        session = self._sessions.load()
        if session.trading_day != trading_date().isoformat():
            session = session.for_today()

        tickers = self._base_inputs.tickers

        if _should_run_heavy_open(now, session, self._config):
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._heavy_inputs(),
                kind="heavy",
                analysts=list(self._config.heavy_analysts),
            )
            _update_session_after_heavy(session, result, triggered=False)
            self._sessions.save(session)
            return

        evaluation = self._triggers.evaluate(tickers, session)
        if evaluation.fired:
            reason = "; ".join(evaluation.reasons[:3])
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._heavy_inputs(),
                kind="triggered_heavy",
                analysts=list(self._config.heavy_analysts),
                trigger_reason=reason,
            )
            _update_session_after_heavy(session, result, triggered=True)
            self._sessions.save(session)
            return

        if _should_run_light(now, session, self._config):
            result = run_scheduled_cycle(
                self._broker_name,
                base_inputs=self._base_inputs,
                kind="light",
                analysts=list(self._config.light_analysts),
            )
            session.mark_light()
            self._sessions.save(session)
            print(f"\n{result.account_summary}")
            return

        self._sleep_until_next_slot(now, session)

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
                    print(f"{Fore.YELLOW}Market closed. Next open: {target.strftime('%Y-%m-%d %H:%M %Z')}{Style.RESET_ALL}")
                    _sleep_until(target)
                    return
                except (TypeError, ValueError):
                    pass
        target = next_light_tick(now_et(), self._config.light_interval_minutes)
        print(f"{Fore.YELLOW}Outside regular session. Waiting…{Style.RESET_ALL}")
        _sleep_until(target)

    def _sleep_until_next_slot(self, now: datetime, session: TradingSessionState) -> None:
        target = next_light_tick(now, self._config.light_interval_minutes)
        _sleep_until(target)


def run_daemon(
    broker_name: str,
    base_inputs: CycleInputs,
    config: SchedulerConfig | None = None,
) -> None:
    TradingDaemon(broker_name, base_inputs, config).run_forever()
