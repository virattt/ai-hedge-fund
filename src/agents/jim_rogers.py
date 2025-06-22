from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
    get_company_news,
    get_prices,
    get_insider_trades
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
import statistics
from datetime import datetime, timedelta


class JimRogersSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def jim_rogers_agent(state: AgentState):
    """
    Enhanced Jim Rogers analysis based on his legendary investment philosophy:
    
    CORE PRINCIPLES:
    1. Global Macro Focus: "I never buy anything unless I can fill up a whole page with reasons"
    2. Contrarian Investing: "Buy low, sell high" - invest when others are pessimistic
    3. Commodities & Real Assets: Agriculture, energy, precious metals, infrastructure
    4. Long-term Vision: Hold for years/decades, not months
    5. Supply/Demand Fundamentals: Real economic drivers, not financial engineering
    6. Emerging Markets: Undervalued opportunities in developing economies
    7. Economic Cycles: Understanding boom/bust patterns
    8. Demographics & Trends: Population shifts, urbanization, technology adoption
    9. Currency & Geopolitics: How global events affect investments
    10. Direct Investment: Actually understanding the business/commodity
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    analysis_data = {}
    rogers_analysis = {}

    for ticker in tickers:
        progress.update_status("jim_rogers_agent", ticker, "Fetching comprehensive financial data")
        
        # Get multiple time periods for trend analysis
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=10)
        quarterly_metrics = get_financial_metrics(ticker, end_date, period="quarterly", limit=12)

        progress.update_status("jim_rogers_agent", ticker, "Gathering fundamental line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "gross_profit", 
                "operating_income",
                "net_income",
                "earnings_per_share",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "total_assets",
                "inventory",
                "research_and_development",
                "outstanding_shares",
                "dividends_and_other_cash_distributions",
                "depreciation_and_amortization",
                "current_assets",
                "current_liabilities"
            ],
            end_date,
            period="annual",
            limit=10,
        )

        progress.update_status("jim_rogers_agent", ticker, "Getting market cap and pricing data")
        market_cap = get_market_cap(ticker, end_date)
        prices = get_prices(ticker, start_date=start_date, end_date=end_date)

        progress.update_status("jim_rogers_agent", ticker, "Analyzing global news and sentiment")
        company_news = get_company_news(ticker, end_date, start_date=None, limit=200)
        insider_trades = get_insider_trades(ticker, end_date, start_date=start_date, limit=100)

        # Enhanced Jim Rogers Analysis Components
        progress.update_status("jim_rogers_agent", ticker, "Analyzing global macro trends")
        macro_analysis = analyze_global_macro_trends(financial_line_items, company_news, ticker, quarterly_metrics)

        progress.update_status("jim_rogers_agent", ticker, "Identifying contrarian opportunities")
        contrarian_analysis = analyze_contrarian_opportunities(prices, company_news, metrics, insider_trades)

        progress.update_status("jim_rogers_agent", ticker, "Evaluating commodities & real assets exposure")
        commodities_analysis = analyze_commodities_real_assets(ticker, financial_line_items, metrics, company_news)

        progress.update_status("jim_rogers_agent", ticker, "Assessing supply/demand fundamentals")
        supply_demand_analysis = analyze_supply_demand_dynamics(financial_line_items, metrics, prices)

        progress.update_status("jim_rogers_agent", ticker, "Analyzing demographic & structural trends")
        demographic_analysis = analyze_demographic_trends(company_news, financial_line_items, ticker)

        progress.update_status("jim_rogers_agent", ticker, "Evaluating long-term economic cycles")
        cycle_analysis = analyze_economic_cycles(financial_line_items, metrics, prices, ticker)

        # Calculate Jim Rogers weighted score
        # His priorities: Macro (35%), Contrarian (25%), Commodities (20%), Demographics (10%), Cycles (10%)
        total_score = (
            macro_analysis["score"] * 0.35 +
            contrarian_analysis["score"] * 0.25 +
            commodities_analysis["score"] * 0.20 +
            supply_demand_analysis["score"] * 0.10 +
            demographic_analysis["score"] * 0.05 +
            cycle_analysis["score"] * 0.05
        )

        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": 10.0,
            "macro_analysis": macro_analysis,
            "contrarian_analysis": contrarian_analysis,
            "commodities_analysis": commodities_analysis,
            "supply_demand_analysis": supply_demand_analysis,
            "demographic_analysis": demographic_analysis,
            "cycle_analysis": cycle_analysis,
            "market_cap": market_cap,
            "price_performance": calculate_price_performance(prices),
        }

        progress.update_status("jim_rogers_agent", ticker, "Generating Jim Rogers investment thesis")
        rogers_output = generate_enhanced_rogers_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
        )

        rogers_analysis[ticker] = {
            "signal": rogers_output.signal,
            "confidence": rogers_output.confidence,
            "reasoning": rogers_output.reasoning,
        }

        progress.update_status("jim_rogers_agent", ticker, "Analysis complete", analysis=rogers_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(rogers_analysis), name="jim_rogers_agent")

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(rogers_analysis, "Jim Rogers Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["jim_rogers_agent"] = rogers_analysis

    progress.update_status("jim_rogers_agent", None, "Complete")

    return {"messages": [message], "data": state["data"]}


def analyze_global_macro_trends(financial_line_items: list, company_news: list, ticker: str, quarterly_metrics: list) -> dict:
    """Enhanced macro analysis focusing on global economic trends and geopolitical factors."""
    if not financial_line_items:
        return {"score": 0, "details": "Insufficient data for macro analysis"}

    details = []
    score = 0

    # 1. Multi-year revenue growth trends (global expansion indicator)
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    if len(revenues) >= 5:
        latest_rev = revenues[0]
        oldest_rev = revenues[-1]
        years = len(revenues) - 1
        
        if oldest_rev > 0 and years > 0:
            cagr = ((latest_rev / oldest_rev) ** (1/years)) - 1
            if cagr > 0.20:  # Strong global growth
                score += 4
                details.append(f"Exceptional global growth CAGR: {cagr:.1%} - strong macro tailwinds")
            elif cagr > 0.12:
                score += 3
                details.append(f"Strong global growth CAGR: {cagr:.1%}")
            elif cagr > 0.06:
                score += 2
                details.append(f"Steady global growth CAGR: {cagr:.1%}")
            elif cagr > 0:
                score += 1
                details.append(f"Modest growth CAGR: {cagr:.1%}")

    # 2. Global economic resilience (revenue stability across cycles)
    if len(revenues) >= 7:
        revenue_volatility = statistics.stdev(revenues) / statistics.mean(revenues) if statistics.mean(revenues) > 0 else float('inf')
        if revenue_volatility < 0.10:
            score += 2
            details.append("Exceptional revenue stability - recession-resistant business")
        elif revenue_volatility < 0.20:
            score += 1
            details.append("Good revenue stability across economic cycles")

    # 3. International/emerging markets exposure through news analysis
    if company_news:
        global_keywords = [
            'international', 'global', 'worldwide', 'overseas', 'export', 'import',
            'emerging', 'asia', 'china', 'india', 'brazil', 'africa', 'latin america',
            'europe', 'expansion', 'infrastructure', 'developing', 'growth markets'
        ]
        global_news_count = sum(1 for news in company_news if 
                               any(keyword in news.title.lower() for keyword in global_keywords))
        
        total_news = len(company_news)
        if total_news > 0:
            global_exposure_ratio = global_news_count / total_news
            if global_exposure_ratio > 0.15:
                score += 2
                details.append(f"Strong global/emerging markets exposure in news ({global_exposure_ratio:.1%})")
            elif global_exposure_ratio > 0.05:
                score += 1
                details.append(f"Moderate global exposure in news ({global_exposure_ratio:.1%})")

    # 4. Currency/commodity sensitivity indicators
    if quarterly_metrics and len(quarterly_metrics) >= 4:
        # Look for margin volatility that might indicate commodity/currency exposure
        margins = [qm.gross_margin for qm in quarterly_metrics[-4:] if qm.gross_margin is not None]
        if len(margins) >= 3:
            margin_volatility = statistics.stdev(margins)
            if margin_volatility > 0.05:  # High margin volatility suggests commodity exposure
                score += 1
                details.append("Margin volatility suggests commodity/currency sensitivity")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited global macro indicators"
    }


def analyze_contrarian_opportunities(prices: list, company_news: list, metrics: list, insider_trades: list) -> dict:
    """Enhanced contrarian analysis - buying when others are pessimistic."""
    if not prices:
        return {"score": 0, "details": "Insufficient price data for contrarian analysis"}

    details = []
    score = 0

    # 1. Price performance analysis (looking for beaten-down stocks)
    if len(prices) >= 60:  # Need at least ~3 months of data
        recent_prices = [p.close for p in prices[:30]]  # Last 30 days
        older_prices = [p.close for p in prices[-30:]]   # 30 days ago
        
        recent_avg = sum(recent_prices) / len(recent_prices)
        older_avg = sum(older_prices) / len(older_prices)
        
        price_change = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        
        if price_change < -0.20:  # Down >20%
            score += 4
            details.append(f"Significant price decline ({price_change:.1%}) - potential contrarian opportunity")
        elif price_change < -0.10:  # Down >10%
            score += 3
            details.append(f"Notable price decline ({price_change:.1%}) - contrarian signal")
        elif price_change < -0.05:  # Down >5%
            score += 2
            details.append(f"Moderate price decline ({price_change:.1%})")

    # 2. Negative sentiment analysis in news
    if company_news:
        negative_keywords = [
            'concern', 'worry', 'decline', 'fall', 'drop', 'weak', 'poor', 'disappointing',
            'challenge', 'pressure', 'struggle', 'difficult', 'recession', 'crisis',
            'uncertainty', 'volatility', 'risk', 'threat', 'competition'
        ]
        negative_news_count = sum(1 for news in company_news if 
                                any(keyword in news.title.lower() for keyword in negative_keywords))
        
        total_news = len(company_news)
        if total_news > 0:
            negative_ratio = negative_news_count / total_news
            if negative_ratio > 0.30:
                score += 2
                details.append(f"High negative sentiment in news ({negative_ratio:.1%}) - contrarian opportunity")
            elif negative_ratio > 0.15:
                score += 1
                details.append(f"Moderate negative sentiment in news ({negative_ratio:.1%})")

    # 3. Insider buying during downturn (contrarian signal)
    if insider_trades:
        recent_trades = [trade for trade in insider_trades if trade.transaction_shares and trade.transaction_shares > 0]
        buying_volume = sum(trade.transaction_shares for trade in recent_trades)
        
        if buying_volume > 0:
            score += 1
            details.append("Insider buying detected during market weakness")

    # 4. Valuation compression (low multiples due to pessimism)
    if metrics:
        latest_metrics = metrics[0]
        if latest_metrics.price_to_earnings_ratio and latest_metrics.price_to_earnings_ratio < 12:
            score += 2
            details.append(f"Low P/E ratio ({latest_metrics.price_to_earnings_ratio:.1f}) - potential value opportunity")
        elif latest_metrics.price_to_earnings_ratio and latest_metrics.price_to_earnings_ratio < 15:
            score += 1
            details.append(f"Reasonable P/E ratio ({latest_metrics.price_to_earnings_ratio:.1f})")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited contrarian signals detected"
    }


def analyze_commodities_real_assets(ticker: str, financial_line_items: list, metrics: list, company_news: list) -> dict:
    """Enhanced commodities and real assets analysis."""
    details = []
    score = 0

    # 1. Direct commodity sector exposure (Jim Rogers' specialty)
    commodity_sectors = {
        'agriculture': ['ADM', 'BG', 'CF', 'MOS', 'FMC', 'NTR', 'POT', 'DE', 'CAT'],
        'energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'HAL', 'OXY', 'PXD', 'FANG', 'DVN'],
        'mining': ['FCX', 'NEM', 'GOLD', 'AEM', 'AU', 'KL', 'VALE', 'RIO', 'BHP'],
        'materials': ['DD', 'DOW', 'LYB', 'APD', 'LIN', 'SHW', 'PPG', 'AA', 'X'],
        'infrastructure': ['UNP', 'CSX', 'NSC', 'KMI', 'WMB', 'EPD', 'ET', 'OKE']
    }

    # Check direct commodity exposure
    for sector, tickers_list in commodity_sectors.items():
        if ticker in tickers_list:
            score += 5
            details.append(f"Direct commodity exposure in {sector} sector - Jim Rogers specialty")
            break

    # 2. Commodity-like business characteristics
    if financial_line_items:
        # Low R&D suggests commodity business
        rd_expenses = [fi.research_and_development for fi in financial_line_items if fi.research_and_development is not None]
        revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
        
        if rd_expenses and revenues and len(rd_expenses) >= 3 and len(revenues) >= 3:
            avg_rd_ratio = sum(rd / rev for rd, rev in zip(rd_expenses[:3], revenues[:3]) if rev > 0) / 3
            if avg_rd_ratio < 0.02:  # Less than 2% R&D
                score += 2
                details.append("Low R&D spending - commodity business characteristics")
            elif avg_rd_ratio < 0.05:  # Less than 5% R&D
                score += 1
                details.append("Moderate R&D spending - some commodity characteristics")

        # High asset intensity (typical of commodity businesses)
        if financial_line_items:
            latest = financial_line_items[0]
            if latest.total_assets and latest.revenue:
                asset_turnover = latest.revenue / latest.total_assets
                if asset_turnover < 0.8:  # Capital intensive
                    score += 1
                    details.append("Capital intensive business - typical of commodity/infrastructure")

    # 3. Infrastructure and real asset themes in news
    if company_news:
        commodity_keywords = [
            'commodity', 'commodities', 'raw materials', 'infrastructure', 'pipeline',
            'mining', 'drilling', 'exploration', 'agriculture', 'farming', 'crop',
            'oil', 'gas', 'energy', 'power', 'electricity', 'renewable', 'solar', 'wind',
            'transportation', 'shipping', 'logistics', 'supply chain', 'warehouse'
        ]
        commodity_news_count = sum(1 for news in company_news if 
                                 any(keyword in news.title.lower() for keyword in commodity_keywords))
        
        total_news = len(company_news)
        if total_news > 0:
            commodity_ratio = commodity_news_count / total_news
            if commodity_ratio > 0.20:
                score += 2
                details.append(f"Strong commodity/infrastructure themes in news ({commodity_ratio:.1%})")
            elif commodity_ratio > 0.10:
                score += 1
                details.append(f"Moderate commodity themes in news ({commodity_ratio:.1%})")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited commodity/real asset exposure"
    }


def analyze_supply_demand_dynamics(financial_line_items: list, metrics: list, prices: list) -> dict:
    """Analyze real supply/demand fundamentals - Rogers' focus on economic reality."""
    if not financial_line_items or not metrics:
        return {"score": 0, "details": "Insufficient data for supply/demand analysis"}

    details = []
    score = 0

    # 1. Pricing power through margin expansion
    if len(financial_line_items) >= 5:
        gross_profits = [fi.gross_profit for fi in financial_line_items if fi.gross_profit is not None]
        revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
        
        if len(gross_profits) >= 5 and len(revenues) >= 5:
            margins = [(gp / rev) if rev > 0 else 0 for gp, rev in zip(gross_profits, revenues)]
            
            if len(margins) >= 5:
                recent_margins = margins[:2]  # Last 2 years
                older_margins = margins[-2:]  # Oldest 2 years
                
                recent_avg = sum(recent_margins) / len(recent_margins)
                older_avg = sum(older_margins) / len(older_margins)
                margin_improvement = recent_avg - older_avg
                
                if margin_improvement > 0.05:  # 5%+ improvement
                    score += 3
                    details.append(f"Strong margin expansion ({margin_improvement:.1%}) - excellent pricing power")
                elif margin_improvement > 0.02:  # 2%+ improvement
                    score += 2
                    details.append(f"Good margin expansion ({margin_improvement:.1%}) - solid demand")
                elif margin_improvement > 0:
                    score += 1
                    details.append("Modest margin improvement")

    # 2. Capacity utilization and efficiency
    if financial_line_items and metrics:
        latest_metrics = metrics[0]
        if latest_metrics.asset_turnover:
            if latest_metrics.asset_turnover > 2.0:
                score += 2
                details.append("High asset turnover - strong demand for products/services")
            elif latest_metrics.asset_turnover > 1.2:
                score += 1
                details.append("Good asset turnover - decent demand dynamics")

    # 3. Inventory management (supply chain efficiency)
    if len(financial_line_items) >= 3:
        inventories = [fi.inventory for fi in financial_line_items if fi.inventory is not None]
        revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
        
        if len(inventories) >= 3 and len(revenues) >= 3:
            inventory_ratios = [inv / rev if rev > 0 else 0 for inv, rev in zip(inventories, revenues)]
            
            if len(inventory_ratios) >= 3:
                recent_ratio = inventory_ratios[0]
                older_ratio = inventory_ratios[-1]
                
                if recent_ratio < older_ratio * 0.9:  # Inventory efficiency improving
                    score += 1
                    details.append("Improving inventory efficiency - good demand management")

    # 4. Free cash flow generation (real economic value)
    if financial_line_items:
        fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]
        if len(fcf_values) >= 3:
            positive_fcf_years = sum(1 for fcf in fcf_values if fcf > 0)
            if positive_fcf_years == len(fcf_values):
                score += 2
                details.append("Consistent free cash flow generation - strong business fundamentals")
            elif positive_fcf_years >= len(fcf_values) * 0.7:
                score += 1
                details.append("Generally positive free cash flow")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited supply/demand data available"
    }


