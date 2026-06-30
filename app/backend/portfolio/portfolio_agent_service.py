"""Portfolio Agent Service — orchestrates hedge-fund agents on user holdings.

Loads holdings from DB, normalizes tickers, calls existing AI agents,
synthesizes educational action labels, and stores results.
"""

import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.backend.database.models import Holding, Watchlist, PortfolioAnalysisResult
from app.backend.portfolio.ticker_normalizer import normalize_ticker
from app.backend.portfolio.action_rules import determine_educational_action
from app.backend.services.api_key_service import ApiKeyService


class ApiKeyMissingError(Exception):
    """Raised when a required API key is not configured."""
    def __init__(self, provider: str, env_var: str):
        self.provider = provider
        self.env_var = env_var
        super().__init__(
            f"{provider} API key not configured. "
            f"Set {env_var} in .env file or add it via Settings > API Keys."
        )

logger = logging.getLogger(__name__)


def run_portfolio_analysis(
    db: Session,
    holding_ids: Optional[list[int]] = None,
    watchlist_ids: Optional[list[int]] = None,
    model_name: str = "gpt-4o-mini",
    model_provider: str = "OpenAI",
    analysis_mode: str = "quick_scan",
) -> list[dict]:
    """Run analysis pipeline on holdings and/or watchlist items.

    Modes:
    - quick_scan: Local indicators only, no LLM calls (zero tokens).
    - standard: 4 core agents (technical, fundamental, sentiment, valuation).
    - deep_dive: All 18+ agents (full multi-agent pipeline).
    """
    from app.backend.portfolio.analysis_modes import AnalysisMode, TIER_AGENTS, TIER_MODELS

    mode = AnalysisMode(analysis_mode) if analysis_mode in [m.value for m in AnalysisMode] else AnalysisMode.QUICK_SCAN

    # Resolve model: mode defaults can be overridden by explicit request
    effective_model = model_name
    effective_provider = model_provider
    tier_defaults = TIER_MODELS.get(mode, {})
    if model_name == "gpt-4o-mini" and mode == AnalysisMode.DEEP_DIVE:
        effective_model = tier_defaults.get("model_name", "gpt-4.1")
        effective_provider = tier_defaults.get("model_provider", "OpenAI")

    # Gather API keys from database
    api_key_service = ApiKeyService(db)
    api_keys = api_key_service.get_api_keys_dict()

    # Set env vars for agents that read from environment
    for key, value in api_keys.items():
        if value:
            os.environ[key] = value

    # Pre-flight: validate API key only if we need LLM agents
    if mode != AnalysisMode.QUICK_SCAN:
        provider_env_map = {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "Groq": "GROQ_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
            "Google": "GOOGLE_API_KEY",
        }
        required_env_var = provider_env_map.get(effective_provider)
        if required_env_var and not os.environ.get(required_env_var):
            logger.error(
                f"API key missing: {required_env_var} not found in environment or database. "
                f"Provider={effective_provider}, Model={effective_model}"
            )
            raise ApiKeyMissingError(provider=effective_provider, env_var=required_env_var)

    # Collect items to analyze
    items_to_analyze: list[dict] = []

    if holding_ids:
        holdings = db.query(Holding).filter(Holding.id.in_(holding_ids)).all()
        for h in holdings:
            items_to_analyze.append({
                "holding_id": h.id,
                "watchlist_id": None,
                "broker_ticker": h.ticker,
                "investment_name": h.investment_name,
            })
    elif not watchlist_ids:
        holdings = db.query(Holding).all()
        for h in holdings:
            items_to_analyze.append({
                "holding_id": h.id,
                "watchlist_id": None,
                "broker_ticker": h.ticker,
                "investment_name": h.investment_name,
            })

    if watchlist_ids:
        watchlist_items = db.query(Watchlist).filter(Watchlist.id.in_(watchlist_ids)).all()
        for w in watchlist_items:
            items_to_analyze.append({
                "holding_id": None,
                "watchlist_id": w.id,
                "broker_ticker": w.ticker,
                "investment_name": w.investment_name or w.ticker,
            })

    # Group by normalized ticker (avoid duplicate API calls)
    us_ticker_groups: dict[str, list[dict]] = {}
    lse_ticker_groups: dict[str, list[dict]] = {}
    unsupported_items: list[dict] = []

    for item in items_to_analyze:
        analysis_ticker, supported = normalize_ticker(item["broker_ticker"])
        item["analysis_ticker"] = analysis_ticker
        item["supported"] = supported

        if not supported:
            unsupported_items.append(item)
        elif analysis_ticker.upper().endswith(".L"):
            lse_ticker_groups.setdefault(analysis_ticker, []).append(item)
        else:
            us_ticker_groups.setdefault(analysis_ticker, []).append(item)

    results: list[dict] = []

    # Handle unsupported tickers
    for item in unsupported_items:
        result = _create_unsupported_result(db, item)
        results.append(result)

    # All modes: LSE tickers always use lightweight provider-based analysis (no LLM)
    if lse_ticker_groups:
        for ticker, items in lse_ticker_groups.items():
            try:
                lse_results = _analyze_via_providers(db, ticker, items, api_keys)
                results.extend(lse_results)
            except Exception as e:
                logger.error(f"Provider analysis failed for {ticker}: {e}")
                for item in items:
                    results.append(_create_error_result(db, item, str(e)))

    # US tickers: route based on analysis mode
    us_tickers = list(us_ticker_groups.keys())

    if us_tickers:
        if mode == AnalysisMode.QUICK_SCAN:
            # No LLM calls — use the same provider-based path as LSE tickers
            for ticker, items in us_ticker_groups.items():
                try:
                    us_results = _analyze_via_providers(db, ticker, items, api_keys)
                    results.extend(us_results)
                except Exception as e:
                    logger.error(f"Quick scan failed for {ticker}: {e}")
                    for item in items:
                        results.append(_create_error_result(db, item, str(e)))
        else:
            # STANDARD or DEEP_DIVE: run LLM agent pipeline
            from src.main import run_hedge_fund

            selected_analysts = TIER_AGENTS.get(mode)
            # Empty list means all agents (deep dive)
            if selected_analysts is not None and len(selected_analysts) == 0:
                selected_analysts = None

            portfolio = {
                "cash": 100000.0,
                "margin_requirement": 0.0,
                "margin_used": 0.0,
                "positions": {t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0} for t in us_tickers},
                "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in us_tickers},
            }

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            try:
                agent_result = run_hedge_fund(
                    tickers=us_tickers,
                    start_date=start_date,
                    end_date=end_date,
                    portfolio=portfolio,
                    show_reasoning=False,
                    selected_analysts=selected_analysts,
                    model_name=effective_model,
                    model_provider=effective_provider,
                )

                analyst_signals = agent_result.get("analyst_signals", {})
                decisions = agent_result.get("decisions", {})

                for ticker, items in us_ticker_groups.items():
                    ticker_result = _process_ticker_result(
                        db, ticker, items, analyst_signals, decisions
                    )
                    results.extend(ticker_result)

            except Exception as e:
                logger.error(f"Agent pipeline failed: {e}\n{traceback.format_exc()}")
                for ticker, items in us_ticker_groups.items():
                    for item in items:
                        result = _create_error_result(db, item, str(e))
                        results.append(result)

    return results


