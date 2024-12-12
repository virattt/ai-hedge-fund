"""
Specialized agent implementations that inherit from BaseAgent.
"""

from typing import Dict, Any
import json
from .base import BaseAgent
from ..providers import BaseProvider

class SentimentAgent(BaseAgent):
    """Analyzes market sentiment using configurable AI providers."""

    def analyze_sentiment(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment from market data and insider trades.

        Args:
            state: Current workflow state containing market data

        Returns:
            Updated state with sentiment analysis
        """
        system_prompt = """
        You are a market sentiment analyst.
        Analyze the market data and insider trades to provide sentiment analysis.
        Return your analysis as JSON with the following fields:
        - sentiment_score: float between -1 (bearish) and 1 (bullish)
        - confidence: float between 0 and 1
        - reasoning: string explaining the analysis
        """

        user_prompt = f"""
        Analyze the following market data and insider trades:
        Market Data: {state.get('market_data', {})}
        """

        try:
            response = self.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            analysis = self.validate_response(response)
            if "error" in analysis:
                state["error"] = analysis["error"]
                return state
            state['sentiment_analysis'] = analysis
            return state
        except Exception as e:
            state['sentiment_analysis'] = {
                'sentiment_score': 0,
                'confidence': 0,
                'reasoning': f'Error analyzing sentiment: {str(e)}'
            }
            return state

class RiskManagementAgent(BaseAgent):
    """Evaluates portfolio risk using configurable AI providers."""

    def evaluate_risk(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate trading risk based on market conditions.

        Args:
            state: Current workflow state with market data and sentiment

        Returns:
            Updated state with risk assessment
        """
        system_prompt = """
        You are a risk management specialist.
        Evaluate trading risk based on market data and sentiment analysis.
        Return your assessment as JSON with the following fields:
        - risk_level: string (low, moderate, high)
        - position_limit: integer (maximum position size)
        - reasoning: string explaining the assessment
        """

        user_prompt = f"""
        Evaluate risk based on:
        Market Data: {state.get('market_data', {})}
        Sentiment Analysis: {state.get('sentiment_analysis', {})}
        """

        try:
            response = self.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            assessment = self.validate_response(response)
            if "error" in assessment:
                state["error"] = assessment["error"]
                return state
            state['risk_assessment'] = assessment
            return state
        except Exception as e:
            state['risk_assessment'] = {
                'risk_level': 'high',
                'position_limit': 0,
                'reasoning': f'Error evaluating risk: {str(e)}'
            }
            return state

class PortfolioManagementAgent(BaseAgent):
    """Makes final trading decisions using configurable AI providers."""

    def make_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make final trading decision based on all signals.

        Args:
            state: Current workflow state with all analyses

        Returns:
            Updated state with trading decision
        """
        system_prompt = """
        You are a portfolio manager making final trading decisions.
        Make a decision based on market data, sentiment, and risk assessment.
        Return your decision as JSON with the following fields:
        - action: string (buy, sell, hold)
        - quantity: integer
        - reasoning: string explaining the decision
        """

        user_prompt = f"""
        Make trading decision based on:
        Market Data: {state.get('market_data', {})}
        Sentiment Analysis: {state.get('sentiment_analysis', {})}
        Risk Assessment: {state.get('risk_assessment', {})}
        """

        try:
            response = self.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            decision = self.validate_response(response)
            if "error" in decision:
                state["error"] = decision["error"]
                return state
            state['trading_decision'] = decision
            return state
        except Exception as e:
            state['trading_decision'] = {
                'action': 'hold',
                'quantity': 0,
                'reasoning': f'Error making decision: {str(e)}'
            }
            return state