def analyze_demographic_trends(company_news: list, financial_line_items: list, ticker: str) -> dict:
    """Analyze demographic and structural trends - Rogers' long-term view."""
    details = []
    score = 0

    # 1. Demographic trend themes in news
    if company_news:
        demographic_keywords = [
            'aging', 'elderly', 'retirement', 'healthcare', 'medical', 'pharmaceutical',
            'millennial', 'generation', 'demographic', 'population', 'urbanization',
            'education', 'technology adoption', 'digital transformation', 'automation',
            'climate', 'environment', 'sustainability', 'renewable', 'green',
            'emerging markets', 'developing', 'growth markets', 'middle class'
        ]
        
        demographic_news_count = sum(1 for news in company_news if 
                                   any(keyword in news.title.lower() for keyword in demographic_keywords))
        
        total_news = len(company_news)
        if total_news > 0:
            demographic_ratio = demographic_news_count / total_news
            if demographic_ratio > 0.15:
                score += 3
                details.append(f"Strong demographic/structural trend exposure ({demographic_ratio:.1%})")
            elif demographic_ratio > 0.05:
                score += 2
                details.append(f"Moderate demographic trend exposure ({demographic_ratio:.1%})")

    # 2. Technology adoption and infrastructure development
    tech_infrastructure_sectors = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'AMD', 'INTC']
    if ticker in tech_infrastructure_sectors:
        score += 2
        details.append("Technology infrastructure - key demographic trend beneficiary")

    # 3. Revenue growth consistency (indicating structural demand)
    if len(financial_line_items) >= 7:
        revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
        if len(revenues) >= 7:
            growth_years = sum(1 for i in range(len(revenues)-1) if revenues[i] > revenues[i+1])
            consistency_ratio = growth_years / (len(revenues) - 1)
            
            if consistency_ratio > 0.8:  # 80%+ of years showed growth
                score += 2
                details.append("Highly consistent revenue growth - structural demand trend")
            elif consistency_ratio > 0.6:
                score += 1
                details.append("Good revenue growth consistency")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited demographic trend indicators"
    }