def _analyze_via_providers(
    db: Session,
    ticker: str,
    items: list[dict],
    api_keys: dict,
) -> list[dict]:
    """Lightweight analysis for LSE/international tickers via provider layer.

    Uses Yahoo Finance for prices, fundamentals, and news. Computes technical
    indicators locally and generates a probabilistic outlook.
    """
    import numpy as np
    import pandas as pd
    from app.backend.data_providers import ProviderManager, DataAvailability
    from app.backend.portfolio.outlook import compute_outlook

    manager = ProviderManager(api_keys=api_keys)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    # --- Fetch data ---
    price_result = manager.get_prices(ticker, start_date, end_date)
    fundamental_result = manager.get_fundamentals(ticker)
    sentiment_result = manager.get_sentiment(ticker)

    # --- Technical analysis from prices ---
    technical_signal = None
    technical_confidence = None
    rsi_14 = None
    trend = None
    annualized_volatility = None

    # Set failure-specific default summaries
    if price_result.availability == DataAvailability.PROVIDER_ERROR:
        technical_summary = f"Price data fetch failed ({price_result.error_message or 'provider error'}). Technical analysis unavailable."
    elif price_result.availability == DataAvailability.NO_DATA:
        technical_summary = "No price history found for this ticker. Technical analysis unavailable."
    elif price_result.availability == DataAvailability.RATE_LIMITED:
        technical_summary = "Data provider rate limited. Try again shortly."
    else:
        technical_summary = "Price data not available for technical analysis."

    if price_result.availability == DataAvailability.AVAILABLE and price_result.data:
        bars = price_result.data
        if len(bars) >= 14:
            closes = pd.Series([b.close for b in bars])

            # RSI
            delta = closes.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta.where(delta < 0, 0.0))
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi_val = rsi_series.iloc[-1]
            if not pd.isna(rsi_val):
                rsi_14 = float(rsi_val)

            # SMAs and trend
            current_price = float(closes.iloc[-1])
            sma_20 = float(closes.rolling(20).mean().iloc[-1]) if len(closes) >= 20 else None
            sma_50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else None

            if sma_20 and sma_50:
                if current_price > sma_20 > sma_50:
                    trend = "up"
                elif current_price < sma_20 < sma_50:
                    trend = "down"
                else:
                    trend = "sideways"
            elif sma_20:
                trend = "up" if current_price > sma_20 else "down"
            else:
                trend = "sideways"

            # Volatility
            daily_returns = closes.pct_change().dropna()
            if len(daily_returns) > 5:
                annualized_volatility = float(daily_returns.std() * np.sqrt(252))

            # Determine technical signal (dead zone: RSI 40-60 is neutral)
            bullish_points = 0
            bearish_points = 0
            if trend == "up":
                bullish_points += 1
            elif trend == "down":
                bearish_points += 1
            if rsi_14 and rsi_14 > 60:
                bullish_points += 1
            elif rsi_14 and rsi_14 < 40:
                bearish_points += 1

            if bullish_points > bearish_points:
                technical_signal = "bullish"
            elif bearish_points > bullish_points:
                technical_signal = "bearish"
            else:
                technical_signal = "neutral"

            technical_confidence = 60.0 if abs(bullish_points - bearish_points) > 1 else 45.0

            # Build readable summary
            rsi_desc = f"RSI(14) at {rsi_14:.0f}" if rsi_14 else "RSI not available"
            trend_desc = {"up": "positive", "down": "negative", "sideways": "sideways"}.get(trend, "unknown")
            technical_summary = (
                f"Technical outlook is {'positive' if technical_signal == 'bullish' else 'negative' if technical_signal == 'bearish' else 'neutral'} "
                f"with {technical_confidence:.0f}% confidence. "
                f"Price trend is {trend_desc}. {rsi_desc}."
            )

    # --- Fundamental analysis ---
    fundamental_signal = None
    fundamental_confidence = None
    if fundamental_result.availability == DataAvailability.PROVIDER_ERROR:
        fundamental_summary = f"Fundamental data fetch failed ({fundamental_result.error_message or 'provider error'})."
    elif fundamental_result.availability == DataAvailability.NO_DATA:
        fundamental_summary = "No fundamental data available for this instrument (may be an ETF or fund)."
    else:
        fundamental_summary = "Fundamental data not available from current providers."

    if fundamental_result.availability == DataAvailability.AVAILABLE and fundamental_result.data:
        fd = fundamental_result.data
        bullish_points = 0
        bearish_points = 0
        details = []

        if fd.roe and fd.roe > 0.15:
            bullish_points += 1
            details.append(f"strong return on equity ({fd.roe:.1%})")
        elif fd.roe and fd.roe < 0.05:
            bearish_points += 1

        if fd.profit_margin and fd.profit_margin > 0.15:
            bullish_points += 1
            details.append(f"healthy profit margin ({fd.profit_margin:.1%})")
        elif fd.profit_margin and fd.profit_margin < 0.05:
            bearish_points += 1

        if fd.revenue_growth and fd.revenue_growth > 0.10:
            bullish_points += 1
            details.append(f"revenue growing at {fd.revenue_growth:.1%}")
        elif fd.revenue_growth and fd.revenue_growth < 0:
            bearish_points += 1
            details.append(f"revenue declining ({fd.revenue_growth:.1%})")

        if fd.debt_to_equity and fd.debt_to_equity > 2.0:
            bearish_points += 1
            details.append(f"high leverage (D/E: {fd.debt_to_equity:.1f})")
        elif fd.debt_to_equity and fd.debt_to_equity < 0.5:
            bullish_points += 1

        if bullish_points > bearish_points:
            fundamental_signal = "bullish"
        elif bearish_points > bullish_points:
            fundamental_signal = "bearish"
        else:
            fundamental_signal = "neutral"

        fundamental_confidence = 55.0 if abs(bullish_points - bearish_points) > 1 else 40.0

        signal_word = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}[fundamental_signal]
        detail_str = ". Key metrics: " + ", ".join(details[:3]) + "." if details else "."
        fundamental_summary = (
            f"Fundamental outlook is {signal_word} with {fundamental_confidence:.0f}% confidence{detail_str}"
        )

    # --- Sentiment analysis ---
    sentiment_signal_str = None
    if sentiment_result.availability == DataAvailability.PROVIDER_ERROR:
        sentiment_summary = f"Sentiment analysis failed ({sentiment_result.error_message or 'provider error'})."
    elif sentiment_result.availability == DataAvailability.NO_DATA:
        sentiment_summary = "No recent news found for sentiment analysis."
    else:
        sentiment_summary = "News and sentiment data not available."

    if sentiment_result.availability == DataAvailability.AVAILABLE and sentiment_result.data:
        sent = sentiment_result.data
        sentiment_signal_str = sent.overall_sentiment

        theme_str = f" Key themes: {', '.join(sent.themes[:3])}." if sent.themes else ""
        headline_str = ""
        if sent.headlines:
            headline_str = f" Recent: \"{sent.headlines[0][:80]}\"."

        sentiment_summary = (
            f"Market sentiment is {'positive' if sent.overall_sentiment == 'bullish' else 'negative' if sent.overall_sentiment == 'bearish' else 'neutral'} "
            f"based on {sent.total_articles} recent articles "
            f"({sent.bullish_count} positive, {sent.bearish_count} negative).{theme_str}{headline_str}"
        )

    # --- Valuation signal (from fundamentals if available) ---
    valuation_signal = None
    valuation_summary = "Valuation data not available for this instrument."

    if fundamental_result.availability == DataAvailability.AVAILABLE and fundamental_result.data:
        fd = fundamental_result.data
        if fd.pe_ratio:
            if fd.pe_ratio < 15:
                valuation_signal = "bullish"
                valuation_summary = f"Valuation appears attractive with P/E of {fd.pe_ratio:.1f}."
            elif fd.pe_ratio > 30:
                valuation_signal = "bearish"
                valuation_summary = f"Valuation appears stretched with P/E of {fd.pe_ratio:.1f}."
            else:
                valuation_signal = "neutral"
                valuation_summary = f"Valuation appears fair with P/E of {fd.pe_ratio:.1f}."

            if fd.pb_ratio:
                valuation_summary += f" Price-to-book: {fd.pb_ratio:.1f}."
            if fd.dividend_yield:
                valuation_summary += f" Dividend yield: {fd.dividend_yield:.1%}."

    # --- Risk summary ---
    risk_summary = "Risk data not available."
    if annualized_volatility:
        vol_level = "high" if annualized_volatility > 0.4 else "moderate" if annualized_volatility > 0.25 else "low"
        risk_summary = f"Volatility is {vol_level} ({annualized_volatility:.0%} annualised)."

    # --- Compute outlook ---
    outlook = compute_outlook(
        rsi_14=rsi_14,
        trend=trend,
        sentiment=sentiment_signal_str,
        valuation_signal=valuation_signal,
        annualized_volatility=annualized_volatility,
    )

    # --- Determine action and confidence ---
    action_label, confidence, positive_factors, risk_factors, uncertainties = determine_educational_action(
        technical_signal=technical_signal,
        technical_confidence=technical_confidence,
        fundamental_signal=fundamental_signal,
        fundamental_confidence=fundamental_confidence,
        sentiment_signal=sentiment_signal_str,
        valuation_signal=valuation_signal,
        risk_remaining_limit=None,
        portfolio_manager_action=None,
        rsi_14=rsi_14,
    )

    # Generate synthesis summary
    portfolio_manager_summary = _generate_portfolio_manager_summary(
        action_label=action_label,
        consensus_score=0.0,
        positive_factors=positive_factors,
        risk_factors=risk_factors,
        uncertainties=uncertainties,
        technical_signal=technical_signal,
        fundamental_signal=fundamental_signal,
        sentiment_signal=sentiment_signal_str,
        valuation_signal=valuation_signal,
    )

    # Add outlook to the summary
    portfolio_manager_summary += (
        f" Short-term outlook: {outlook.direction} ({outlook.confidence} confidence). "
        f"Expected range: {outlook.expected_range_low:+.1f}% to {outlook.expected_range_high:+.1f}%."
    )

    # --- Compute experimental price estimate ---
    from app.backend.portfolio.price_estimate import compute_price_estimate, estimate_to_dict

    price_estimate_data = None
    if price_result.availability == DataAvailability.AVAILABLE and price_result.data:
        bars = price_result.data
        if len(bars) >= 5:
            closes = [b.close for b in bars]
            daily_rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] != 0]

            # Determine sentiment score for estimate
            est_sentiment = None
            if sentiment_result.availability == DataAvailability.AVAILABLE and sentiment_result.data:
                sent = sentiment_result.data
                if sent.overall_sentiment == "bullish":
                    est_sentiment = sent.confidence
                elif sent.overall_sentiment == "bearish":
                    est_sentiment = -sent.confidence
                else:
                    est_sentiment = 0.0

            # Agent consensus from action_rules signals
            from app.backend.portfolio.action_rules import SIGNAL_SCORE
            agent_scores = []
            for sig in [technical_signal, fundamental_signal, sentiment_signal_str, valuation_signal]:
                if sig in SIGNAL_SCORE:
                    agent_scores.append(SIGNAL_SCORE[sig])
            agent_consensus = sum(agent_scores) / len(agent_scores) if agent_scores else None

            is_etf = ticker.upper() in ("ISF.L", "VWRL.L", "VMID.L", "VUSA.L", "CSP1.L", "IITU.L", "EQQQ.L", "SGLN.L", "SSLN.L")

            estimate = compute_price_estimate(
                current_price=closes[-1],
                daily_returns=daily_rets,
                sentiment_score=est_sentiment,
                agent_consensus_score=agent_consensus,
                is_etf=is_etf,
                ticker=ticker,
            )
            price_estimate_data = estimate_to_dict(estimate)

    # --- Save results ---
    results = []
    for item in items:
        analysis_result = PortfolioAnalysisResult(
            holding_id=item.get("holding_id"),
            watchlist_id=item.get("watchlist_id"),
            ticker=item["broker_ticker"],
            analysis_ticker=ticker,
            final_action=action_label,
            confidence=round(confidence, 1),
            technical_summary=technical_summary,
            fundamental_summary=fundamental_summary,
            sentiment_summary=sentiment_summary,
            valuation_summary=valuation_summary,
            risk_summary=risk_summary,
            portfolio_manager_summary=portfolio_manager_summary,
            positive_factors=json.dumps(positive_factors),
            risk_factors=json.dumps(risk_factors),
            uncertainties=json.dumps(uncertainties),
            price_estimate=json.dumps(price_estimate_data) if price_estimate_data else None,
        )
        db.add(analysis_result)
        db.commit()
        db.refresh(analysis_result)
        results.append(_result_to_dict(analysis_result))

    return results


