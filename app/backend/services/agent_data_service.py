"""
Service for extracting and saving agent analysis data to the database.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class AgentDataService:
    """Service for handling agent analysis data extraction and formatting."""
    
    @staticmethod
    def extract_analyst_signals_summary(analyst_signals: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Extract summary data (signal, confidence, reasoning) from analyst_signals.
        
        Args:
            analyst_signals: Dictionary with structure {agent_id: {ticker: {signal, confidence, reasoning, ...}}}
        
        Returns:
            Formatted dictionary: {agent_id: {ticker: {signal, confidence, reasoning}}}
        """
        summary = {}
        
        for agent_id, agent_data in analyst_signals.items():
            if not isinstance(agent_data, dict):
                continue
                
            agent_summary = {}
            
            for ticker, ticker_data in agent_data.items():
                if not isinstance(ticker_data, dict):
                    continue
                
                # Extract only the summary fields we care about
                ticker_summary = {
                    "signal": ticker_data.get("signal"),
                    "confidence": ticker_data.get("confidence"),
                    "reasoning": ticker_data.get("reasoning"),
                }
                
                # Only include if at least signal is present
                if ticker_summary.get("signal") is not None:
                    agent_summary[ticker] = ticker_summary
            
            if agent_summary:
                summary[agent_id] = agent_summary
        
        return summary
    
    @staticmethod
    def format_analyst_signals_for_db(analyst_signals: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Format analyst signals for database storage.
        This is an alias for extract_analyst_signals_summary for clarity.
        
        Args:
            analyst_signals: Raw analyst signals from state["data"]["analyst_signals"]
        
        Returns:
            Formatted summary data ready for JSON storage in database
        """
        return AgentDataService.extract_analyst_signals_summary(analyst_signals)