def analyze_economic_cycles(financial_line_items: list, metrics: list, prices: list, ticker: str = None) -> dict:
    """Analyze economic cycle positioning - Rogers' understanding of cycles."""
    details = []
    score = 0

    # 1. Cyclical resilience during economic stress
    if len(financial_line_items) >= 10:  # Need long history for cycle analysis
        revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
        net_incomes = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
        
        if len(revenues) >= 8 and len(net_incomes) >= 8:
            # Look for companies that maintained performance during 2008-2009, 2020, etc.
            revenue_volatility = statistics.stdev(revenues) / statistics.mean(revenues) if statistics.mean(revenues) > 0 else float('inf')
            
            if revenue_volatility < 0.15:  # Low volatility suggests cycle resilience
                score += 2
                details.append("Low revenue volatility - cycle-resistant business")
            elif revenue_volatility < 0.25:
                score += 1
                details.append("Moderate revenue stability across cycles")

    # 2. Early cycle positioning (commodity/infrastructure)
    if ticker:
        commodity_early_cycle = ['FCX', 'AA', 'X', 'CLF', 'NUE', 'CAT', 'DE', 'UNP', 'CSX']
        if ticker in commodity_early_cycle:
            score += 2
            details.append("Early economic cycle positioning - commodity/infrastructure")

    # 3. Margin cycle analysis
    if len(financial_line_items) >= 5 and metrics:
        operating_margins = [fi.operating_income / fi.revenue if fi.operating_income and fi.revenue and fi.revenue > 0 else 0 
                           for fi in financial_line_items]
        
        if len(operating_margins) >= 5:
            current_margin = operating_margins[0]
            avg_margin = sum(operating_margins) / len(operating_margins)
            
            if current_margin < avg_margin * 0.8:  # Currently depressed margins
                score += 2
                details.append("Currently depressed margins - potential cycle recovery opportunity")
            elif current_margin < avg_margin * 0.9:
                score += 1
                details.append("Below-average margins - possible cycle positioning")

    normalized_score = min(10, score)

    return {
        "score": normalized_score,
        "details": "; ".join(details) if details else "Limited economic cycle data"
    }