def _process_ticker_result(
    db: Session,
    ticker: str,
    items: list[dict],
    analyst_signals: dict,
    decisions: dict,
) -> list[dict]:
    """Process agent results for a single ticker and save to DB."""
    results = []

    # Extract signals for this ticker from each agent type
    technical_signal = None
    technical_confidence = None
    fundamental_signal = None
    fundamental_confidence = None
    sentiment_signal = None
    valuation_signal = None
    risk_remaining_limit = None
    portfolio_manager_action = None
    rsi_14 = None

    # Summaries for display
    technical_summary = ""
    fundamental_summary = ""
    sentiment_summary = ""
    valuation_summary = ""
    risk_summary = ""
    portfolio_manager_summary = ""

    for agent_id, signals in analyst_signals.items():
        if ticker not in signals:
            continue
        ticker_data = signals[ticker]

        if "technical_analyst" in agent_id:
            technical_signal = ticker_data.get("signal")
            technical_confidence = ticker_data.get("confidence")
            reasoning = ticker_data.get("reasoning", {})
            # Extract RSI from mean reversion metrics
            mr = reasoning.get("mean_reversion", {})
            metrics = mr.get("metrics", {})
            if "rsi_14" in metrics:
                rsi_14 = metrics["rsi_14"]
            technical_summary = _summarize_technical(ticker_data)

        elif "fundamentals_analyst" in agent_id:
            fundamental_signal = ticker_data.get("signal")
            fundamental_confidence = ticker_data.get("confidence")
            fundamental_summary = _summarize_fundamentals(ticker_data)

        elif "sentiment_analyst" in agent_id:
            sentiment_signal = ticker_data.get("signal")
            sentiment_summary = _summarize_sentiment(ticker_data)

        elif "valuation_analyst" in agent_id:
            valuation_signal = ticker_data.get("signal")
            valuation_summary = _summarize_valuation(ticker_data)

        elif "risk_management_agent" in agent_id:
            risk_remaining_limit = ticker_data.get("remaining_position_limit")
            risk_summary = _summarize_risk(ticker_data)

    # Portfolio manager decision
    if decisions and ticker in decisions:
        pm_decision = decisions[ticker]
        portfolio_manager_action = pm_decision.get("action")
        portfolio_manager_summary = pm_decision.get("reasoning", "")

    # Determine educational action
    action_label, confidence, positive_factors, risk_factors, uncertainties = determine_educational_action(
        technical_signal=technical_signal,
        technical_confidence=technical_confidence,
        fundamental_signal=fundamental_signal,
        fundamental_confidence=fundamental_confidence,
        sentiment_signal=sentiment_signal,
        valuation_signal=valuation_signal,
        risk_remaining_limit=risk_remaining_limit,
        portfolio_manager_action=portfolio_manager_action,
        rsi_14=rsi_14,
    )

    # Generate readable synthesis summary (replaces raw LLM reasoning)
    portfolio_manager_summary = _generate_portfolio_manager_summary(
        action_label=action_label,
        consensus_score=0.0,  # Not needed for text generation
        positive_factors=positive_factors,
        risk_factors=risk_factors,
        uncertainties=uncertainties,
        technical_signal=technical_signal,
        fundamental_signal=fundamental_signal,
        sentiment_signal=sentiment_signal,
        valuation_signal=valuation_signal,
    )

    # Add short-term outlook
    from app.backend.portfolio.outlook import compute_outlook
    outlook = compute_outlook(
        rsi_14=rsi_14,
        trend=None,  # Trend not directly available from agent signals here
        sentiment=sentiment_signal,
        valuation_signal=valuation_signal,
    )
    portfolio_manager_summary += (
        f" Short-term outlook: {outlook.direction} ({outlook.confidence} confidence). "
        f"Expected range: {outlook.expected_range_low:+.1f}% to {outlook.expected_range_high:+.1f}%."
    )

    # Compute experimental price estimate for US tickers
    from app.backend.portfolio.price_estimate import compute_price_estimate, estimate_to_dict
    from app.backend.portfolio.action_rules import SIGNAL_SCORE

    price_estimate_data = None
    # Fetch prices for the estimate (use the current_prices from risk manager if available)
    current_price_val = None
    for agent_id_key, signals in analyst_signals.items():
        if "risk_management_agent" in agent_id_key and ticker in signals:
            current_price_val = signals[ticker].get("current_price")
            break

    if current_price_val and float(current_price_val) > 0:
        # Fetch daily returns for the estimate
        try:
            from src.tools.api import get_prices, prices_to_df
            end_date_str = datetime.now().strftime("%Y-%m-%d")
            start_date_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            prices_data = get_prices(ticker=ticker, start_date=start_date_str, end_date=end_date_str)
            if prices_data and len(prices_data) >= 5:
                closes = [float(p.close) for p in prices_data]
                daily_rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] != 0]

                # Sentiment score
                est_sentiment = None
                if sentiment_signal in SIGNAL_SCORE:
                    est_sentiment = SIGNAL_SCORE[sentiment_signal]

                # Agent consensus
                agent_scores = []
                for sig in [technical_signal, fundamental_signal, sentiment_signal, valuation_signal]:
                    if sig in SIGNAL_SCORE:
                        agent_scores.append(SIGNAL_SCORE[sig])
                agent_consensus = sum(agent_scores) / len(agent_scores) if agent_scores else None

                estimate = compute_price_estimate(
                    current_price=float(current_price_val),
                    daily_returns=daily_rets,
                    sentiment_score=est_sentiment,
                    agent_consensus_score=agent_consensus,
                    is_etf=False,
                    ticker=ticker,
                )
                price_estimate_data = estimate_to_dict(estimate)
        except Exception as e:
            logger.debug(f"Price estimate failed for {ticker}: {e}")

    # Save result for each item that maps to this ticker
    for item in items:
        analysis_result = PortfolioAnalysisResult(
            holding_id=item.get("holding_id"),
            watchlist_id=item.get("watchlist_id"),
            ticker=item["broker_ticker"],
            analysis_ticker=ticker,
            final_action=action_label,
            confidence=round(confidence, 1),
            technical_summary=technical_summary,
            fundamental_summary=fundamental_summary,
            sentiment_summary=sentiment_summary,
            valuation_summary=valuation_summary,
            risk_summary=risk_summary,
            portfolio_manager_summary=portfolio_manager_summary,
            positive_factors=json.dumps(positive_factors),
            risk_factors=json.dumps(risk_factors),
            uncertainties=json.dumps(uncertainties),
            price_estimate=json.dumps(price_estimate_data) if price_estimate_data else None,
        )
        db.add(analysis_result)
        db.commit()
        db.refresh(analysis_result)

        results.append(_result_to_dict(analysis_result))

    return results


