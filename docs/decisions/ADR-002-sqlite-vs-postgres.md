# ADR-002 — SQLite (single-file, SQLModel) over Postgres for run persistence

- **Status:** Accepted (2026-04-27)
- **Context:** Phase F1 — pick the run persistence engine.
- **Owners:** ltmas

## Problem

We need to persist runs, run events (for replay), per-ticker decisions, per-agent signals, and (Phase F3) backtest day rows. Workload is single-user analytical (one user, occasional concurrent runs). Read pattern is heavy on per-run replay.

## Options considered

| Option | Verdict |
|---|---|
| **SQLite + SQLModel + Alembic** | **Chosen.** Zero-ops, single file, sufficient concurrency for the expected workload (WAL mode), trivial backup (copy the file), perfect Docker volume story. SQLModel keeps Pydantic schemas as a single source of truth between API and DB. |
| Postgres + asyncpg | Better concurrency, mature tooling, full-text search — but adds a service to run/maintain, a Compose service, and a connection string. We do not need it yet at single-user scale. |
| MongoDB / DuckDB / direct JSON files | Either too schemaless (Mongo) or too analytical (DuckDB) for the OLTP-shaped run-event workload, or too unstructured (JSON files) to query for `/history`. |

## Decision

SQLite with WAL mode, SQLModel ORM, Alembic for migrations from day one. DB URL configurable via `AHF_DB_URL` (default `sqlite:///./data/runs.db`).

## Consequences

- Easy to upgrade to Postgres later: SQLModel is portable; Alembic migrations work on both. The migration path is documented in this ADR's "Migration to Postgres" appendix below.
- **No row-level concurrency for write-heavy backtests.** A long backtest writing per-day events while another run streams should be tested under WAL mode early in F3.
- Single-file backup means losing the file loses everything — F3 acceptance must include a documented backup/restore step.

## Migration to Postgres (when we need it)

1. `pip install asyncpg`
2. Set `AHF_DB_URL=postgresql+asyncpg://...`
3. Run existing Alembic migrations against the new database.
4. Migrate data with a one-shot `pgloader` or `sqlite3 .dump | psql` script (no Pydantic schema changes needed).

## References

- `/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md` §B4
- SQLModel docs: https://sqlmodel.tiangolo.com/
