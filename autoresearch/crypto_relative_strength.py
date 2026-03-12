"""
autoresearch/crypto_relative_strength.py

Show HYPE and SOL relative strength vs BTC (benchmark).
Returns and alpha over configurable windows; optional Renko regime on HYPE/BTC and SOL/BTC ratios.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autoresearch.renko_bbwas import renko_regime_mtf

CACHE_DIR = Path(__file__).resolve().parent / "cache"

# ANSI
R = "\033[0m"
B = "\033[1m"
G = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
CYAN = "\033[36m"


def _g(s: str) -> str:
    return f"{G}{s}{R}" if os.environ.get("TERM") and "color" in os.environ.get("TERM", "") else s


def _r(s: str) -> str:
    return f"{RED}{s}{R}" if os.environ.get("TERM") and "color" in os.environ.get("TERM", "") else s


def _fmt_alpha(v: float) -> str:
    s = f"{v:+.2f}%"
    return _g(s) if v > 0 else (_r(s) if v < 0 else f"{DIM}{s}{R}")


def _fmt_ret(v: float) -> str:
    s = f"{v:+.2f}%"
    return _g(s) if v > 0 else (_r(s) if v < 0 else s)


BANNER = r"""
     ═══════════════════════════════════════════════════════════════════════
     ║                                                                      ║
     ║     ██████╗ ███████╗██╗     ██╗      ███████╗████████╗███████╗██████╗   ║
     ║     ██╔══██╗██╔════╝██║     ██║      ██╔════╝╚══██╔══╝██╔════╝██╔══██╗  ║
     ║     ██████╔╝█████╗  ██║     ██║█████╗█████╗     ██║   █████╗  ██████╔╝  ║
     ║     ██╔══██╗██╔══╝  ██║     ██║╚════╝██╔══╝     ██║   ██╔══╝  ██╔══██╗  ║
     ║     ██║  ██║███████╗███████╗███████╗  ███████╗   ██║   ███████╗██║  ██║  ║
     ║     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝  ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝  ║
     ║                                                                      ║
     ║     ███████╗████████╗██████╗ ███████╗███╗   ██╗ ██████╗████████╗██╗  ██╗ ║
     ║     ██╔════╝╚══██╔══╝██╔══██╗██╔════╝████╗  ██║██╔════╝╚══██╔══╝██║  ██║ ║
     ║     ███████╗   ██║   ██████╔╝█████╗  ██╔██╗ ██║██║        ██║   ██║  ██║ ║
     ║     ╚════██║   ██║   ██╔══██╗██╔══╝  ██║╚██╗██║██║        ██║   ██║  ██║ ║
     ║     ███████║   ██║   ██║  ██║███████╗██║ ╚████║╚██████╗   ██║   ╚██████╔╝ ║
     ║     ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝   ╚═╝    ╚═════╝  ║
     ║                                                                      ║
     ║                                                                      ║
     ║         The benchmark.  No substitute.                               ║
     ║                                                                      ║
     ║         "The only measure that matters is beating it."               ║
     ║                                                                      ║
     ║         Simple.  Powerful.  Different.                               ║
     ║                                                                      ║
     ═══════════════════════════════════════════════════════════════════════