def _create_unsupported_result(db: Session, item: dict) -> dict:
    """Create a result for unsupported tickers with clear explanation."""
    broker_ticker = item["broker_ticker"]
    analysis_ticker = item.get("analysis_ticker", broker_ticker)

    # Determine the specific reason
    if analysis_ticker.endswith(".L"):
        reason = f"{broker_ticker} is listed on the London Stock Exchange. Our primary data providers currently cover US-listed equities only."
        category = "UK/LSE-listed instrument"
    elif len(broker_ticker) > 5 and broker_ticker.isalnum():
        reason = f"{broker_ticker} appears to be a SEDOL or ISIN code rather than a tradeable ticker symbol."
        category = "Non-ticker identifier"
    else:
        reason = f"{broker_ticker} is not covered by available data providers."
        category = "Unsupported ticker"

    summary = (
        f"Unable to analyse — {category.lower()}. {reason} "
        f"Price data may still appear from Yahoo Finance, but full agent analysis requires US market data coverage."
    )

    analysis_result = PortfolioAnalysisResult(
        holding_id=item.get("holding_id"),
        watchlist_id=item.get("watchlist_id"),
        ticker=broker_ticker,
        analysis_ticker=analysis_ticker,
        final_action="WATCH",
        confidence=0.0,
        technical_summary="Not available — ticker not supported by analysis providers.",
        fundamental_summary="Not available — no fundamental data source for this instrument.",
        sentiment_summary="Not available — sentiment data requires US-listed coverage.",
        valuation_summary="Not available — valuation metrics not accessible for this instrument.",
        risk_summary="Cannot assess — insufficient data.",
        portfolio_manager_summary=summary,
        positive_factors=json.dumps([]),
        risk_factors=json.dumps([f"No analysis data available ({category})"]),
        uncertainties=json.dumps([reason]),
    )
    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)
    return _result_to_dict(analysis_result)


