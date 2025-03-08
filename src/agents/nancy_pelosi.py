from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal
from utils.progress import progress
from utils.llm import call_llm

from tools.api import get_financial_metrics, get_market_cap, search_line_items, get_company_news, get_insider_trades


class NancyPelosiSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def nancy_pelosi_agent(state: AgentState):
    """
    Analyzes stocks using congressional trading patterns and policy insights:
    1. Companies likely to benefit from upcoming legislation and regulatory changes
    2. Government contractors and sectors with significant public sector exposure
    3. Sectors with active policy discussions and potential regulatory shifts
    4. Strategic long-term positions in market-leading companies
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    
    analysis_data = {}
    pelosi_analysis = {}
    
    for ticker in tickers:
        progress.update_status("nancy_pelosi_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5)
        
        progress.update_status("nancy_pelosi_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue", 
                "net_income",
                "outstanding_shares",
                "total_assets",
                "research_and_development",
            ],
            end_date,
            period="annual",
            limit=5,
        )
        
        progress.update_status("nancy_pelosi_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)
        
        progress.update_status("nancy_pelosi_agent", ticker, "Getting recent news")
        # Analysis of recent news for policy/regulatory mentions
        company_news = get_company_news(ticker, end_date, limit=50)
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing legislative landscape")
        legislation_analysis = analyze_legislation_impact(company_news, ticker)
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing government contract potential")
        gov_contract_analysis = analyze_government_contracts(financial_line_items, company_news)
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing policy trends")
        policy_analysis = analyze_policy_trends(company_news, ticker)
        
        # Calculate total score
        total_score = (
            legislation_analysis["score"] + 
            gov_contract_analysis["score"] + 
            policy_analysis["score"]
        )
        max_possible_score = 10
        
        # Generate trading signal
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"
        
        # Combine all analysis results
        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "legislation_analysis": legislation_analysis,
            "gov_contract_analysis": gov_contract_analysis,
            "policy_analysis": policy_analysis,
            "market_cap": market_cap,
        }
        
        progress.update_status("nancy_pelosi_agent", ticker, "Generating congressional trading analysis")
        pelosi_output = generate_pelosi_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )
        
        # Store analysis in consistent format with other agents
        pelosi_analysis[ticker] = {
            "signal": pelosi_output.signal,
            "confidence": pelosi_output.confidence,
            "reasoning": pelosi_output.reasoning,
        }
        
        progress.update_status("nancy_pelosi_agent", ticker, "Done")
    
    # Create the message
    message = HumanMessage(
        content=json.dumps(pelosi_analysis),
        name="nancy_pelosi_agent"
    )
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(pelosi_analysis, "Nancy Pelosi Agent")
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["nancy_pelosi_agent"] = pelosi_analysis
    
    return {
        "messages": [message],
        "data": state["data"]
    }


def analyze_legislation_impact(company_news: list, ticker: str) -> dict:
    """
    Analyze potential impact of legislation on company performance.
    
    Evaluates:
    - Mentions of pending bills or legislation relevant to the company
    - Regulatory changes affecting the company's sector
    - Congressional focus areas that may impact business operations
    """
    score = 0
    details = []
    
    # Keywords related to legislation
    legislation_keywords = [
        'bill', 'legislation', 'congress', 'senate', 'house of representatives',
        'regulation', 'regulatory', 'policy', 'hearing', 'committee', 'subcommittee',
        'vote', 'passed', 'law', 'executive order', 'oversight'
    ]
    
    relevant_news_count = 0
    positive_legislation_count = 0
    negative_legislation_count = 0
    
    for news in company_news:
        title_lower = news.title.lower()
        
        # Check if news contains legislation keywords
        if any(keyword in title_lower for keyword in legislation_keywords):
            relevant_news_count += 1
            
            # Simple sentiment analysis based on news sentiment
            if news.sentiment == "positive":
                positive_legislation_count += 1
            elif news.sentiment == "negative":
                negative_legislation_count += 1
    
    # Score based on volume of legislation-related news
    if relevant_news_count > 10:
        score += 2
        details.append(f"Significant legislative activity: {relevant_news_count} relevant news items indicating potential policy shifts")
    elif relevant_news_count > 5:
        score += 1
        details.append(f"Moderate legislative activity: {relevant_news_count} relevant news items suggesting policy attention")
    
    # Score based on sentiment of legislation-related news
    net_sentiment = positive_legislation_count - negative_legislation_count
    if net_sentiment > 3:
        score += 3
        details.append(f"Highly favorable legislative outlook: +{net_sentiment} - positions before public awareness advisable")
    elif net_sentiment > 0:
        score += 2
        details.append(f"Positive legislative outlook: +{net_sentiment} - early strategic positioning recommended")
    elif net_sentiment < -3:
        score -= 2
        details.append(f"Highly unfavorable legislative outlook: {net_sentiment} - consider defensive positioning")
    elif net_sentiment < 0:
        score -= 1
        details.append(f"Negative legislative outlook: {net_sentiment} - portfolio adjustments may be prudent")
    
    return {
        "score": max(0, score),  # Ensure score is not negative
        "details": "; ".join(details) if details else "No significant legislative impacts detected",
        "relevant_news_count": relevant_news_count,
        "positive_legislation_count": positive_legislation_count,
        "negative_legislation_count": negative_legislation_count
    }


def analyze_government_contracts(financial_line_items: list, company_news: list) -> dict:
    """
    Analyze potential government contract opportunities and public sector revenue
    
    Evaluates company news and financial data for indicators of government
    contract activity and public sector business relationships.
    """
    score = 0
    details = []
    
    # Keywords related to government contracts
    contract_keywords = [
        'contract', 'awarded', 'government', 'federal', 'pentagon', 'defense',
        'department of', 'agency', 'grant', 'funding', 'appropriation', 'budget',
        'military', 'procurement', 'infrastructure', 'stimulus', 'project'
    ]
    
    contract_news_count = 0
    large_contracts = 0
    
    for news in company_news:
        title_lower = news.title.lower()
        
        # Check if news contains contract keywords
        if any(keyword in title_lower for keyword in contract_keywords):
            contract_news_count += 1
            
            # Very basic estimate for large contract news
            if any(x in title_lower for x in ['billion', 'million', 'major', 'large', 'significant']):
                large_contracts += 1
    
    # Score based on potential government contracts in news
    if large_contracts > 2:
        score += 4
        details.append(f"Significant government contract opportunities: {large_contracts} major contracts mentioned")
    elif contract_news_count > 5:
        score += 2
        details.append(f"Moderate government contract activity: {contract_news_count} contract-related news items")
    elif contract_news_count > 0:
        score += 1
        details.append(f"Some government contract activity: {contract_news_count} contract-related news items")
    
    # Advanced analysis would examine financials for government contract revenue
    
    return {
        "score": score,
        "details": "; ".join(details) if details else "No significant government contract activity detected",
        "contract_news_count": contract_news_count,
        "large_contracts": large_contracts
    }


def analyze_policy_trends(company_news: list, ticker: str) -> dict:
    """
    Analyze broader policy trends that might affect the company's prospects
    
    Examines sector-wide policy changes, regulatory environments,
    and government priorities that could impact future performance.
    """
    score = 0
    details = []
    
    # Keywords for policy areas often subject to government action
    policy_areas = {
        'technology': ['tech', 'technology', 'software', 'data', 'privacy', 'cybersecurity', 'ai', 'artificial intelligence'],
        'healthcare': ['health', 'medical', 'medicare', 'medicaid', 'affordable care', 'pharma', 'drug', 'vaccine'],
        'finance': ['bank', 'financial', 'credit', 'loan', 'interest rate', 'federal reserve', 'treasury'],
        'energy': ['energy', 'oil', 'gas', 'renewable', 'solar', 'wind', 'climate', 'carbon', 'emissions'],
        'infrastructure': ['infrastructure', 'construction', 'transportation', 'highway', 'bridge', 'road', 'rail'],
        'defense': ['defense', 'military', 'security', 'weapons', 'contractor', 'army', 'navy', 'air force']
    }
    
    # Count news by policy area
    policy_area_counts = {area: 0 for area in policy_areas}
    trending_policy_areas = []
    
    for news in company_news:
        title_lower = news.title.lower()
        
        for area, keywords in policy_areas.items():
            if any(keyword in title_lower for keyword in keywords):
                policy_area_counts[area] += 1
    
    # Identify trending policy areas (areas with significant news coverage)
    for area, count in policy_area_counts.items():
        if count > 5:
            trending_policy_areas.append(area)
            score += 1
            details.append(f"Significant {area} policy activity: {count} news items - potential strategic advantage")
        elif count > 2:
            trending_policy_areas.append(area)
            score += 0.5
            details.append(f"Some {area} policy activity: {count} news items - worth monitoring closely")
    
    # Additional score for sectors with current legislative momentum
    priority_sectors = ['infrastructure', 'technology', 'healthcare', 'energy']
    if any(area in priority_sectors for area in trending_policy_areas):
        score += 2
        details.append(f"Company in high-priority policy sectors: {[area for area in trending_policy_areas if area in priority_sectors]} - favorable positioning")
    
    return {
        "score": score,
        "details": "; ".join(details) if details else "No significant policy trends affecting company",
        "policy_area_counts": policy_area_counts,
        "trending_policy_areas": trending_policy_areas
    }


def generate_pelosi_output(
    ticker: str,
    analysis_data: dict[str, any],
    model_name: str,
    model_provider: str,
) -> NancyPelosiSignal:
    """Generate congressional trading style investment decision from LLM."""
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a strategic congressional trading analyst who evaluates stocks based on policy insights:

            1. Companies positioned to benefit from upcoming legislation and regulation
            2. Government contractors and sectors with significant federal spending
            3. Sectors receiving priority in current policy discussions
            4. Companies with strategic importance to national initiatives
            5. Blue-chip companies with strong government relationships
            
            Key investment principles:
            - Identify companies well-positioned for legislative and regulatory tailwinds
            - Focus on sectors currently receiving policy attention and funding
            - Recognize early policy signals before they become widely understood
            - Consider timing of major policy announcements for optimal positioning
            - Maintain a strategic view of government priorities and spending
            
            Your analysis should leverage deep understanding of policy processes and government operations for optimal investment outcomes. Focus on information advantage regarding policy directions and regulatory changes.
            """
        ),
        (
            "human",
            """Based on the following congressional trading style analysis, create an investment signal:

            Analysis Data for {ticker}:
            {analysis_data}

            Return the trading signal in the following JSON format:
            {{
              "signal": "bullish/bearish/neutral",
              "confidence": float (0-100),
              "reasoning": "string"
            }}
            """
        )
    ])

    # Generate the prompt
    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker
    })

    # Create default factory for NancyPelosiSignal
    def create_default_signal():
        return NancyPelosiSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=NancyPelosiSignal,
        agent_name="nancy_pelosi_agent",
        default_factory=create_default_signal,
    ) 