def calculate_price_performance(prices: list) -> dict:
    """Calculate various price performance metrics."""
    if not prices or len(prices) < 2:
        return {"ytd_return": 0, "volatility": 0, "max_drawdown": 0}
    
    # Calculate returns
    closes = [p.close for p in prices]
    ytd_return = (closes[0] - closes[-1]) / closes[-1] if closes[-1] > 0 else 0
    
    # Calculate volatility
    returns = [(closes[i] - closes[i+1]) / closes[i+1] for i in range(len(closes)-1) if closes[i+1] > 0]
    volatility = statistics.stdev(returns) if len(returns) > 1 else 0
    
    # Calculate max drawdown
    peak = closes[0]
    max_drawdown = 0
    for price in closes:
        if price > peak:
            peak = price
        drawdown = (peak - price) / peak
        max_drawdown = max(max_drawdown, drawdown)
    
    return {
        "ytd_return": ytd_return,
        "volatility": volatility,
        "max_drawdown": max_drawdown
    }


def generate_enhanced_rogers_output(ticker: str, analysis_data: dict, state: AgentState) -> JimRogersSignal:
    """Generate comprehensive Jim Rogers analysis using LLM reasoning."""
    
    def create_default_jim_rogers_signal():
        ticker_data = analysis_data.get(ticker, {})
        score = ticker_data.get("score", 0)
        return JimRogersSignal(
            signal="neutral", 
            confidence=30, 
            reasoning=f"Analysis completed with limited data. Overall score: {score:.1f}/10. Unable to generate detailed reasoning."
        )

    try:
        ticker_data = analysis_data[ticker]
        
        template = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are Jim Rogers, legendary global macro investor and commodities expert. Analyze investment opportunities using your proven methodology developed over 40+ years of investing around the world:

                MY CORE INVESTMENT PHILOSOPHY:
                1. "I never buy anything unless I can fill up a whole page with reasons" - Deep research is essential
                2. "Buy low, sell high" - Be contrarian when others are fearful or greedy
                3. Global Macro Focus - Understanding big picture trends that drive markets for years/decades
                4. Commodities & Real Assets - Agriculture, energy, precious metals, infrastructure are real wealth
                5. Long-term Perspective - Hold for years or decades, not months. "I'm not a trader, I'm an investor"
                6. Supply/Demand Fundamentals - Focus on real economic drivers, not financial engineering
                7. Emerging Markets - "The 19th century was Britain's, 20th century was America's, 21st century will be Asia's"
                8. Economic Cycles - Understanding boom/bust patterns and positioning accordingly
                9. Demographics & Structural Trends - Population shifts, urbanization, technology adoption
                10. Currency & Geopolitics - How global events and currency changes affect investments

                MY INVESTMENT PREFERENCES:
                STRONGLY FAVOR:
                - Commodity producers (agriculture, energy, mining, materials)
                - Infrastructure companies (railways, pipelines, utilities, ports)
                - Companies with emerging market exposure (especially Asia)
                - Businesses benefiting from demographic trends (aging, urbanization, middle class growth)
                - Companies with real assets and pricing power
                - Contrarian opportunities in beaten-down sectors/countries

                GENERALLY AVOID:
                - Overvalued growth stocks with no real assets
                - Companies with excessive debt and financial engineering
                - Sectors with unclear long-term fundamentals
                - Markets/countries with poor governance
                - Short-term trading plays

                MY ANALYSIS APPROACH:
                1. Global Macro Environment - What are the big trends affecting this investment?
                2. Supply/Demand Dynamics - Are these real business fundamentals or financial manipulation?
                3. Contrarian Opportunity - Is everyone too optimistic or pessimistic about this?
                4. Long-term Structural Position - Will this matter in 10-20 years?
                5. Real Asset Value - Does this company own/control real, tangible assets?
                6. Geographic/Demographic Exposure - How does this benefit from global trends?

                MY LANGUAGE & STYLE:
                - Speak with conviction based on decades of global investing experience
                - Reference historical examples and patterns I've observed
                - Be specific about macro trends and their investment implications
                - Show enthusiasm for true contrarian opportunities
                - Express skepticism about financial engineering and bubbles
                - Use analogies from my travels and observations around the world
                - Be direct about risks and opportunities

                CONFIDENCE LEVELS:
                - 90-100%: Perfect macro setup, strong contrarian opportunity, excellent long-term prospects
                - 70-89%: Good macro trends, solid fundamentals, reasonable contrarian value
                - 50-69%: Mixed signals, would need better price or stronger catalysts
                - 30-49%: Unclear macro picture or concerning fundamentals
                - 10-29%: Poor positioning for macro trends or significantly overvalued
                """
            ),
            (
                "human",
                """Analyze this investment opportunity for {ticker} using your Jim Rogers methodology:

                COMPREHENSIVE ANALYSIS DATA:
                Overall Score: {score:.1f}/10
                
                Global Macro Analysis: {macro_details}
                Contrarian Opportunities: {contrarian_details}  
                Commodities/Real Assets: {commodities_details}
                Supply/Demand Dynamics: {supply_demand_details}
                Demographic Trends: {demographic_details}
                Economic Cycle Position: {cycle_details}
                
                Price Performance: YTD Return {ytd_return:.1%}, Volatility {volatility:.1%}, Max Drawdown {max_drawdown:.1%}
                Market Cap: ${market_cap:,.0f} million

                Please provide your investment decision in exactly this JSON format:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": float between 0 and 100,
                  "reasoning": "string with your detailed Jim Rogers-style analysis"
                }}

                In your reasoning, be specific about:
                1. The global macro trends affecting this investment and their long-term implications
                2. Whether this represents a contrarian opportunity and why
                3. The company's exposure to commodities, real assets, or structural demographic trends
                4. Supply/demand fundamentals and real economic drivers
                5. How this fits into current economic cycles and global positioning
                6. Your assessment of long-term prospects (10-20 year view)
                7. Any risks or concerns from a macro perspective

                Write as Jim Rogers would speak - with conviction, global perspective, and focus on big-picture trends that drive markets for years.
                """
            ),
        ])

        prompt = template.invoke({
            "ticker": ticker,
            "score": ticker_data["score"],
            "macro_details": ticker_data["macro_analysis"]["details"],
            "contrarian_details": ticker_data["contrarian_analysis"]["details"],
            "commodities_details": ticker_data["commodities_analysis"]["details"],
            "supply_demand_details": ticker_data["supply_demand_analysis"]["details"],
            "demographic_details": ticker_data["demographic_analysis"]["details"],
            "cycle_details": ticker_data["cycle_analysis"]["details"],
            "ytd_return": ticker_data["price_performance"]["ytd_return"],
            "volatility": ticker_data["price_performance"]["volatility"],
            "max_drawdown": ticker_data["price_performance"]["max_drawdown"],
            "market_cap": ticker_data["market_cap"] / 1_000_000 if ticker_data["market_cap"] else 0,
        })

        return call_llm(
            prompt=prompt,
            pydantic_model=JimRogersSignal,
            agent_name="jim_rogers_agent",
            state=state,
            default_factory=create_default_jim_rogers_signal,
        )
        
    except Exception as e:
        print(f"Error in Jim Rogers analysis: {e}")
        return create_default_jim_rogers_signal() 