def _create_error_result(db: Session, item: dict, error_msg: str) -> dict:
    """Create a result when the pipeline errors, with clear explanation."""
    broker_ticker = item["broker_ticker"]

    # Classify the error
    error_lower = error_msg.lower()
    if "api key" in error_lower or "unauthorized" in error_lower or "401" in error_lower:
        summary = (
            f"Analysis failed — API key issue. The configured API key may be invalid or expired. "
            f"Check Settings > API Keys to verify your credentials."
        )
        risk_note = "API authentication failure — check API key configuration"
    elif "timeout" in error_lower or "connection" in error_lower:
        summary = (
            f"Analysis failed — network issue. Could not reach the data provider. "
            f"This may be temporary; try again in a few minutes."
        )
        risk_note = "Network/timeout error — may be temporary"
    elif "rate limit" in error_lower or "429" in error_lower:
        summary = (
            f"Analysis failed — rate limited by data provider. "
            f"Too many requests in a short period. Wait a few minutes before retrying."
        )
        risk_note = "Rate limited — wait before retrying"
    else:
        summary = (
            f"Analysis encountered an unexpected error and could not complete. "
            f"The issue has been logged. You may retry, or check that the ticker is valid."
        )
        risk_note = "Unexpected analysis error"

    analysis_result = PortfolioAnalysisResult(
        holding_id=item.get("holding_id"),
        watchlist_id=item.get("watchlist_id"),
        ticker=broker_ticker,
        analysis_ticker=item.get("analysis_ticker", broker_ticker),
        final_action="WATCH",
        confidence=0.0,
        technical_summary="Analysis did not complete.",
        fundamental_summary="Analysis did not complete.",
        sentiment_summary="Analysis did not complete.",
        valuation_summary="Analysis did not complete.",
        risk_summary="Cannot assess — analysis pipeline error.",
        portfolio_manager_summary=summary,
        positive_factors=json.dumps([]),
        risk_factors=json.dumps([risk_note]),
        uncertainties=json.dumps([f"Error detail: {error_msg[:200]}"]),
    )
    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)
    return _result_to_dict(analysis_result)


