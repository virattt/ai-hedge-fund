"""Prompt cache — one JSON file per LLM decision.

This is deliberately three things at once (a locked design decision):
1. a cache: a backtest re-running an agent over an unchanged snapshot costs $0;
2. the persistence record: the EXACT prompt + response behind every Signal,
   for replay and audit;
3. the debug trail: failed parses keep the raw response on disk.

Files live under .v2_cache/llm/ (gitignored), keyed by a hash of
(agent, model, prompt).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CACHE_DIR = Path(".v2_cache/llm")


def prompt_key(agent: str, model: str, system: str, user: str) -> str:
    """Cache key for one (agent, model, prompt) combination."""
    payload = f"{agent}|{model}|{system}|{user}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


class PromptCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self._dir = Path(cache_dir)

    def get(self, key: str) -> dict | None:
        path = self._dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None  # corrupt cache entry -> treat as miss, will be rewritten

    def put(self, key: str, record: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        record = {**record, "created_at": datetime.now(timezone.utc).isoformat()}
        path = self._dir / f"{key}.json"
        path.write_text(json.dumps(record, indent=2))
