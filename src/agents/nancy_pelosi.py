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
    print(f"\n[DEBUG] Nancy Pelosi Agent Starting")
    print(f"[DEBUG] Input state: {json.dumps(state, default=str, indent=2)}")
    
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    
    print(f"[DEBUG] Processing tickers: {tickers}, end_date: {end_date}")
    
    analysis_data = {}
    pelosi_analysis = {}
    
    for ticker in tickers:
        print(f"\n[DEBUG] --- Processing ticker: {ticker} ---")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Fetching financial metrics")
        # Fetch required data
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5)
        print(f"[DEBUG] Financial metrics: {len(metrics)} records retrieved")
        if metrics:
            print(f"[DEBUG] Most recent metrics: {metrics[0].model_dump()}")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Gathering financial line items")
        try:
            print(f"[DEBUG] Requesting line items for {ticker}")
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
            print(f"[DEBUG] Line items: {len(financial_line_items)} records retrieved")
            if financial_line_items:
                print(f"[DEBUG] Most recent line items: {financial_line_items[0].model_dump()}")
        except Exception as e:
            print(f"[DEBUG] ERROR fetching line items: {str(e)}")
            raise e
        
        progress.update_status("nancy_pelosi_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)
        print(f"[DEBUG] Market cap: {market_cap}")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Getting recent news")
        # Analysis of recent news for policy/regulatory mentions
        company_news = get_company_news(ticker, end_date, limit=50)
        print(f"[DEBUG] Company news: {len(company_news)} articles retrieved")
        if company_news:
            print(f"[DEBUG] Most recent news: {company_news[0].title} ({company_news[0].date})")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing legislative landscape")
        print(f"[DEBUG] Starting legislation impact analysis...")
        legislation_analysis = analyze_legislation_impact(company_news, ticker)
        print(f"[DEBUG] Legislation analysis results: {legislation_analysis}")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing government contract potential")
        print(f"[DEBUG] Starting government contract analysis...")
        gov_contract_analysis = analyze_government_contracts(financial_line_items, company_news)
        print(f"[DEBUG] Government contract analysis results: {gov_contract_analysis}")
        
        progress.update_status("nancy_pelosi_agent", ticker, "Analyzing policy trends")
        print(f"[DEBUG] Starting policy trends analysis...")
        policy_analysis = analyze_policy_trends(company_news, ticker)
        print(f"[DEBUG] Policy analysis results: {policy_analysis}")
        
        # Calculate total score
        total_score = (
            legislation_analysis["score"] + 
            gov_contract_analysis["score"] + 
            policy_analysis["score"]
        )
        max_possible_score = 10
        
        print(f"[DEBUG] Score calculation: {legislation_analysis['score']} (legislation) + "
              f"{gov_contract_analysis['score']} (contracts) + {policy_analysis['score']} (policy) = "
              f"{total_score} / {max_possible_score}")
        
        # Generate trading signal
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"
        
        print(f"[DEBUG] Initial signal calculation: {signal} (score: {total_score})")
        
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
        print(f"[DEBUG] Sending analysis to LLM for final output...")
        pelosi_output = generate_pelosi_output(
            ticker=ticker,
            analysis_data=analysis_data,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )
        
        print(f"[DEBUG] LLM output for {ticker}: {pelosi_output.model_dump()}")
        
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
    
    print(f"[DEBUG] Final message content: {message.content}")
    
    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(pelosi_analysis, "Nancy Pelosi Agent")
    
    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["nancy_pelosi_agent"] = pelosi_analysis
    
    print(f"[DEBUG] Nancy Pelosi Agent Completed")
    
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
    print(f"[DEBUG] Analyzing legislation impact for {ticker} with {len(company_news)} news items")
    
    score = 0
    details = []
    
    # Keywords related to legislation
    legislation_keywords = [
        'bill', 'legislation', 'congress', 'senate', 'house of representatives',
        'regulation', 'regulatory', 'policy', 'hearing', 'committee', 'subcommittee',
        'vote', 'passed', 'law', 'executive order', 'oversight'
    ]
    
    print(f"[DEBUG] Using legislation keywords: {legislation_keywords}")
    
    relevant_news_count = 0
    positive_legislation_count = 0
    negative_legislation_count = 0
    
    for i, news in enumerate(company_news):
        title_lower = news.title.lower()
        
        # Check if news contains legislation keywords
        matched_keywords = [k for k in legislation_keywords if k in title_lower]
        if matched_keywords:
            relevant_news_count += 1
            print(f"[DEBUG] Matched legislation news ({i}): '{news.title}' with keywords: {matched_keywords}")
            
            # Simple sentiment analysis based on news sentiment
            if news.sentiment == "positive":
                positive_legislation_count += 1
                print(f"[DEBUG]   Sentiment: positive")
            elif news.sentiment == "negative":
                negative_legislation_count += 1
                print(f"[DEBUG]   Sentiment: negative")
            else:
                print(f"[DEBUG]   Sentiment: neutral or unknown ({news.sentiment})")
    
    print(f"[DEBUG] Found {relevant_news_count} legislation-related news items "
          f"(Positive: {positive_legislation_count}, Negative: {negative_legislation_count})")
    
    # Score based on volume of legislation-related news
    if relevant_news_count > 10:
        score += 2
        details.append(f"Significant legislative activity: {relevant_news_count} relevant news items indicating potential policy shifts")
        print(f"[DEBUG] Volume score: +2 (>10 news items)")
    elif relevant_news_count > 5:
        score += 1
        details.append(f"Moderate legislative activity: {relevant_news_count} relevant news items suggesting policy attention")
        print(f"[DEBUG] Volume score: +1 (>5 news items)")
    else:
        print(f"[DEBUG] Volume score: 0 ({relevant_news_count} news items)")
    
    # Score based on sentiment of legislation-related news
    net_sentiment = positive_legislation_count - negative_legislation_count
    print(f"[DEBUG] Net sentiment: {net_sentiment}")
    
    if net_sentiment > 3:
        score += 3
        details.append(f"Highly favorable legislative outlook: +{net_sentiment} - positions before public awareness advisable")
        print(f"[DEBUG] Sentiment score: +3 (highly favorable)")
    elif net_sentiment > 0:
        score += 2
        details.append(f"Positive legislative outlook: +{net_sentiment} - early strategic positioning recommended")
        print(f"[DEBUG] Sentiment score: +2 (positive)")
    elif net_sentiment < -3:
        score -= 2
        details.append(f"Highly unfavorable legislative outlook: {net_sentiment} - consider defensive positioning")
        print(f"[DEBUG] Sentiment score: -2 (highly unfavorable)")
    elif net_sentiment < 0:
        score -= 1
        details.append(f"Negative legislative outlook: {net_sentiment} - portfolio adjustments may be prudent")
        print(f"[DEBUG] Sentiment score: -1 (negative)")
    else:
        print(f"[DEBUG] Sentiment score: 0 (neutral)")
    
    final_score = max(0, score)  # Ensure score is not negative
    print(f"[DEBUG] Final legislation score: {final_score} (raw score: {score})")
    
    return {
        "score": final_score,
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
    print(f"[DEBUG] Analyzing government contracts with {len(company_news)} news items "
          f"and {len(financial_line_items)} financial line items")
    
    score = 0
    details = []
    
    # Keywords related to government contracts
    contract_keywords = [
        'contract', 'awarded', 'government', 'federal', 'pentagon', 'defense',
        'department of', 'agency', 'grant', 'funding', 'appropriation', 'budget',
        'military', 'procurement', 'infrastructure', 'stimulus', 'project'
    ]
    
    print(f"[DEBUG] Using contract keywords: {contract_keywords}")
    
    contract_news_count = 0
    large_contracts = 0
    
    for i, news in enumerate(company_news):
        title_lower = news.title.lower()
        
        # Check if news contains contract keywords
        matched_keywords = [k for k in contract_keywords if k in title_lower]
        if matched_keywords:
            contract_news_count += 1
            print(f"[DEBUG] Matched contract news ({i}): '{news.title}' with keywords: {matched_keywords}")
            
            # Very basic estimate for large contract news
            large_contract_keywords = ['billion', 'million', 'major', 'large', 'significant']
            large_matches = [k for k in large_contract_keywords if k in title_lower]
            if large_matches:
                large_contracts += 1
                print(f"[DEBUG]   Large contract indicators: {large_matches}")
    
    print(f"[DEBUG] Found {contract_news_count} contract-related news items "
          f"(Large contracts: {large_contracts})")
    
    # Score based on potential government contracts in news
    if large_contracts > 2:
        score += 4
        details.append(f"Significant government contract opportunities: {large_contracts} major contracts mentioned")
        print(f"[DEBUG] Contract score: +4 (>2 large contracts)")
    elif contract_news_count > 5:
        score += 2
        details.append(f"Moderate government contract activity: {contract_news_count} contract-related news items")
        print(f"[DEBUG] Contract score: +2 (>5 contract news)")
    elif contract_news_count > 0:
        score += 1
        details.append(f"Some government contract activity: {contract_news_count} contract-related news items")
        print(f"[DEBUG] Contract score: +1 (some contract news)")
    else:
        print(f"[DEBUG] Contract score: 0 (no contract news)")
    
    print(f"[DEBUG] Final government contract score: {score}")
    
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
    print(f"[DEBUG] Analyzing policy trends for {ticker} with {len(company_news)} news items")
    
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
    
    print(f"[DEBUG] Using policy areas: {list(policy_areas.keys())}")
    
    # Count news by policy area
    policy_area_counts = {area: 0 for area in policy_areas}
    trending_policy_areas = []
    
    for i, news in enumerate(company_news):
        title_lower = news.title.lower()
        
        for area, keywords in policy_areas.items():
            matched_keywords = [k for k in keywords if k in title_lower]
            if matched_keywords:
                policy_area_counts[area] += 1
                print(f"[DEBUG] Matched policy news ({i}): '{news.title}' with area: {area}, keywords: {matched_keywords}")
    
    print(f"[DEBUG] Policy area counts: {policy_area_counts}")
    
    # Identify trending policy areas (areas with significant news coverage)
    for area, count in policy_area_counts.items():
        if count > 5:
            trending_policy_areas.append(area)
            score += 1
            details.append(f"Significant {area} policy activity: {count} news items - potential strategic advantage")
            print(f"[DEBUG] {area} score: +1 (significant coverage: {count} items)")
        elif count > 2:
            trending_policy_areas.append(area)
            score += 0.5
            details.append(f"Some {area} policy activity: {count} news items - worth monitoring closely")
            print(f"[DEBUG] {area} score: +0.5 (moderate coverage: {count} items)")
        else:
            print(f"[DEBUG] {area} score: 0 (limited coverage: {count} items)")
    
    print(f"[DEBUG] Trending policy areas: {trending_policy_areas}")
    
    # Additional score for sectors with current legislative momentum
    priority_sectors = ['infrastructure', 'technology', 'healthcare', 'energy']
    priority_matches = [area for area in trending_policy_areas if area in priority_sectors]
    
    if priority_matches:
        score += 2
        details.append(f"Company in high-priority policy sectors: {priority_matches} - favorable positioning")
        print(f"[DEBUG] Priority sector bonus: +2 (matches: {priority_matches})")
    else:
        print(f"[DEBUG] No priority sector matches found")
    
    print(f"[DEBUG] Final policy trends score: {score}")
    
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
    print(f"[DEBUG] Generating Pelosi output for {ticker} using {model_provider} {model_name}")
    
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
    
    print(f"[DEBUG] Generated prompt for LLM:\n{prompt.messages[0].content}\n---\n{prompt.messages[1].content}")

    # Create default factory for NancyPelosiSignal
    def create_default_signal():
        print(f"[DEBUG] Using default signal (error occurred)")
        return NancyPelosiSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    # Get LLM response
    try:
        result = call_llm(
            prompt=prompt,
            model_name=model_name,
            model_provider=model_provider,
            pydantic_model=NancyPelosiSignal,
            agent_name="nancy_pelosi_agent",
            default_factory=create_default_signal,
        )
        print(f"[DEBUG] LLM response: {result.model_dump()}")
        return result
    except Exception as e:
        print(f"[DEBUG] Error calling LLM: {str(e)}")
        return create_default_signal() 