def _result_to_dict(r: PortfolioAnalysisResult) -> dict:
    """Convert a DB result to a serializable dict."""
    price_estimate = None
    if r.price_estimate:
        try:
            price_estimate = json.loads(r.price_estimate)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": r.id,
        "holding_id": r.holding_id,
        "watchlist_id": r.watchlist_id,
        "ticker": r.ticker,
        "analysis_ticker": r.analysis_ticker,
        "final_action": r.final_action,
        "confidence": r.confidence,
        "technical_summary": r.technical_summary,
        "fundamental_summary": r.fundamental_summary,
        "sentiment_summary": r.sentiment_summary,
        "valuation_summary": r.valuation_summary,
        "risk_summary": r.risk_summary,
        "portfolio_manager_summary": r.portfolio_manager_summary,
        "positive_factors": json.loads(r.positive_factors) if r.positive_factors else [],
        "risk_factors": json.loads(r.risk_factors) if r.risk_factors else [],
        "uncertainties": json.loads(r.uncertainties) if r.uncertainties else [],
        "price_estimate": price_estimate,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# --- Human-readable summary formatters ---

_SIGNAL_LABELS = {
    "bullish": "positive",
    "bearish": "negative",
    "neutral": "neutral",
}


def _signal_word(signal: str) -> str:
    return _SIGNAL_LABELS.get(signal, signal or "unknown")


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"{v*100:.1f}%" if abs(v) < 10 else f"{v:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _fmt_num(val) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1_000_000_000:
            return f"${v/1e9:.1f}B"
        if abs(v) >= 1_000_000:
            return f"${v/1e6:.1f}M"
        if abs(v) >= 1000:
            return f"${v:,.0f}"
        return f"{v:.2f}"
    except (TypeError, ValueError):
        return str(val)


