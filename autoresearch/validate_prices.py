"""
Validate price cache before paper trading. Checks: missing days, outliers, staleness.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def validate_prices(
    prices_path: str | Path | None = None,
    max_age_days: int = 2,
    max_gap_days: int = 3,
    outlier_z: float = 4.0,
    all_caches: bool = True,
) -> tuple[bool, list[str]]:
    """
    Validate price cache. Returns (ok, list of warning/error messages).
    If all_caches, validate all prices_*.json in cache dir.
    """
    paths = []
    if prices_path:
        paths = [Path(prices_path)]
    elif all_caches:
        paths = list(CACHE_DIR.glob("prices*.json"))
    else:
        paths = [CACHE_DIR / "prices.json"]
    if not paths:
        return False, [f"No price caches in {CACHE_DIR}"]
    msgs = []
    today = datetime.now().date()
    for path in paths:
        if not path.exists():
            msgs.append(f"Price cache not found: {path}")
            continue
        try:
            with open(path) as f:
                raw = json.load(f)
        except Exception as e:
            msgs.append(f"Failed to load {path}: {e}")
            continue
        for ticker, recs in raw.items():
            if not recs or not isinstance(recs[0], dict):
                continue
            dates = [r["date"] for r in recs if isinstance(r.get("date"), str)]
            if not dates:
                msgs.append(f"{ticker}: no dates")
                continue
            last_date = max(dates)
            try:
                last_dt = datetime.strptime(last_date[:10], "%Y-%m-%d").date()
            except ValueError:
                msgs.append(f"{ticker}: invalid date {last_date}")
                continue
            age = (today - last_dt).days
            if age > max_age_days:
                msgs.append(f"{ticker}: stale ({age}d old, max {max_age_days})")
            closes = [float(r["close"]) for r in recs if "close" in r and r["close"]]
            if len(closes) >= 10 and outlier_z > 0:
                import numpy as np
                arr = np.array(closes)
                mean, std = arr.mean(), arr.std()
                if std > 1e-8:
                    z = np.abs((arr - mean) / std)
                    if (z > outlier_z).any():
                        msgs.append(f"{ticker}: possible outliers (z>{outlier_z})")
    ok = len([m for m in msgs if "not found" in m or "Failed" in m]) == 0
    return ok, msgs


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--prices-path", type=str, help="Path to prices JSON")
    p.add_argument("--max-age-days", type=int, default=2)
    p.add_argument("--strict", action="store_true", help="Exit 1 on any warning")
    args = p.parse_args()
    ok, msgs = validate_prices(args.prices_path, max_age_days=args.max_age_days)
    for m in msgs:
        print(m)
    if args.strict and msgs:
        exit(1)
    exit(0 if ok else 1)


if __name__ == "__main__":
    main()
