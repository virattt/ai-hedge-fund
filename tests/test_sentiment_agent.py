import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

from src.agents.sentiment import sentiment_analyst_agent
from src.graph.state import AgentState


class TestSentimentAgent:
    """Test suite for the sentiment analyst agent."""

    @pytest.fixture
    def mock_agent_state(self):
        """Create a mock agent state for testing."""
        return {
            "data": {
                "end_date": "2024-01-01",
                "tickers": ["AAPL", "GOOGL"],
                "analyst_signals": {}
            },
            "metadata": {
                "show_reasoning": False
            }
        }

    @pytest.fixture
    def mock_news_data(self):
        """Create mock news data for testing."""
        return [
            {
                "title": "Apple Reports Strong Q4 Earnings",
                "content": "Apple Inc. reported better than expected quarterly earnings driven by strong iPhone sales.",
                "sentiment": "positive",
                "confidence": 0.85,
                "source": "Reuters",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "title": "Google Faces Regulatory Challenges",
                "content": "Alphabet's Google subsidiary faces new regulatory scrutiny in European markets.",
                "sentiment": "negative",
                "confidence": 0.75,
                "source": "Bloomberg",
                "timestamp": "2024-01-01T09:00:00Z"
            },
            {
                "title": "Tech Stocks Mixed in Early Trading",
                "content": "Technology stocks showed mixed performance in early market trading.",
                "sentiment": "neutral",
                "confidence": 0.60,
                "source": "CNBC",
                "timestamp": "2024-01-01T08:00:00Z"
            }
        ]

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_analyst_success(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state, mock_news_data):
        """Test successful sentiment analysis."""
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = mock_news_data
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        assert len(result["messages"]) == 1
        
        # Verify API calls
        mock_get_news.assert_called()
        mock_get_api_key.assert_called_once()
        
        # Verify progress updates were called
        assert mock_progress.update_status.call_count > 0

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_analyst_no_news_data(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test handling when no news data is available."""
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = []
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        
        # Verify the analysis contains empty results for failed ticker
        analyst_signals = result["data"]["analyst_signals"]["sentiment_analyst_agent"]
        assert "AAPL" not in analyst_signals  # Should be skipped due to no data

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    @patch('src.agents.sentiment.show_agent_reasoning')
    def test_sentiment_analyst_with_reasoning(self, mock_show_reasoning, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state, mock_news_data):
        """Test sentiment analysis with reasoning enabled."""
        # Enable reasoning
        mock_agent_state["metadata"]["show_reasoning"] = True
        
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = mock_news_data
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Verify reasoning was displayed
        mock_show_reasoning.assert_called_once()

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_positive_sentiment_analysis(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test positive sentiment analysis."""
        # Create positive news data
        positive_news = [
            {
                "title": "Apple Stock Surges on Positive Outlook",
                "content": "Apple shares rose significantly after positive analyst ratings.",
                "sentiment": "positive",
                "confidence": 0.90,
                "source": "WSJ",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "title": "Apple Announces New Product Launch",
                "content": "Apple announced innovative new products expected to drive growth.",
                "sentiment": "positive",
                "confidence": 0.85,
                "source": "TechCrunch",
                "timestamp": "2024-01-01T09:00:00Z"
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = positive_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify bullish sentiment signal
        assert aapl_analysis["signal"] in ["bullish", "strong_bullish"]
        assert aapl_analysis["confidence"] > 70

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_negative_sentiment_analysis(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test negative sentiment analysis."""
        # Create negative news data
        negative_news = [
            {
                "title": "Apple Faces Regulatory Scrutiny",
                "content": "Apple is facing increased regulatory pressure over App Store policies.",
                "sentiment": "negative",
                "confidence": 0.85,
                "source": "Reuters",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "title": "Apple Sales Decline Expected",
                "content": "Analysts predict declining iPhone sales in upcoming quarter.",
                "sentiment": "negative",
                "confidence": 0.80,
                "source": "Bloomberg",
                "timestamp": "2024-01-01T09:00:00Z"
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = negative_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify bearish sentiment signal
        assert aapl_analysis["signal"] in ["bearish", "strong_bearish"]
        assert aapl_analysis["confidence"] > 70

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_mixed_sentiment_analysis(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state, mock_news_data):
        """Test mixed sentiment analysis."""
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = mock_news_data
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify signal exists and is reasonable
        assert aapl_analysis["signal"] in ["bullish", "bearish", "neutral"]
        assert "confidence" in aapl_analysis
        assert "reasoning" in aapl_analysis

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_confidence_weighting(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test sentiment confidence weighting."""
        # Create news with varying confidence levels
        mixed_confidence_news = [
            {
                "title": "Apple Positive News",
                "content": "Positive development for Apple.",
                "sentiment": "positive",
                "confidence": 0.95,  # High confidence
                "source": "Reuters",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "title": "Apple Negative News",
                "content": "Negative development for Apple.",
                "sentiment": "negative",
                "confidence": 0.30,  # Low confidence
                "source": "Unknown",
                "timestamp": "2024-01-01T09:00:00Z"
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = mixed_confidence_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Should favor high confidence positive sentiment
        assert aapl_analysis["signal"] in ["bullish", "neutral"]

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key straightaway')
ously return value for get_api_key_from_state
    @patch('src.agents.sentiment.progress')
    def test_multiple_tickers_sentiment(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test sentiment analysis for multiple tickers."""
        # Create different news for each ticker
        aapl_news = [
            {
                "title": "Apple Good News",
                "content": "Positive developments at Apple.",
                "sentiment": "positive",
                "confidence": 0.80,
                "source": "Reuters",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
        
        googl_news = [
            {
                "title": "Google Bad News",
                "content": "Challenges facing Google.",
                "sentiment": "negative",
                "confidence": 0.75,
                "source": "Bloomberg",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.side_effect = [aapl_news, googl_news]
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        
        # Verify both tickers were analyzed
        assert "AAPL" in analysis
        assert "GOOGL" in analysis
        
        # Verify different signals
        assert analysis["AAPL"]["signal"] in ["bullish", "strong_bullish"]
        assert analysis["GOOGL"]["signal"] in ["bearish", "strong_bearish"]

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_time_decay(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test sentiment time decay weighting."""
        # Create news with different timestamps
        time_weighted_news = [
            {
                "title": "Recent Apple News",
                "content": "Very recent positive development.",
                "sentiment": "positive",
                "confidence": 0.70,
                "source": "Reuters",
                "timestamp": "2024-01-01T10:00:00Z"  # Recent
            },
            {
                "title": "Old Apple News",
                "content": "Older negative development.",
                "sentiment": "negative",
                "confidence": 0.80,
                "source": "Bloomberg",
                "timestamp": "2023-12-01T10:00:00Z"  # Older
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = time_weighted_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Should favor recent news even if confidence is lower
        assert aapl_analysis["signal"] in ["bullish", "neutral"]

    def test_sentiment_signal_aggregation(self):
        """Test sentiment signal aggregation logic."""
        # Test various sentiment combinations
        test_cases = [
            (["positive", "positive", "positive"], "bullish"),
            (["negative", "negative", "negative"], "bearish"),
            (["positive", "negative", "neutral"], "neutral"),
            (["positive", "positive", "negative"], "bullish"),
            (["negative", "negative", "positive"], "bearish"),
        ]
        
        for sentiments, expected_signaljm in test_cases:
            # Simple aggregation logic
            positive_count = sentiments.count("positive")
            negative_count = sentiments.count("negative")
            neutral_count = sentiments.count("neutral")
            
            if positive_count > negative_count:
                signal = "bullish"
            elif negative_count > positive_count:
                signal = "bearish"
            else:
                signal = "neutral"
            
            assert signal == expected_signal

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_source_credibility(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test sentiment source credibility weighting."""
        # Create news from different sources
        source_weighted_news = [
            {
                "title": "Apple News from Credible Source",
                "content": "Positive development reported by major outlet.",
                "sentiment": "positive",
                "confidence": 0.70,
                "source": "Reuters",  # High credibility
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "title": "Apple News from Less Credible Source",
                "content": "Negative development reported by unknown source.",
                "sentiment": "negative",
                "confidence": 0.80,
                "source": "UnknownBlog",  # Low credibility
                "timestamp": "2024-01-01T09:00:00Z"
            }
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = source_weighted_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Should favor credible source even with lower confidence
        assert aapl_analysis["signal"] in ["bullish", "neutral"]

    @patch('src.agents.sentiment.get_news_sentiment')
    @patch('src.agents.sentiment.get_api_key_from_state')
    @patch('src.agents.sentiment.progress')
    def test_sentiment_volume_analysis(self, mock_progress, mock_get_api_key, mock_get_news, mock_agent_state):
        """Test sentiment volume analysis."""
        # Create high volume of positive news
        high_volume_news = [
            {
                "title": f"Apple Positive News {i}",
                "content": f"Positive development {i} for Apple.",
                "sentiment": "positive",
                "confidence": 0.70,
                "source": "Reuters",
                "timestamp": f"2024-01-{(i%28)+1:02d}T10:00:00Z"
            }
            for i in range(10)
        ]
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_news.return_value = high_volume_news
        
        # Call the function
        result = sentiment_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # High volume of positive news should result in strong signal
        assert aapl_analysis["signal"] in ["bullish", "strong_bullish"]
        assert aapl_analysis["confidence"] > 70


if __name__ == "__main__":
    pytest.main([__file__])