def _rsi_description(rsi: float) -> str:
    if rsi > 70:
        return f"overbought ({rsi:.0f})"
    if rsi < 30:
        return f"oversold ({rsi:.0f})"
    if rsi > 60:
        return f"moderately strong ({rsi:.0f})"
    if rsi < 40:
        return f"moderately weak ({rsi:.0f})"
    return f"neutral range ({rsi:.0f})"


def _summarize_technical(data: dict) -> str:
    signal = data.get("signal", "unknown")
    confidence = data.get("confidence")
    reasoning = data.get("reasoning", {})

    parts = []

    # Lead with a readable sentence
    conf_str = f" with {confidence:.0f}% confidence" if confidence is not None else ""
    parts.append(f"Technical outlook is {_signal_word(signal)}{conf_str}.")

    # Trend context
    tf = reasoning.get("trend_following", {})
    if tf.get("signal"):
        trend_word = _signal_word(tf["signal"])
        parts.append(f"Price trend is {trend_word}.")

    # RSI
    mr = reasoning.get("mean_reversion", {})
    metrics = mr.get("metrics", {})
    if "rsi_14" in metrics:
        parts.append(f"RSI(14) is {_rsi_description(metrics['rsi_14'])}.")

    # Momentum
    mom = reasoning.get("momentum", {})
    if mom.get("signal"):
        parts.append(f"Momentum is {_signal_word(mom['signal'])}.")

    return " ".join(parts)


def _summarize_fundamentals(data: dict) -> str:
    signal = data.get("signal", "unknown")
    confidence = data.get("confidence")
    reasoning = data.get("reasoning", {})

    parts = []
    conf_str = f" with {confidence:.0f}% confidence" if confidence is not None else ""
    parts.append(f"Fundamental outlook is {_signal_word(signal)}{conf_str}.")

    if isinstance(reasoning, str):
        parts.append(reasoning[:200])
        return " ".join(parts)

    # Key metrics in readable form
    details = []
    if "revenue_growth" in reasoning:
        details.append(f"revenue growing at {_fmt_pct(reasoning['revenue_growth'])}")
    if "earnings_growth" in reasoning:
        details.append(f"earnings growth of {_fmt_pct(reasoning['earnings_growth'])}")
    if "profit_margin" in reasoning:
        details.append(f"profit margin at {_fmt_pct(reasoning['profit_margin'])}")
    if "roe" in reasoning:
        details.append(f"return on equity of {_fmt_pct(reasoning['roe'])}")
    if "debt_to_equity" in reasoning:
        details.append(f"debt-to-equity ratio of {_fmt_num(reasoning['debt_to_equity'])}")

    if details:
        parts.append("Key metrics: " + ", ".join(details[:3]) + ".")
    elif reasoning and not isinstance(reasoning, str):
        flat = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in list(reasoning.items())[:3] if not isinstance(v, dict))
        if flat:
            parts.append(flat[:150] + ".")

    return " ".join(parts)


def _summarize_sentiment(data: dict) -> str:
    signal = data.get("signal", "unknown")
    confidence = data.get("confidence")
    reasoning = data.get("reasoning", {})

    parts = []
    conf_str = f" with {confidence:.0f}% confidence" if confidence is not None else ""
    parts.append(f"Market sentiment is {_signal_word(signal)}{conf_str}.")

    if isinstance(reasoning, str):
        parts.append(reasoning[:200])
        return " ".join(parts)

    if "insider_trading" in reasoning:
        insider = reasoning["insider_trading"]
        if isinstance(insider, dict) and insider.get("signal"):
            parts.append(f"Insider activity is {_signal_word(insider['signal'])}.")
    if "news_sentiment" in reasoning:
        news = reasoning["news_sentiment"]
        if isinstance(news, dict) and news.get("signal"):
            parts.append(f"News coverage is {_signal_word(news['signal'])}.")
        elif isinstance(news, str):
            parts.append(news[:100])

    return " ".join(parts)


def _summarize_valuation(data: dict) -> str:
    signal = data.get("signal", "unknown")
    confidence = data.get("confidence")
    reasoning = data.get("reasoning", {})

    parts = []
    conf_str = f" with {confidence:.0f}% confidence" if confidence is not None else ""

    val_description = {
        "bullish": "appears undervalued or fairly priced",
        "bearish": "appears expensive relative to fundamentals",
        "neutral": "appears fairly valued",
    }
    desc = val_description.get(signal, f"is {_signal_word(signal)}")
    parts.append(f"Valuation {desc}{conf_str}.")

    if isinstance(reasoning, str):
        parts.append(reasoning[:200])
        return " ".join(parts)

    details = []
    if "pe_ratio" in reasoning and reasoning["pe_ratio"]:
        details.append(f"P/E of {_fmt_num(reasoning['pe_ratio'])}")
    if "pb_ratio" in reasoning and reasoning["pb_ratio"]:
        details.append(f"P/B of {_fmt_num(reasoning['pb_ratio'])}")
    if "margin_of_safety" in reasoning and reasoning["margin_of_safety"]:
        details.append(f"margin of safety: {_fmt_pct(reasoning['margin_of_safety'])}")
    if "intrinsic_value" in reasoning and reasoning["intrinsic_value"]:
        details.append(f"estimated intrinsic value: {_fmt_num(reasoning['intrinsic_value'])}")

    if details:
        parts.append("Metrics: " + ", ".join(details[:3]) + ".")

    return " ".join(parts)


