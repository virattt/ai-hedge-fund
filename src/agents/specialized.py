"""
Specialized agent implementations that inherit from BaseAgent.
"""

from typing import Dict, Any, Optional, List
from ..providers import ModelProvider
from .base import BaseAgent
from langchain_core.messages import HumanMessage
import json

class SentimentAgent(BaseAgent):
    """Analyzes market sentiment using configurable AI providers."""

    def analyze_sentiment(self, insider_trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze sentiment from insider trades.

        Args:
            insider_trades: List of insider trading data

        Returns:
            Dict containing sentiment analysis
        """
        system_prompt = """
        You are a market sentiment analyst.
        Your job is to analyze the insider trades of a company and provide a sentiment analysis.
        The insider trades are a list of transactions made by company insiders.
        - If the insider is buying, the sentiment may be bullish.
        - If the insider is selling, the sentiment may be bearish.
        - If the insider is neutral, the sentiment may be neutral.
        The sentiment is amplified if the insider is buying or selling a large amount of shares.
        Also, the sentiment is amplified if the insider is a high-level executive (e.g. CEO, CFO, etc.) or board member.
        For each insider trade, provide the following in your output (as a JSON):
        "sentiment": <bullish | bearish | neutral>,
        "reasoning": <concise explanation of the decision>
        """

        user_prompt = f"""
        Based on the following insider trades, provide your sentiment analysis.
        {insider_trades}

        Only include the sentiment and reasoning in your JSON output. Do not include any JSON markdown.
        """

        try:
            result = self.generate_response(system_prompt, user_prompt)
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "sentiment": "neutral",
                "reasoning": "Unable to parse JSON output of market sentiment analysis",
            }

class RiskManagementAgent(BaseAgent):
    """Evaluates portfolio risk using configurable AI providers."""

    def evaluate_risk(
        self,
        quant_signal: Dict[str, Any],
        fundamental_signal: Dict[str, Any],
        sentiment_signal: Dict[str, Any],
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate portfolio risk and recommend position sizing.

        Args:
            quant_signal: Signal from quantitative analysis
            fundamental_signal: Signal from fundamental analysis
            sentiment_signal: Signal from sentiment analysis
            portfolio: Current portfolio state

        Returns:
            Dict containing risk assessment
        """
        system_prompt = """You are a risk management specialist.
        Your job is to take a look at the trading analysis and
        evaluate portfolio exposure and recommend position sizing.
        Provide the following in your output (as a JSON):
        "max_position_size": <float greater than 0>,
        "risk_score": <integer between 1 and 10>,
        "trading_action": <buy | sell | hold>,
        "reasoning": <concise explanation of the decision>
        """

        user_prompt = f"""Based on the trading analysis below, provide your risk assessment.

        Quant Analysis Trading Signal: {quant_signal}
        Fundamental Analysis Trading Signal: {fundamental_signal}
        Sentiment Analysis Trading Signal: {sentiment_signal}
        Here is the current portfolio:
        Portfolio:
        Cash: {portfolio['cash']:.2f}
        Current Position: {portfolio['stock']} shares

        Only include the max position size, risk score, trading action, and reasoning in your JSON output. Do not include any JSON markdown.
        """

        result = self.generate_response(system_prompt, user_prompt)
        return json.loads(result)

class PortfolioManagementAgent(BaseAgent):
    """Makes final trading decisions using configurable AI providers."""

    def make_decision(
        self,
        quant_signal: Dict[str, Any],
        fundamental_signal: Dict[str, Any],
        sentiment_signal: Dict[str, Any],
        risk_signal: Dict[str, Any],
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make final trading decision based on all signals.

        Args:
            quant_signal: Signal from quantitative analysis
            fundamental_signal: Signal from fundamental analysis
            sentiment_signal: Signal from sentiment analysis
            risk_signal: Signal from risk management
            portfolio: Current portfolio state

        Returns:
            Dict containing trading decision
        """
        system_prompt = """You are a portfolio manager making final trading decisions.
        Your job is to make a trading decision based on the team's analysis.
        Provide the following in your output:
        - "action": "buy" | "sell" | "hold",
        - "quantity": <positive integer>
        - "reasoning": <concise explanation of the decision>
        Only buy if you have available cash.
        The quantity that you buy must be less than or equal to the max position size.
        Only sell if you have shares in the portfolio to sell.
        The quantity that you sell must be less than or equal to the current position."""

        user_prompt = f"""Based on the team's analysis below, make your trading decision.

        Quant Analysis Trading Signal: {quant_signal}
        Fundamental Analysis Trading Signal: {fundamental_signal}
        Sentiment Analysis Trading Signal: {sentiment_signal}
        Risk Management Trading Signal: {risk_signal}

        Here is the current portfolio:
        Portfolio:
        Cash: {portfolio['cash']:.2f}
        Current Position: {portfolio['stock']} shares

        Only include the action, quantity, and reasoning in your output as JSON. Do not include any JSON markdown.

        Remember, the action must be either buy, sell, or hold.
        You can only buy if you have available cash.
        You can only sell if you have shares in the portfolio to sell.
        """

        result = self.generate_response(system_prompt, user_prompt)
        return json.loads(result)
