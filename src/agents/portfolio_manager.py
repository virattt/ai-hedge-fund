import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from utils.progress import progress
from utils.llm import call_llm
from datetime import datetime
from llm.models import get_model, ModelProvider


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


def parse_llm_response(response_text):
    """Parse JSON from LLM response"""
    try:
        # Try to extract JSON content if it's wrapped in markdown code blocks
        if "```json" in response_text:
            start_idx = response_text.find("```json") + 7
            end_idx = response_text.find("```", start_idx)
            json_str = response_text[start_idx:end_idx].strip()
            return json.loads(json_str)
        # Try to parse the entire response as JSON
        else:
            return json.loads(response_text)
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        return {"error": "Could not parse response"}


##### Portfolio Management Agent #####
def portfolio_management_agent(state):
    """Portfolio Management Agent"""
    # In LangGraph 0.2.56, state might be a dict instead of AgentState object
    # Handle both cases for compatibility
    if isinstance(state, dict):
        data = state["data"]
        metadata = state["metadata"]
        messages = state["messages"]
    else:
        data = state.data
        metadata = state.metadata
        messages = state.messages
    
    tickers = data["tickers"]
    portfolio = data["portfolio"]
    signals = data["analyst_signals"]
    model_name = metadata.get("model_name", "gpt-4o")
    model_provider = metadata.get("model_provider", "OpenAI")
    
    # Get trade history and frequency from state 
    trade_history = data.get("trade_history", {})
    trading_frequency = data.get("trading_frequency", {})
    current_date = data.get("current_date", datetime.now().strftime("%Y-%m-%d"))
    
    # Generate prompt including trade history
    prompt = f"""You are the Portfolio Management Agent of an AI-powered hedge fund.

Current Date: {current_date}

Your role is to make the final trading decisions based on analyst recommendations and risk management guidelines.

Current Portfolio:
{json.dumps(portfolio, indent=2)}

Risk Analysis:
{json.dumps(signals.get("risk_management_agent", {}), indent=2)}

Current Analyst Signals:
{json.dumps({k: v for k, v in signals.items() if k != "risk_management_agent"}, indent=2)}

Trading Frequency Metrics:
{json.dumps(trading_frequency, indent=2)}

## Overtrading Protection Rules
1. Maximum 5 trades per day across all tickers
2. Wait at least 2 days after a trade before trading same ticker again, unless:
   - New significant information justifies immediate action
   - A clear reversal signal is present with high conviction
3. Maximum 3 trades per week per ticker
4. Today's trade count so far: {trading_frequency.get('today_trade_count', 0)}
5. Never make multiple trades in the same ticker on the same day

For each ticker, evaluate all signals and determine the optimal action:
1. "buy": Buy shares if bullish signals are strong, we have available cash, and haven't traded the ticker recently
2. "sell": Sell shares if bearish signals are strong and we own shares
3. "short": Short stock if very bearish signals exist AND we have margin capability
4. "cover": Cover short position if signals turn neutral or bullish
5. "hold": Take no action (default)

For each action, provide a quantity that:
- Respects the position limits from risk management
- Accounts for available cash
- Is proportional to the conviction level
- Considers existing positions
- Prevents overtrading/excessive turnover

Respond with JSON format with decisions for each ticker:
{{
  "TICKER1": {{
    "action": "buy"|"sell"|"short"|"cover"|"hold",
    "quantity": 10
  }},
  "TICKER2": {{ ... }}
}}
"""

    # Get reasoning and decisions from LLM
    llm = get_model(model_name, ModelProvider(model_provider))
    messages_for_llm = [
        HumanMessage(content=prompt)
    ]
    try:
        response = llm.invoke(messages_for_llm)
        reasoning = response.content
        
        # Check if we're approaching trading limits
        today_count = trading_frequency.get('today_trade_count', 0)
        max_daily_trades = 5  # Maximum allowed trades per day
        approaching_limit = today_count >= max_daily_trades - 2  # Warning if we have 3+ trades already
        
        # Parse the output as-is
        parsed_response = parse_llm_response(reasoning)
        
        # Apply overtrading protection
        if approaching_limit:
            print(f"{Fore.YELLOW}WARNING: Approaching daily trade limit ({today_count}/{max_daily_trades}){Style.RESET_ALL}")
            
            # If we're at the limit, override decisions to "hold"
            if today_count >= max_daily_trades:
                print(f"{Fore.RED}ALERT: Daily trade limit reached. Forcing HOLD on all positions.{Style.RESET_ALL}")
                for ticker in parsed_response:
                    if parsed_response[ticker]["action"] != "hold":
                        parsed_response[ticker]["action"] = "hold"
                        parsed_response[ticker]["quantity"] = 0
                        parsed_response[ticker]["override_reason"] = "Daily trade limit reached"
        
        # Check for recent trades on each ticker
        for ticker in list(parsed_response.keys()):
            ticker_history = trade_history.get(ticker, [])
            if ticker_history and isinstance(ticker_history, list) and len(ticker_history) > 0:
                first_trade = ticker_history[0]
                days_ago = first_trade.get("days_ago")
                
                if days_ago is not None and days_ago < 2:
                    # We traded this ticker in the last 2 days
                    print(f"{Fore.YELLOW}Recent trade detected for {ticker} ({days_ago} days ago){Style.RESET_ALL}")
                    
                    # Check if there's a strong consensus from multiple analysts
                    ticker_signals_count = sum(1 for k, v in signals.items() 
                                              if k != "risk_management_agent" and ticker in v)
                    strong_consensus = ticker_signals_count >= 3
                    
                    decision = parsed_response[ticker]
                    if not strong_consensus and decision["action"] != "hold":
                        decision["original_action"] = decision["action"]
                        decision["action"] = "hold"
                        decision["quantity"] = 0
                        decision["override_reason"] = f"Recent trade ({days_ago} days ago) without strong new consensus"
        
        # Convert parsed_response to string for JSON response
        final_decisions = {}
        for ticker, decision in parsed_response.items():
            final_decisions[ticker] = {
                "action": decision.get("action", "hold"),
                "quantity": decision.get("quantity", 0),
                "confidence": decision.get("confidence", 50.0)
            }
            
    except Exception as e:
        print(f"Error in portfolio management agent: {e}")
        final_decisions = {}
        reasoning = f"Error: {str(e)}"

    # If show_reasoning is enabled, print it
    if metadata.get("show_reasoning", False):
        print(f"\n{Fore.BLUE}Portfolio Management Agent Reasoning:{Style.RESET_ALL}")
        print(reasoning)

    # Return the response as a system message
    if isinstance(state, dict):
        state["messages"].append(SystemMessage(content=json.dumps(final_decisions)))
    else:
        state.messages.append(SystemMessage(content=json.dumps(final_decisions)))
        
    return state