def _summarize_risk(data: dict) -> str:
    reasoning = data.get("reasoning", {})
    price = data.get("current_price")
    parts = []

    if isinstance(reasoning, dict):
        vol = data.get("volatility_metrics", {})
        ann_vol = vol.get("annualized_volatility")
        if ann_vol:
            if ann_vol > 0.4:
                parts.append(f"Volatility is high ({ann_vol:.0%} annualised).")
            elif ann_vol > 0.25:
                parts.append(f"Volatility is moderate ({ann_vol:.0%} annualised).")
            else:
                parts.append(f"Volatility is low ({ann_vol:.0%} annualised).")
        adj = reasoning.get("risk_adjustment")
        if adj and isinstance(adj, str):
            parts.append(adj[:150])
    elif isinstance(reasoning, str):
        parts.append(reasoning[:200])

    limit = data.get("remaining_position_limit")
    if limit is not None and limit < 0:
        parts.append("Position size exceeds recommended risk limit.")

    return " ".join(parts) if parts else "Risk data not available for this ticker."


def _generate_portfolio_manager_summary(
    action_label: str,
    consensus_score: float,
    positive_factors: list[str],
    risk_factors: list[str],
    uncertainties: list[str],
    technical_signal: Optional[str],
    fundamental_signal: Optional[str],
    sentiment_signal: Optional[str],
    valuation_signal: Optional[str],
) -> str:
    """Generate a coherent, readable portfolio manager synthesis summary."""
    parts = []

    available = [s for s in [technical_signal, fundamental_signal, sentiment_signal, valuation_signal] if s]
    bullish_count = sum(1 for s in available if s == "bullish")
    bearish_count = sum(1 for s in available if s == "bearish")
    neutral_count = sum(1 for s in available if s == "neutral")

    if not available:
        return "Insufficient data to form a consensus view. Monitoring recommended."

    has_conflict = bullish_count > 0 and bearish_count > 0

    # Consensus description — language strength proportional to signal strength
    if has_conflict:
        if bullish_count > bearish_count + 1:
            parts.append("Predominantly positive signals, though not unanimous.")
        elif bearish_count > bullish_count + 1:
            parts.append("Predominantly cautious signals, though not unanimous.")
        elif bullish_count > bearish_count:
            parts.append("Mixed signals with a slight positive lean.")
        elif bearish_count > bullish_count:
            parts.append("Mixed signals with a slight negative lean.")
        else:
            parts.append("Conflicting signals — no clear directional consensus.")
    elif bullish_count >= 3:
        parts.append("Broad positive agreement across analysis dimensions.")
    elif bearish_count >= 3:
        parts.append("Broad caution across analysis dimensions.")
    elif bullish_count == 2 and neutral_count >= 1:
        parts.append("Mildly positive outlook with some neutral readings.")
    elif bearish_count == 2 and neutral_count >= 1:
        parts.append("Mildly cautious outlook with some neutral readings.")
    elif bullish_count == 2:
        parts.append("Moderately positive outlook from available data.")
    elif bearish_count == 2:
        parts.append("Moderately cautious outlook from available data.")
    elif neutral_count >= 3:
        parts.append("Broadly neutral — no strong signals in either direction.")
    elif neutral_count >= 2:
        parts.append("Mostly neutral with limited directional conviction.")
    elif bullish_count == 1 and neutral_count >= 1:
        parts.append("Slightly positive lean, but largely neutral picture.")
    elif bearish_count == 1 and neutral_count >= 1:
        parts.append("Slightly cautious lean, but largely neutral picture.")
    else:
        parts.append("Limited data — insufficient for strong conviction.")

    # Describe the key tension if signals conflict
    if has_conflict:
        pos_dims = []
        neg_dims = []
        if technical_signal == "bullish":
            pos_dims.append("technicals")
        if fundamental_signal == "bullish":
            pos_dims.append("fundamentals")
        if sentiment_signal == "bullish":
            pos_dims.append("sentiment")
        if valuation_signal == "bullish":
            pos_dims.append("valuation")
        if technical_signal == "bearish":
            neg_dims.append("technicals")
        if fundamental_signal == "bearish":
            neg_dims.append("fundamentals")
        if sentiment_signal == "bearish":
            neg_dims.append("sentiment")
        if valuation_signal == "bearish":
            neg_dims.append("valuation")

        if pos_dims and neg_dims:
            parts.append(
                f"{', '.join(pos_dims).capitalize()} {'are' if len(pos_dims) > 1 else 'is'} supportive, "
                f"while {', '.join(neg_dims)} {'suggest' if len(neg_dims) > 1 else 'suggests'} caution."
            )

    # Add key factor context (concise — max 1 positive + 1 risk)
    if positive_factors and not has_conflict:
        parts.append(f"Key positive: {positive_factors[0].lower()}.")
    if risk_factors:
        parts.append(f"Key concern: {risk_factors[0].lower()}.")

    # Action context — calibrated language
    action_context = {
        "ADD CAUTIOUSLY": "May warrant gradual position building for long-term investors with appropriate risk tolerance.",
        "HOLD": "Current position appears reasonable to maintain.",
        "WATCH": "Monitoring recommended — wait for clearer signals before acting.",
        "REVIEW": "Worth reviewing whether current allocation remains appropriate.",
        "REDUCE / REVIEW EXIT": "Consider reducing exposure given current risk profile.",
    }
    if action_label in action_context:
        parts.append(action_context[action_label])

    return " ".join(parts)
