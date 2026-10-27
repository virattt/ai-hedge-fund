"""The ledger — a paper fund's append-only book of record.

One JSON file per session under ledger/, each SessionRecord carrying the
hash of the one before it. The fund's state (positions, cash, the pending
decision, the last session) is never stored on its own: it is rebuilt by
folding `next_state` over the chain, so there is nothing to drift. A gap,
a reordered file, or an edited record breaks the chain and `replay` refuses.

Layout, by cadence:

    ledger/2026-10-05.json                a daily fund's session
    ledger/2026-10-05/100500.json         a minute fund's 10:05:00 bar
    ledger/2026-10-05/checkpoint.json     the state after that day's last bar

A minute fund writes hundreds of records a day, so each day gets a
directory and, once it closes, a checkpoint: `replay` starts from the
newest checkpoint it can trust (its last session is still on the chain
with the hash it remembers) and folds forward from there. `replay(full=True)`
ignores checkpoints and verifies every link, as `aihf paper status --verify`
does. A checkpoint is a cache of the chain, never a substitute for it.

control.json is the kill switch. It is read into FundState.halted by
`replay`, and `advance` checks it first — so no client of the engine (CLI,
TUI, cron) can trade a halted fund by forgetting to look.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hedge_fund.data.bars import is_intraday, session_date
from hedge_fund.pipeline.session import FundState, next_state, SessionRecord
from hedge_fund.paths import write_atomic

LEDGER_SUBDIR = "ledger"
SUPERSEDED_SUBDIR = "superseded"  # records taken off the chain by a redo, kept
CHECKPOINT_FILE = "checkpoint.json"
CONTROL_FILE = "control.json"
EVENTS_FILE = "events.jsonl"

_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_BAR_FILE = re.compile(r"(\d{2})(\d{2})(\d{2})")


class LedgerError(RuntimeError):
    """The ledger is inconsistent, or an append would make it so."""


class Ledger:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.records_dir = self.directory / LEDGER_SUBDIR
        self.control_path = self.directory / CONTROL_FILE
        self.events_path = self.directory / EVENTS_FILE

    # ---- records ----------------------------------------------------------

    def init(self) -> None:
        """Create an empty ledger with the kill switch off."""
        self.records_dir.mkdir(parents=True, exist_ok=True)
        if not self.control_path.exists():
            write_atomic(self.control_path, json.dumps({"halted": False}, indent=2))

    def sessions(self) -> list[str]:
        """Every recorded session, daily and bar alike, in chain order."""
        if not self.records_dir.exists():
            return []
        found: list[str] = []
        for entry in self.records_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json" and _DAY.fullmatch(entry.stem):
                found.append(entry.stem)
            elif entry.is_dir() and _DAY.fullmatch(entry.name):
                for bar in entry.glob("*.json"):
                    match = _BAR_FILE.fullmatch(bar.stem)
                    if match:
                        found.append(f"{entry.name}T{':'.join(match.groups())}")
        return sorted(found)

    def days(self) -> list[str]:
        """The New York dates with at least one record, in order."""
        return sorted({session_date(s) for s in self.sessions()})

    def path(self, session: str) -> Path:
        if is_intraday(session):
            return self.records_dir / session_date(session) / f"{session[11:].replace(':', '')}.json"
        return self.records_dir / f"{session}.json"

    def read(self, session: str) -> SessionRecord:
        try:
            return SessionRecord.model_validate_json(self.path(session).read_text())
        except (OSError, ValueError) as exc:
            raise LedgerError(f"{self.path(session)}: cannot read session record: {exc}") from exc

    def records(self, *, since: str | None = None) -> list[SessionRecord]:
        """Every record in order; with *since*, only sessions at or after it."""
        return [self.read(s) for s in self.sessions() if since is None or s >= since]

    def latest(self) -> SessionRecord | None:
        sessions = self.sessions()
        return self.read(sessions[-1]) if sessions else None

    def append(self, record: SessionRecord) -> Path:
        """Append *record*, refusing a duplicate session, an out-of-order
        session, a broken hash chain, or a record whose hash is not its own."""
        path = self.path(record.session)
        if path.exists():
            raise LedgerError(f"{record.fund}: session {record.session} is already recorded")
        latest = self.latest()
        if latest is not None and record.session <= latest.session:
            raise LedgerError(
                f"{record.fund}: session {record.session} is not after the last "
                f"recorded session {latest.session}"
            )
        expected_prev = latest.hash if latest is not None else None
        if record.prev_hash != expected_prev:
            raise LedgerError(
                f"{record.fund}: session {record.session} does not chain to the "
                f"last recorded session ({latest.session if latest else 'none'})"
            )
        if record.hash != record.compute_hash():
            raise LedgerError(f"{record.fund}: session {record.session} hash does not match its contents")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, record.model_dump_json(indent=2))
        return path

    def rewind(self) -> SessionRecord:
        """Take the latest record off the chain so its session can be run
        again. The record is not destroyed: it moves to ledger/superseded/,
        named with its hash, where it no longer counts but can still be read.
        A checkpoint that remembered it is dropped. The broker's book is the
        caller's to restore."""
        latest = self.latest()
        if latest is None:
            raise LedgerError(f"{self.directory.name}: nothing recorded to rewind")
        keep = self.records_dir / SUPERSEDED_SUBDIR
        keep.mkdir(exist_ok=True)
        safe = latest.session.replace(":", "")
        self.path(latest.session).rename(keep / f"{safe}.{latest.hash[:12]}.json")
        checkpoint = self.checkpoint_path(session_date(latest.session))
        if checkpoint.exists():
            checkpoint.unlink()
        return latest

    def replay(self, capital: float, *, before: str | None = None, full: bool = False) -> FundState:
        """Fold the chain into the fund's current state, verifying every link
        it walks. With *before*, stop short of that session: the state the
        fund was in going into it. Starts from the newest trusted checkpoint
        before the stop unless *full*, which walks from the first record."""
        state = FundState.initial(capital)
        sessions = self.sessions()
        if not full:
            checkpoint = self._trusted_checkpoint(sessions, before)
            if checkpoint is not None:
                state = checkpoint
                sessions = [s for s in sessions if s > checkpoint.last_session]
        for session in sessions:
            if before is not None and session >= before:
                break
            record = self.read(session)
            if record.session != session:
                raise LedgerError(f"{self.path(session)}: file is named {session} but records {record.session}")
            if record.prev_hash != state.prev_hash:
                raise LedgerError(f"{record.fund}: chain broken at session {session}")
            if record.hash != record.compute_hash():
                raise LedgerError(f"{record.fund}: session {session} has been altered since it was written")
            state = next_state(state, record)
        return state.model_copy(update={"halted": self.halted()})

    # ---- checkpoints ------------------------------------------------------

    def checkpoint_path(self, day: str) -> Path:
        return self.records_dir / day / CHECKPOINT_FILE

    def checkpoint(self, state: FundState) -> Path:
        """Remember *state* as the state after its last session's day. Only a
        state whose last session is the newest recorded one can be kept:
        a checkpoint is a shortcut to the chain's head, not a fork."""
        if state.last_session is None or not is_intraday(state.last_session):
            raise LedgerError(f"{self.directory.name}: only a minute fund's day is checkpointed")
        latest = self.latest()
        if latest is None or latest.session != state.last_session or latest.hash != state.prev_hash:
            raise LedgerError(
                f"{self.directory.name}: checkpoint for {state.last_session} does not match the chain's head"
            )
        path = self.checkpoint_path(session_date(state.last_session))
        write_atomic(path, state.model_dump_json(exclude={"halted"}, indent=2))
        self.log_event("checkpoint", session=state.last_session)
        return path

    def _trusted_checkpoint(self, sessions: list[str], before: str | None) -> FundState | None:
        """The newest checkpoint whose last session is still on the chain with
        the hash it remembers, and which lies before *before*. Anything else
        is ignored, not an error: the chain is the truth, this is a cache."""
        if not self.records_dir.exists():
            return None
        recorded = set(sessions)
        days = sorted((p.parent.name for p in self.records_dir.glob(f"*/{CHECKPOINT_FILE}")), reverse=True)
        for day in days:
            if before is not None and day >= before[:10]:
                continue
            try:
                state = FundState.model_validate_json(self.checkpoint_path(day).read_text())
            except (OSError, ValueError):
                continue
            if state.last_session not in recorded or (before is not None and state.last_session >= before):
                continue
            try:
                head = self.read(state.last_session)
            except LedgerError:
                continue
            if head.hash == state.prev_hash and head.hash == head.compute_hash():
                return state
        return None

    # ---- the kill switch --------------------------------------------------

    def halted(self) -> str | None:
        """The halt reason, or None when the fund may trade."""
        if not self.control_path.exists():
            return None
        try:
            control = json.loads(self.control_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise LedgerError(f"{self.control_path}: cannot read the kill switch: {exc}") from exc
        if not control.get("halted"):
            return None
        return control.get("reason") or "halted"

    def halt(self, reason: str) -> None:
        self._write_control(True, reason)
        self.log_event("halt", reason=reason)

    def resume(self) -> None:
        self._write_control(False, None)
        self.log_event("resume")

    def _write_control(self, halted: bool, reason: str | None) -> None:
        write_atomic(self.control_path, json.dumps({
            "halted": halted, "reason": reason, "since": _now(),
        }, indent=2))

    # ---- events -----------------------------------------------------------

    def log_event(self, kind: str, **fields) -> None:
        line = json.dumps({"time": _now(), "kind": kind, **fields}, default=str)
        with self.events_path.open("a") as handle:
            handle.write(line + "\n")

    def events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines() if line.strip()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
