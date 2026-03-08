"""Load SOUL.md thesis and build injection strings for agent prompts."""

from pathlib import Path


def _shared_config_dir() -> Path:
    return Path.home() / ".ai-hedge-fund"


def _default_thesis_search_paths() -> list[Path]:
    cwd = Path.cwd()
    return [
        cwd / "SOUL.md",
        _shared_config_dir() / "SOUL.md",
    ]


def load_thesis(path: str | Path | None = None) -> str:
    """
    Load thesis text from SOUL.md. Search order:
    1. path (if provided, e.g. from --thesis)
    2. ./SOUL.md (repo root)
    3. ~/.ai-hedge-fund/SOUL.md (shared config)
    Returns empty string if no file found.
    """
    if path is not None:
        p = Path(path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").strip()
        return ""

    for p in _default_thesis_search_paths():
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def thesis_injection_for_prompt(thesis_context: str) -> str:
    """
    Build the thesis context block to append to an agent's system message.
    Returns the full string with thesis interpolated, or empty string if no thesis.
    """
    if not (thesis_context and thesis_context.strip()):
        return ""
    return """

## Portfolio Thesis Context
The following is the portfolio manager's structural thesis. Use it to contextualize your analysis: where does this ticker sit in the thesis? Does the data support or contradict the thesis? Flag any thesis-relevant insights.

""" + thesis_context.strip()


def load_portfolio_targets(path: str | Path | None = None) -> dict:
    """
    Load target portfolio allocations from PORTFOLIO.md (optional, for future use).
    Returns empty dict if file not found or not yet implemented.
    """
    if path is not None:
        p = Path(path)
        if p.exists() and p.is_file():
            # Future: parse PORTFOLIO.md (ticker, weight, layer, tier)
            return {}
    if (_shared_config_dir() / "PORTFOLIO.md").exists():
        return {}
    return {}
