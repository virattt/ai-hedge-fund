"""Stock Snapshot — per-ticker live dashboard printed after every run."""
import json
import math
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from colorama import Fore, Style
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from tabulate import tabulate

from src.agents.technicals import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_rsi,
    safe_float,
)
from src.tools.api import get_insider_trades, get_prices, prices_to_df
from src.utils.llm import call_llm


class SnapshotNarrative(BaseModel):
    sentiment_line1: str = Field(description="First sentence of internet/news sentiment")
    sentiment_line2: str = Field(description="Second sentence on what could shift sentiment")
    ta_summary_line1: str = Field(description="First sentence of TA summary — trend structure")
    ta_summary_line2: str = Field(description="Second sentence — momentum and volume")
    ta_summary_line3: str = Field(description="Third sentence — what to watch next")


def _sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def _color(val: float, good_positive: bool = True) -> str:
    if val > 0:
        return Fore.GREEN if good_positive else Fore.RED
    elif val < 0:
        return Fore.RED if good_positive else Fore.GREEN
    return Fore.YELLOW


def _wrap(text: str, width: int = 68) -> str:
    words = text.split(); lines = []; cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n  ".join(lines)


def build_and_print_snapshots(
    tickers: list[str],
    result: dict,
    start_date: str,
    end_date: str,
    state: dict | None = None,
) -> dict:
    """
    Build a per-ticker live data snapshot and print it.
    Returns the snapshot dict for downstream validation.
    """
    api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
    analyst_signals = result.get("analyst_signals", {})
    snapshots: dict = {}

    for ticker in tickers:
        print(f"\n{Fore.WHITE}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}  LIVE STOCK SNAPSHOT — {ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")

        # ── Price data ──────────────────────────────────────────────────────
        prices = get_prices(ticker, start_date, end_date, api_key=api_key)
        if not prices:
            print(f"  {Fore.RED}No price data available.{Style.RESET_ALL}")
            continue

        df = prices_to_df(prices).copy()
        cur_price = float(df["close"].iloc[-1])

        def pct_change(n):
            idx = -min(n + 1, len(df))
            return (cur_price / float(df["close"].iloc[idx]) - 1) * 100

        chg_1m = pct_change(21)
        chg_3m = pct_change(63)
        chg_1y = pct_change(252)

        c1m = Fore.GREEN if chg_1m >= 0 else Fore.RED
        c3m = Fore.GREEN if chg_3m >= 0 else Fore.RED
        c1y = Fore.GREEN if chg_1y >= 0 else Fore.RED

        print(f"\n  {Fore.WHITE}{Style.BRIGHT}PRICE{Style.RESET_ALL}")
        print(f"  Current:  {Fore.WHITE}{Style.BRIGHT}${cur_price:,.2f}{Style.RESET_ALL}   "
              f"1M: {c1m}{chg_1m:+.2f}%{Style.RESET_ALL}   "
              f"3M: {c3m}{chg_3m:+.2f}%{Style.RESET_ALL}   "
              f"1Y: {c1y}{chg_1y:+.2f}%{Style.RESET_ALL}")

        # ── Technical Indicators ────────────────────────────────────────────
        rsi14 = calculate_rsi(df, 14)
        rsi_val = safe_float(rsi14.iloc[-1])

        macd_line, macd_sig = _macd(df["close"])
        macd_bull = safe_float(macd_line.iloc[-1]) > safe_float(macd_sig.iloc[-1])
        macd_str = f"{'BULLISH' if macd_bull else 'BEARISH'}"

        sma50 = safe_float(_sma(df["close"], 50).iloc[-1])
        sma200 = safe_float(_sma(df["close"], 200).iloc[-1])
        ma_signal = ("Golden Cross" if sma50 > sma200 else "Death Cross")
        ma_color = Fore.GREEN if sma50 > sma200 else Fore.RED

        vol_avg20 = float(df["volume"].rolling(20).mean().iloc[-1])
        vol_ratio = float(df["volume"].iloc[-1]) / max(vol_avg20, 1)

        atr14 = calculate_atr(df, 14)
        atr_pct = safe_float(atr14.iloc[-1]) / cur_price * 100

        bb_upper, bb_lower = calculate_bollinger_bands(df, 20)
        bb_pos = (cur_price - safe_float(bb_lower.iloc[-1])) / max(
            safe_float(bb_upper.iloc[-1]) - safe_float(bb_lower.iloc[-1]), 1e-10)

        window_252 = df.iloc[-252:] if len(df) >= 252 else df
        high_52w = float(window_252["high"].max())
        low_52w = float(window_252["low"].min())
        range_52w = (cur_price - low_52w) / max(high_52w - low_52w, 1e-10) * 100

        hist_vol = df["close"].pct_change().rolling(21).std() * math.sqrt(252)
        hvol_pct = safe_float(hist_vol.iloc[-1]) * 100

        rsi_color = (Fore.GREEN if rsi_val < 70 and rsi_val > 30 else
                     Fore.RED if rsi_val >= 70 else Fore.YELLOW)
        macd_color = Fore.GREEN if macd_bull else Fore.RED

        print(f"\n  {Fore.WHITE}{Style.BRIGHT}TECHNICAL INDICATORS{Style.RESET_ALL}")
        ta_rows = [
            ["RSI(14)", f"{rsi_color}{rsi_val:.1f}{Style.RESET_ALL}",
             "Overbought" if rsi_val >= 70 else "Oversold" if rsi_val <= 30 else "Neutral"],
            ["MACD(12/26/9)", f"{macd_color}{macd_str}{Style.RESET_ALL}", "Above signal" if macd_bull else "Below signal"],
            ["SMA 50 vs 200", f"{ma_color}{ma_signal}{Style.RESET_ALL}",
             f"50={sma50:.2f}  200={sma200:.2f}"],
            ["Volume Ratio", f"{Fore.GREEN if vol_ratio >= 1 else Fore.YELLOW}{vol_ratio:.2f}x{Style.RESET_ALL}",
             "Above avg" if vol_ratio >= 1.1 else "Below avg"],
            ["ATR%", f"{Fore.WHITE}{atr_pct:.2f}%{Style.RESET_ALL}", "Daily volatility"],
            ["BB Position", f"{Fore.WHITE}{bb_pos:.2f}{Style.RESET_ALL}",
             "Near upper" if bb_pos > 0.8 else "Near lower" if bb_pos < 0.2 else "Mid-range"],
            ["52W Range Pos", f"{Fore.WHITE}{range_52w:.1f}%{Style.RESET_ALL}",
             f"H={high_52w:.2f}  L={low_52w:.2f}"],
            ["Hist Vol (ann)", f"{Fore.WHITE}{hvol_pct:.1f}%{Style.RESET_ALL}", "21-day annualized"],
        ]
        print(tabulate(ta_rows, headers=["Indicator", "Value", "Notes"], tablefmt="simple",
                       colalign=("left", "right", "left")))

        # ── Insider Trades ──────────────────────────────────────────────────
        insider_data: dict = {}
        try:
            ins_end = end_date
            ins_start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=180)).strftime("%Y-%m-%d")
            trades = get_insider_trades(ticker, ins_end, ins_start, limit=50, api_key=api_key)
            if trades:
                buys = sum(1 for t in trades if getattr(t, "transaction_shares", 0) and
                           float(getattr(t, "transaction_shares", 0) or 0) > 0)
                sells = sum(1 for t in trades if getattr(t, "transaction_shares", 0) and
                            float(getattr(t, "transaction_shares", 0) or 0) < 0)
                net_shares = sum(float(getattr(t, "transaction_shares", 0) or 0) for t in trades)
                net_value = sum(float(getattr(t, "transaction_value", 0) or 0) for t in trades)

                # Most notable trade (by absolute value)
                sorted_trades = sorted(
                    [t for t in trades if getattr(t, "transaction_value", None)],
                    key=lambda t: abs(float(getattr(t, "transaction_value", 0) or 0)),
                    reverse=True,
                )
                notable = None
                if sorted_trades:
                    nt = sorted_trades[0]
                    notable = {
                        "name": getattr(nt, "owner_name", "Unknown"),
                        "title": getattr(nt, "owner_title", ""),
                        "shares": int(float(getattr(nt, "transaction_shares", 0) or 0)),
                        "value_usd": int(float(getattr(nt, "transaction_value", 0) or 0)),
                        "date": getattr(nt, "transaction_date", ""),
                    }

                insider_data = {
                    "buys_6m": buys, "sells_6m": sells,
                    "net_shares": int(net_shares), "net_value_usd": int(net_value),
                    "notable_trade": notable,
                }

                ins_color = Fore.GREEN if buys >= sells else Fore.RED
                ins_signal = "NET BUYING" if buys > sells else "NET SELLING" if sells > buys else "NEUTRAL"
                print(f"\n  {Fore.WHITE}{Style.BRIGHT}INSIDER ACTIVITY (last 6M){Style.RESET_ALL}")
                print(f"  {Fore.GREEN}{buys} Buys{Style.RESET_ALL}  /  {Fore.RED}{sells} Sells{Style.RESET_ALL}   "
                      f"Signal: {ins_color}{Style.BRIGHT}{ins_signal}{Style.RESET_ALL}")
                if net_value:
                    nv_color = Fore.GREEN if net_value > 0 else Fore.RED
                    print(f"  Net Value: {nv_color}${abs(net_value):,.0f}{Style.RESET_ALL} "
                          f"({'inflow' if net_value > 0 else 'outflow'})")
                if notable:
                    dir_str = "BOUGHT" if notable["shares"] > 0 else "SOLD"
                    print(f"  Notable: {notable['name']} ({notable['title']}) "
                          f"{dir_str} {abs(notable['shares']):,} shares "
                          f"(${abs(notable['value_usd']):,}) on {notable['date']}")
        except Exception:
            pass

        # ── Quant / FA metrics from FYI deep fundamental ───────────────────
        fyi_fa = analyst_signals.get("fyi_deep_fundamental_agent", {}).get(ticker, {})
        fa_metrics = fyi_fa.get("metrics", {})
        if fa_metrics:
            print(f"\n  {Fore.WHITE}{Style.BRIGHT}QUANT METRICS{Style.RESET_ALL}")
            quant_rows = []
            pio = fa_metrics.get("piotroski_f_score")
            az = fa_metrics.get("altman_z_score")
            az_zone = fa_metrics.get("altman_zone", "")
            sgr = fa_metrics.get("sustainable_growth_rate_pct")
            roe = fa_metrics.get("return_on_equity")
            roic = fa_metrics.get("return_on_invested_capital")
            ev_ebitda = fa_metrics.get("ev_to_ebitda")

            if pio:
                num = int(str(pio).split("/")[0])
                pio_color = Fore.GREEN if num >= 7 else Fore.RED if num <= 3 else Fore.YELLOW
                quant_rows.append(["Piotroski F-Score", f"{pio_color}{pio}{Style.RESET_ALL}", "Strong≥7 / Weak≤3"])
            if az is not None:
                az_color = Fore.GREEN if az > 2.99 else Fore.RED if az < 1.81 else Fore.YELLOW
                quant_rows.append(["Altman Z-Score", f"{az_color}{az:.2f}{Style.RESET_ALL}", az_zone])
            if roe is not None:
                roe_color = Fore.GREEN if roe > 0.15 else Fore.RED if roe < 0 else Fore.YELLOW
                quant_rows.append(["Return on Equity", f"{roe_color}{roe*100:.1f}%{Style.RESET_ALL}", ""])
            if roic is not None:
                roic_color = Fore.GREEN if roic > 0.10 else Fore.RED if roic < 0 else Fore.YELLOW
                quant_rows.append(["ROIC", f"{roic_color}{roic*100:.1f}%{Style.RESET_ALL}", ""])
            if sgr is not None:
                quant_rows.append(["Sustainable Growth", f"{Fore.WHITE}{sgr:.1f}%{Style.RESET_ALL}", ""])
            if ev_ebitda is not None:
                quant_rows.append(["EV/EBITDA", f"{Fore.WHITE}{ev_ebitda:.1f}x{Style.RESET_ALL}", ""])

            dupont = fa_metrics.get("dupont_analysis", {})
            if dupont.get("net_profit_margin") and dupont.get("asset_turnover"):
                quant_rows.append([
                    "DuPont (NM×AT×EM)",
                    f"{Fore.WHITE}{dupont['net_profit_margin']*100:.1f}%  ×  {dupont['asset_turnover']:.2f}  ×  {(dupont.get('equity_multiplier') or 1):.2f}{Style.RESET_ALL}",
                    f"= ROE {(dupont.get('roe_dupont_reconstructed') or 0)*100:.1f}%",
                ])
            if quant_rows:
                print(tabulate(quant_rows, headers=["Metric", "Value", "Notes"], tablefmt="simple",
                               colalign=("left", "right", "left")))

        # ── LLM narrative: sentiment + TA summary ──────────────────────────
        market_ctx = analyst_signals.get("fyi_market_context_agent", {}).get(ticker, {})
        fyi_ta = analyst_signals.get("fyi_deep_technical_agent", {}).get(ticker, {})

        news_headlines = []
        ns_agent = analyst_signals.get("news_sentiment_analyst_agent", {}).get(ticker, {})
        if isinstance(ns_agent.get("reasoning"), dict):
            for item in list(ns_agent["reasoning"].values())[:8]:
                if isinstance(item, str):
                    news_headlines.append(item)
        elif isinstance(ns_agent.get("reasoning"), str):
            news_headlines = [ns_agent["reasoning"][:400]]

        ta_metrics_str = json.dumps({
            "rsi_14": round(rsi_val, 1),
            "macd_signal": "bullish" if macd_bull else "bearish",
            "sma_50_vs_200": ma_signal,
            "bb_position": round(bb_pos, 2),
            "vol_ratio": round(vol_ratio, 2),
            "range_52w_pct": round(range_52w, 1),
            "deep_ta_summary": fyi_ta.get("summary", ""),
            "deep_ta_key_levels": fyi_ta.get("key_levels", ""),
            "deep_ta_pattern": fyi_ta.get("pattern_detected", ""),
        }, indent=2)

        template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a sharp equity analyst. Respond ONLY with a JSON object. "
             "No markdown, no explanation — raw JSON only. Schema:\n"
             '{{"sentiment_line1":"<1 sentence: broad market/analyst sentiment>","sentiment_line2":"<1 sentence: what could shift sentiment>",'
             '"ta_summary_line1":"<1 sentence: trend structure using deep_ta_summary>","ta_summary_line2":"<1 sentence: momentum and volume>",'
             '"ta_summary_line3":"<1 sentence: key levels and what to watch>"}}\n'
             "Use deep_ta_summary/key_levels/pattern for TA lines. Be specific with numbers."),
            ("human",
             "Ticker: {ticker}\nPrice: ${price}\n1M: {chg1m}%  1Y: {chg1y}%\n\n"
             "TA Metrics:\n{ta}\n\n"
             "Market Context: {ctx}\n\n"
             "News/Sentiment context: {news}"),
        ])

        prompt = template.invoke({
            "ticker": ticker,
            "price": f"{cur_price:,.2f}",
            "chg1m": f"{chg_1m:+.2f}",
            "chg1y": f"{chg_1y:+.2f}",
            "ta": ta_metrics_str,
            "ctx": (market_ctx.get("macro_theme") or market_ctx.get("reasoning") or "N/A"),
            "news": " | ".join(news_headlines[:4]) if news_headlines else "No news data",
        })

        narrative = call_llm(prompt=prompt, pydantic_model=SnapshotNarrative,
                             agent_name="snapshot", state=state)

        _err = "Error in analysis, using default"
        if narrative and narrative.sentiment_line1 != _err:
            print(f"\n  {Fore.WHITE}{Style.BRIGHT}MARKET SENTIMENT (Internet / Analyst Community){Style.RESET_ALL}")
            print(f"  {Fore.CYAN}{_wrap(narrative.sentiment_line1)}{Style.RESET_ALL}")
            if narrative.sentiment_line2 and narrative.sentiment_line2 != _err:
                print(f"  {Fore.CYAN}{_wrap(narrative.sentiment_line2)}{Style.RESET_ALL}")

            print(f"\n  {Fore.WHITE}{Style.BRIGHT}TECHNICAL ANALYSIS SUMMARY{Style.RESET_ALL}")
            if narrative.ta_summary_line1 and narrative.ta_summary_line1 != _err:
                print(f"  {Fore.WHITE}{_wrap(narrative.ta_summary_line1)}{Style.RESET_ALL}")
            if narrative.ta_summary_line2 and narrative.ta_summary_line2 != _err:
                print(f"  {Fore.WHITE}{_wrap(narrative.ta_summary_line2)}{Style.RESET_ALL}")
            if narrative.ta_summary_line3 and narrative.ta_summary_line3 != _err:
                print(f"  {Fore.WHITE}{_wrap(narrative.ta_summary_line3)}{Style.RESET_ALL}")

        # ── FYI agent summaries ─────────────────────────────────────────────
        print(f"\n  {Fore.WHITE}{Style.BRIGHT}FYI INTELLIGENCE STREAMS{Style.RESET_ALL}")
        fyi_rows = []
        for fyi_key, label in [
            ("fyi_market_context_agent", "Market Context"),
            ("fyi_deep_technical_agent", "Deep Technical"),
            ("fyi_deep_fundamental_agent", "Deep Fundamental"),
        ]:
            sig_data = analyst_signals.get(fyi_key, {}).get(ticker, {})
            if not sig_data:
                continue
            sig = sig_data.get("signal", "neutral").upper()
            conf = sig_data.get("confidence", 0)
            sig_color = {"BULLISH": Fore.GREEN, "BEARISH": Fore.RED, "NEUTRAL": Fore.YELLOW}.get(sig, Fore.WHITE)
            reasoning = sig_data.get("reasoning") or sig_data.get("summary", "")
            short_r = _wrap(reasoning[:200], 55) if reasoning else ""
            fyi_rows.append([
                f"{Fore.CYAN}{label}{Style.RESET_ALL}",
                f"{sig_color}{sig}{Style.RESET_ALL}",
                f"{Fore.WHITE}{conf}%{Style.RESET_ALL}",
                f"{Fore.WHITE}{short_r}{Style.RESET_ALL}",
            ])
        if fyi_rows:
            print(tabulate(fyi_rows, headers=["Stream", "Signal", "Conf", "Summary"],
                           tablefmt="simple", colalign=("left", "center", "right", "left")))

        print(f"\n{Fore.WHITE}{Style.BRIGHT}{'═' * 70}{Style.RESET_ALL}")

        # Build snapshot dict for validator
        snapshots[ticker] = {
            "price": cur_price,
            "change_1m_pct": round(chg_1m, 2),
            "change_3m_pct": round(chg_3m, 2),
            "change_1y_pct": round(chg_1y, 2),
            "rsi_14": round(rsi_val, 1),
            "macd_signal": "bullish" if macd_bull else "bearish",
            "sma_50": round(sma50, 2),
            "sma_200": round(sma200, 2),
            "ma_signal": ma_signal,
            "volume_ratio": round(vol_ratio, 2),
            "atr_pct": round(atr_pct, 2),
            "bb_position": round(bb_pos, 2),
            "range_52w_pct": round(range_52w, 1),
            "hist_vol_ann_pct": round(hvol_pct, 1),
            "insider_data": insider_data,
            "fa_metrics": {k: v for k, v in fa_metrics.items()
                           if not isinstance(v, dict) and v is not None},
            "fyi_market_context": market_ctx.get("reasoning", ""),
            "fyi_deep_technical_summary": fyi_ta.get("summary", ""),
            "fyi_deep_fundamental_summary": fyi_fa.get("summary", ""),
        }

    return snapshots