"""


def load_ohlc(ticker: str) -> pd.DataFrame:
    path = CACHE_DIR / f"prices_{ticker.lower()}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run data refresh from CRYPTO.md section 2.")
    raw = json.loads(path.read_text())
    if ticker not in raw or not raw[ticker]:
        raise ValueError(f"No data for {ticker} in {path}")
    df = pd.DataFrame(raw[ticker])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def build_ratio_ohlc(numer_df: pd.DataFrame, denom_df: pd.DataFrame) -> pd.DataFrame:
    common = numer_df.index.intersection(denom_df.index)
    a = numer_df.loc[common]
    b = denom_df.loc[common]
    ratio = pd.DataFrame(index=common)
    ratio["open"] = a["open"] / b["open"]
    ratio["high"] = a["high"] / b["low"].replace(0, pd.NA)
    ratio["low"] = a["low"] / b["high"].replace(0, pd.NA)
    ratio["close"] = a["close"] / b["close"].replace(0, pd.NA)
    ratio["volume"] = a["volume"]
    return ratio.dropna()


def main():
    parser = argparse.ArgumentParser(description="Relative strength vs BTC")
    parser.add_argument("--windows", type=int, nargs="+", default=[5, 21, 63, 252],
                        help="Return windows in days (default: 5 21 63 252)")
    parser.add_argument("--renko", action="store_true", help="Show Renko regime on HYPE/BTC and SOL/BTC ratios")
    parser.add_argument("--compact", action="store_true", help="Minimal output, no banner")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--atr-mult-fast", type=float, default=1.0)
    parser.add_argument("--atr-mult-slow", type=float, default=2.0)
    args = parser.parse_args()

    if args.no_color:
        os.environ["TERM"] = ""

    btc = load_ohlc("BTC")
    sol = load_ohlc("SOL")
    hype = load_ohlc("HYPE")

    common = btc.index.intersection(sol.index).intersection(hype.index)
    btc = btc.loc[common]
    sol = sol.loc[common]
    hype = hype.loc[common]

    close = pd.DataFrame({"BTC": btc["close"], "SOL": sol["close"], "HYPE": hype["close"]}).dropna()
    if len(close) < max(args.windows) + 1:
        print(f"Need at least {max(args.windows) + 1} days; have {len(close)}")
        sys.exit(1)

    last = close.index[-1]

    if not args.compact:
        print(BANNER)
        print(f"  {DIM}As of {last.date()}{R}\n")

    # Table
    print("  ╭──────────┬────────────┬────────────┬────────────┬──────────┬──────────╮")
    print(f"  │ {'Window':<8} │ {'BTC':>10} │ {'SOL':>10} │ {'HYPE':>10} │ {'SOL α':>8} │ {'HYPE α':>8} │")
    print("  ├──────────┼────────────┼────────────┼────────────┼──────────┼──────────┤")

    for w in args.windows:
        if len(close) < w + 1:
            continue
        ret_btc = (close["BTC"].iloc[-1] / close["BTC"].iloc[-w - 1] - 1) * 100
        ret_sol = (close["SOL"].iloc[-1] / close["SOL"].iloc[-w - 1] - 1) * 100
        ret_hype = (close["HYPE"].iloc[-1] / close["HYPE"].iloc[-w - 1] - 1) * 100
        alpha_sol = ret_sol - ret_btc
        alpha_hype = ret_hype - ret_btc
        label = f"{w}d" if w < 365 else f"{w//252}y"
        r_btc = _fmt_ret(ret_btc)
        r_sol = _fmt_ret(ret_sol)
        r_hype = _fmt_ret(ret_hype)
        a_sol = _fmt_alpha(alpha_sol)
        a_hype = _fmt_alpha(alpha_hype)
        print(f"  │ {label:<8} │ {r_btc:>10} │ {r_sol:>10} │ {r_hype:>10} │ {a_sol:>8} │ {a_hype:>8} │")

    print("  ╰──────────┴────────────┴────────────┴────────────┴──────────┴──────────╯")
    print(f"\n  {DIM}α = alpha vs BTC  │  positive = outperforming the benchmark{R}\n")

    if args.renko:
        hype_btc = build_ratio_ohlc(hype, btc)
        sol_btc = build_ratio_ohlc(sol, btc)
        sig_h = renko_regime_mtf("HYPE/BTC", args.atr_mult_fast, args.atr_mult_slow, require_agreement=True, ohlc_df=hype_btc)
        sig_s = renko_regime_mtf("SOL/BTC", args.atr_mult_fast, args.atr_mult_slow, require_agreement=True, ohlc_df=sol_btc)
        print("  ┌─────────────────────────────────────────────────────────────────────┐")
        print("  │  R E N K O   R E G I M E   ·   R A T I O   V S   B T C              │")
        print("  │  " + "─" * 65 + " │")
        print("  │  Precision.  No noise.  Just the signal.                            │")
        print("  ├─────────────────────────────────────────────────────────────────────┤")
        print(f"  │  HYPE/BTC  {B}{sig_h.get('direction', '?'):<12}{R}  conf {sig_h.get('confidence', 0):.0%}   scale {sig_h.get('scale', 0):.2f}  │")
        print(f"  │  SOL/BTC   {B}{sig_s.get('direction', '?'):<12}{R}  conf {sig_s.get('confidence', 0):.0%}   scale {sig_s.get('scale', 0):.2f}  │")
        print("  ├─────────────────────────────────────────────────────────────────────┤")
        print(f"  │  {DIM}bull = outperforming  │  bear = underperforming  │  neutral = mixed{R}  │")
        print("  └─────────────────────────────────────────────────────────────────────┘")


if __name__ == "__main__":
    main()
