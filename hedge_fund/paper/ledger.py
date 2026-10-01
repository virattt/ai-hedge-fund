"""The ledger — a paper fund's append-only book of record.

One JSON file per session under ledger/, each SessionRecord carrying the
hash of the one before it. The fund's state (positions, cash, the pending
decision, the last session) is never stored on its own: it is rebuilt by
folding `next_state` over the chain, so there is nothing to drift. A gap,
a reordered file, or an edited record breaks the chain and `replay` refuses.

control.json is the kill switch. It is read into FundState.halted by
`replay`, and `advance` checks it first — so no client of the engine (CLI,
TUI, cron) can trade a halted fund by forgetting to look.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from hedge_fund.pipeline.session import FundState, next_state, SessionRecord
from hedge_fund.paths import write_atomic

LEDGER_SUBDIR = "ledger"
SUPERSEDED_SUBDIR = "superseded"  # records taken off the chain by a redo, kept
CONTROL_FILE = "control.json"
EVENTS_FILE = "events.jsonl"


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
        if not self.records_dir.exists():
            return []
        return sorted(p.stem for p in self.records_dir.glob("*.json"))

    def path(self, session: str) -> Path:
        return self.records_dir / f"{session}.json"

    def read(self, session: str) -> SessionRecord:
        try:
            return SessionRecord.model_validate_json(self.path(session).read_text())
        except (OSError, ValueError) as exc:
            raise LedgerError(f"{self.path(session)}: cannot read session record: {exc}") from exc

    def records(self) -> list[SessionRecord]:
        return [self.read(session) for session in self.sessions()]

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
        self.records_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(path, record.model_dump_json(indent=2))
        return path

    def rewind(self) -> SessionRecord:
        """Take the latest record off the chain so its session can be run
        again. The record is not destroyed: it moves to ledger/superseded/,
        named with its hash, where it no longer counts but can still be read.
        The broker's book is the caller's to restore."""
        latest = self.latest()
        if latest is None:
            raise LedgerError(f"{self.directory.name}: nothing recorded to rewind")
        keep = self.records_dir / SUPERSEDED_SUBDIR
        keep.mkdir(exist_ok=True)
        self.path(latest.session).rename(keep / f"{latest.session}.{latest.hash[:12]}.json")
        return latest

    def replay(self, capital: float, *, before: str | None = None) -> FundState:
        """Fold the chain into the fund's current state, verifying every link.
        With *before*, stop short of that session: the state the fund was in
        going into it."""
        state = FundState.initial(capital)
        for session in self.sessions():
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