def generate_trading_decision(
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict[str, float],
    model_name: str,
    model_provider: str,
) -> PortfolioManagerOutput:
    """Attempts to get a decision from the LLM with retry logic"""
    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
              "system",
              """You are a portfolio manager making final trading decisions based on multiple tickers.

              Trading Rules:
              - For long positions:
                * Only buy if you have available cash
                * Only sell if you currently hold long shares of that ticker
                * Sell quantity must be ≤ current long position shares
                * Buy quantity must be ≤ max_shares for that ticker
              
              - For short positions:
                * Only short if you have available margin (50% of position value required)
                * Only cover if you currently have short shares of that ticker
                * Cover quantity must be ≤ current short position shares
                * Short quantity must respect margin requirements
              
              - The max_shares values are pre-calculated to respect position limits
              - Consider both long and short opportunities based on signals
              - Maintain appropriate risk management with both long and short exposure

              Available Actions:
              - "buy": Open or add to long position
              - "sell": Close or reduce long position
              - "short": Open or add to short position
              - "cover": Close or reduce short position
              - "hold": No action

              Inputs:
              - signals_by_ticker: dictionary of ticker → signals
              - max_shares: maximum shares allowed per ticker
              - portfolio_cash: current cash in portfolio
              - portfolio_positions: current positions (both long and short)
              - current_prices: current prices for each ticker
              - margin_requirement: current margin requirement for short positions
              """,
            ),
            (
              "human",
              """Based on the team's analysis, make your trading decisions for each ticker.

              Here are the signals by ticker:
              {signals_by_ticker}

              Current Prices:
              {current_prices}

              Maximum Shares Allowed For Purchases:
              {max_shares}

              Portfolio Cash: {portfolio_cash}
              Current Positions: {portfolio_positions}
              Current Margin Requirement: {margin_requirement}

              Output strictly in JSON with the following structure:
              {{
                "decisions": {{
                  "TICKER1": {{
                    "action": "buy/sell/short/cover/hold",
                    "quantity": integer,
                    "confidence": float between 0 and 100,
                    "reasoning": "string"
                  }},
                  "TICKER2": {{
                    ...
                  }},
                  ...
                }}
              }}
              """,
            ),
        ]
    )

    # Generate the prompt
    prompt = template.invoke(
        {
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "current_prices": json.dumps(current_prices, indent=2),
            "max_shares": json.dumps(max_shares, indent=2),
            "portfolio_cash": f"{portfolio.get('cash', 0):.2f}",
            "portfolio_positions": json.dumps(portfolio.get('positions', {}), indent=2),
            "margin_requirement": f"{portfolio.get('margin_requirement', 0):.2f}",
        }
    )

    # Create default factory for PortfolioManagerOutput
    def create_default_portfolio_output():
        return PortfolioManagerOutput(decisions={ticker: PortfolioDecision(action="hold", quantity=0, confidence=0.0, reasoning="Error in portfolio management, defaulting to hold") for ticker in tickers})

    return call_llm(prompt=prompt, model_name=model_name, model_provider=model_provider, pydantic_model=PortfolioManagerOutput, agent_name="portfolio_management_agent", default_factory=create_default_portfolio_output)
