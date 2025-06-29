"""
Enhanced NLP modules for news and social media sentiment analysis.
Includes advanced sentiment analysis, entity extraction, and event detection.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import pandas as pd
from collections import defaultdict, Counter
import numpy as np

from ..data.cache import Cache
from ..data.models import CompanyNews

logger = logging.getLogger(__name__)

class SentimentScore(str, Enum):
    """Sentiment classification levels"""
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"

class NewsCategory(str, Enum):
    """News categories for classification"""
    EARNINGS = "earnings"
    PRODUCT_LAUNCH = "product_launch"
    MERGER_ACQUISITION = "merger_acquisition"  
    REGULATORY = "regulatory"
    MANAGEMENT_CHANGE = "management_change"
    PARTNERSHIP = "partnership"
    LEGAL_ISSUE = "legal_issue"
    MARKET_ANALYSIS = "market_analysis"
    GENERAL = "general"

@dataclass
class SentimentAnalysis:
    """Detailed sentiment analysis results"""
    text: str
    overall_sentiment: SentimentScore
    confidence: float  # 0-1
    positive_score: float
    negative_score: float
    neutral_score: float
    emotions: Dict[str, float]  # emotion -> score
    key_phrases: List[str]
    entities: List[Dict[str, Any]]  # Named entities
    category: NewsCategory
    market_relevance: float  # 0-1
    urgency_score: float  # 0-1
    
@dataclass
class SocialSentiment:
    """Social media sentiment aggregation"""
    ticker: str
    platform: str  # twitter, reddit, stocktwits
    total_mentions: int
    sentiment_distribution: Dict[SentimentScore, int]
    average_sentiment: float  # -1 to 1
    trending_topics: List[str]
    influence_score: float  # Weighted by follower count/engagement
    timestamp: datetime
    sample_posts: List[Dict[str, Any]]

@dataclass
class NewsEvent:
    """Detected news event"""
    title: str
    description: str
    category: NewsCategory
    timestamp: datetime
    affected_tickers: List[str]
    sentiment_impact: float  # -1 to 1
    market_impact_prediction: float  # 0-1
    confidence: float
    source_quality: float  # Reliability of source
    keywords: List[str]

class TextPreprocessor:
    """Advanced text preprocessing for financial news"""
    
    def __init__(self):
        # Financial stop words (words to remove)
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        # Financial terms and their sentiment weights
        self.financial_sentiment_lexicon = {
            # Very Positive
            "soar": 0.9, "surge": 0.8, "rally": 0.7, "boom": 0.8, "breakout": 0.7,
            "outperform": 0.8, "beat": 0.7, "exceed": 0.7, "strong": 0.6, "bullish": 0.8,
            "upgrade": 0.7, "buy": 0.6, "growth": 0.5, "profit": 0.6, "revenue": 0.4,
            
            # Positive  
            "gain": 0.5, "rise": 0.4, "up": 0.3, "increase": 0.4, "improve": 0.5,
            "positive": 0.5, "optimistic": 0.6, "confident": 0.5, "opportunity": 0.4,
            
            # Negative
            "fall": -0.4, "drop": -0.5, "decline": -0.5, "down": -0.3, "decrease": -0.4,
            "negative": -0.5, "concern": -0.4, "worry": -0.5, "risk": -0.3, "challenge": -0.3,
            
            # Very Negative
            "crash": -0.9, "plunge": -0.8, "collapse": -0.9, "plummet": -0.8, "tank": -0.7,
            "bearish": -0.8, "downgrade": -0.7, "sell": -0.6, "loss": -0.6, "weak": -0.5,
            "disappointing": -0.6, "miss": -0.6, "cut": -0.5, "layoffs": -0.7, "bankruptcy": -0.9
        }
        
        # Ticker symbol pattern
        self.ticker_pattern = re.compile(r'\\$([A-Z]{1,5})')
        
        # Number patterns
        self.number_pattern = re.compile(r'\\b\\d+(?:\\.\\d+)?(?:[BMK])?\\b', re.IGNORECASE)
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http\\S+|www\\S+|https\\S+', '', text, flags=re.MULTILINE)
        
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^a-zA-Z0-9\\s\\.,!?$%]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\\s+', ' ', text).strip()
        
        return text
    
    def extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text"""
        tickers = []
        
        # Find $TICKER patterns
        matches = self.ticker_pattern.findall(text.upper())
        tickers.extend(matches)
        
        # Find standalone ticker patterns (3-5 uppercase letters)
        standalone_pattern = re.compile(r'\\b[A-Z]{3,5}\\b')
        standalone_matches = standalone_pattern.findall(text.upper())
        
        # Filter out common false positives
        false_positives = {'THE', 'AND', 'FOR', 'YOU', 'ARE', 'ALL', 'NEW', 'GET', 'NOW', 'SEE'}
        standalone_matches = [t for t in standalone_matches if t not in false_positives]
        
        tickers.extend(standalone_matches)
        
        return list(set(tickers))  # Remove duplicates
    
    def extract_numbers_and_percentages(self, text: str) -> Dict[str, List[float]]:
        """Extract numbers and percentages from text"""
        numbers = []
        percentages = []
        
        # Find percentage patterns
        pct_matches = re.findall(r'\\b(\\d+(?:\\.\\d+)?)%', text)
        percentages.extend([float(m) for m in pct_matches])
        
        # Find number patterns
        num_matches = self.number_pattern.findall(text)
        for match in num_matches:
            try:
                # Handle B, M, K suffixes
                if match.upper().endswith('B'):
                    numbers.append(float(match[:-1]) * 1e9)
                elif match.upper().endswith('M'):
                    numbers.append(float(match[:-1]) * 1e6)
                elif match.upper().endswith('K'):
                    numbers.append(float(match[:-1]) * 1e3)
                else:
                    numbers.append(float(match))
            except ValueError:
                continue
        
        return {"numbers": numbers, "percentages": percentages}
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words/phrases"""
        # Simple tokenization (could be enhanced with spaCy/NLTK)
        words = re.findall(r'\\b\\w+\\b', text.lower())
        return [word for word in words if word not in self.stop_words and len(word) > 2]

class AdvancedSentimentAnalyzer:
    """Advanced sentiment analysis for financial text"""
    
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.cache = Cache()
        
        # Category keywords for news classification
        self.category_keywords = {
            NewsCategory.EARNINGS: ["earnings", "revenue", "profit", "eps", "quarterly", "guidance"],
            NewsCategory.PRODUCT_LAUNCH: ["launch", "product", "release", "unveil", "announce"],
            NewsCategory.MERGER_ACQUISITION: ["merger", "acquisition", "acquire", "deal", "buyout"],
            NewsCategory.REGULATORY: ["regulatory", "regulation", "sec", "fda", "fcc", "compliance"],
            NewsCategory.MANAGEMENT_CHANGE: ["ceo", "cfo", "executive", "management", "appoint", "resign"],
            NewsCategory.PARTNERSHIP: ["partnership", "alliance", "collaborate", "joint venture"],
            NewsCategory.LEGAL_ISSUE: ["lawsuit", "legal", "court", "settlement", "investigation"],
            NewsCategory.MARKET_ANALYSIS: ["analyst", "target", "rating", "recommendation", "outlook"]
        }
    
    async def analyze_sentiment(self, text: str, ticker: Optional[str] = None) -> SentimentAnalysis:
        """Perform comprehensive sentiment analysis"""
        
        # Preprocess text
        cleaned_text = self.preprocessor.clean_text(text)
        tokens = self.preprocessor.tokenize(cleaned_text)
        
        # Calculate sentiment scores
        sentiment_scores = self._calculate_sentiment_scores(tokens, text)
        
        # Classify overall sentiment
        overall_sentiment = self._classify_sentiment(sentiment_scores)
        
        # Extract key phrases
        key_phrases = self._extract_key_phrases(text, tokens)
        
        # Extract entities
        entities = self._extract_entities(text)
        
        # Classify news category
        category = self._classify_news_category(text)
        
        # Calculate market relevance
        market_relevance = self._calculate_market_relevance(text, ticker)
        
        # Calculate urgency
        urgency_score = self._calculate_urgency(text, sentiment_scores)
        
        return SentimentAnalysis(
            text=text,
            overall_sentiment=overall_sentiment,
            confidence=sentiment_scores["confidence"],
            positive_score=sentiment_scores["positive"],
            negative_score=sentiment_scores["negative"],
            neutral_score=sentiment_scores["neutral"],
            emotions=self._detect_emotions(text),
            key_phrases=key_phrases,
            entities=entities,
            category=category,
            market_relevance=market_relevance,
            urgency_score=urgency_score
        )
    
    def _calculate_sentiment_scores(self, tokens: List[str], original_text: str) -> Dict[str, float]:
        """Calculate detailed sentiment scores"""
        positive_score = 0.0
        negative_score = 0.0
        total_sentiment_words = 0
        
        # Score based on financial lexicon
        for token in tokens:
            if token in self.preprocessor.financial_sentiment_lexicon:
                score = self.preprocessor.financial_sentiment_lexicon[token]
                if score > 0:
                    positive_score += score
                else:
                    negative_score += abs(score)
                total_sentiment_words += 1
        
        # Normalize scores
        if total_sentiment_words > 0:
            positive_score /= total_sentiment_words
            negative_score /= total_sentiment_words
        
        # Check for intensity modifiers
        intensity_modifiers = {
            "very": 1.5, "extremely": 2.0, "highly": 1.3, "significantly": 1.4,
            "slightly": 0.5, "somewhat": 0.7, "moderately": 0.8
        }
        
        text_lower = original_text.lower()
        for modifier, multiplier in intensity_modifiers.items():
            if modifier in text_lower:
                positive_score *= multiplier
                negative_score *= multiplier
                break
        
        # Calculate neutral score
        neutral_score = max(0, 1 - positive_score - negative_score)
        
        # Calculate confidence based on number of sentiment words
        confidence = min(1.0, total_sentiment_words / 10.0)  # Max confidence at 10+ sentiment words
        
        return {
            "positive": positive_score,
            "negative": negative_score,
            "neutral": neutral_score,
            "confidence": confidence
        }
    
    def _classify_sentiment(self, scores: Dict[str, float]) -> SentimentScore:
        """Classify overall sentiment"""
        pos = scores["positive"]
        neg = scores["negative"]
        
        if pos > neg + 0.3:
            return SentimentScore.VERY_POSITIVE if pos > 0.7 else SentimentScore.POSITIVE
        elif neg > pos + 0.3:
            return SentimentScore.VERY_NEGATIVE if neg > 0.7 else SentimentScore.NEGATIVE
        else:
            return SentimentScore.NEUTRAL
    
    def _extract_key_phrases(self, text: str, tokens: List[str]) -> List[str]:
        """Extract key phrases from text"""
        # Simple n-gram extraction (could be enhanced with TF-IDF or other methods)
        words = text.lower().split()
        
        # Extract 2-grams and 3-grams
        phrases = []
        
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if any(word in self.preprocessor.financial_sentiment_lexicon for word in [words[i], words[i+1]]):
                phrases.append(bigram)
        
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
            if any(word in self.preprocessor.financial_sentiment_lexicon for word in [words[i], words[i+1], words[i+2]]):
                phrases.append(trigram)
        
        # Return top phrases by frequency
        phrase_counts = Counter(phrases)
        return [phrase for phrase, count in phrase_counts.most_common(5)]
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities (companies, people, locations)"""
        entities = []
        
        # Extract ticker symbols
        tickers = self.preprocessor.extract_tickers(text)
        for ticker in tickers:
            entities.append({
                "text": ticker,
                "type": "TICKER",
                "confidence": 0.9
            })
        
        # Extract numbers and percentages
        numbers_data = self.preprocessor.extract_numbers_and_percentages(text)
        for pct in numbers_data["percentages"]:
            entities.append({
                "text": f"{pct}%",
                "type": "PERCENTAGE",
                "confidence": 0.8
            })
        
        # Simple company name detection (could be enhanced with NER models)
        company_patterns = [
            r'\\b([A-Z][a-z]+ (?:Inc|Corp|LLC|Ltd|Co))\\b',
            r'\\b([A-Z][a-z]+ (?:& [A-Z][a-z]+)+)\\b'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                entities.append({
                    "text": match,
                    "type": "COMPANY",
                    "confidence": 0.7
                })
        
        return entities
    
    def _classify_news_category(self, text: str) -> NewsCategory:
        """Classify news into categories"""
        text_lower = text.lower()
        
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        
        return NewsCategory.GENERAL
    
    def _calculate_market_relevance(self, text: str, ticker: Optional[str] = None) -> float:
        """Calculate how relevant the news is to market movements"""
        relevance_score = 0.0
        
        # Check for financial keywords
        financial_keywords = [
            "earnings", "revenue", "profit", "loss", "stock", "shares", "market",
            "price", "trading", "analyst", "rating", "target", "forecast"
        ]
        
        text_lower = text.lower()
        keyword_count = sum(1 for keyword in financial_keywords if keyword in text_lower)
        relevance_score += min(0.5, keyword_count * 0.1)
        
        # Boost if specific ticker mentioned
        if ticker and ticker.lower() in text_lower:
            relevance_score += 0.3
        
        # Check for quantitative information
        numbers_data = self.preprocessor.extract_numbers_and_percentages(text)
        if numbers_data["percentages"]:
            relevance_score += 0.2
        
        return min(1.0, relevance_score)
    
    def _calculate_urgency(self, text: str, sentiment_scores: Dict[str, float]) -> float:
        """Calculate urgency score for the news"""
        urgency_keywords = [
            "breaking", "urgent", "alert", "immediate", "emergency", "now", "today",
            "plunge", "surge", "crash", "soar", "halt", "suspend"
        ]
        
        text_lower = text.lower()
        urgency_count = sum(1 for keyword in urgency_keywords if keyword in text_lower)
        
        # Base urgency from keywords
        urgency_score = min(0.6, urgency_count * 0.2)
        
        # Add urgency based on extreme sentiment
        extreme_sentiment = max(sentiment_scores["positive"], sentiment_scores["negative"])
        if extreme_sentiment > 0.7:
            urgency_score += 0.3
        
        return min(1.0, urgency_score)
    
    def _detect_emotions(self, text: str) -> Dict[str, float]:
        """Detect emotions in text"""
        emotion_keywords = {
            "fear": ["fear", "afraid", "worried", "concern", "anxiety", "panic", "risk"],
            "greed": ["opportunity", "profit", "gain", "growth", "bullish", "buy"],
            "excitement": ["excited", "thrilled", "amazing", "breakthrough", "surge"],
            "anger": ["angry", "frustrated", "disappointed", "outraged", "furious"],
            "optimism": ["optimistic", "confident", "positive", "hopeful", "bright"],
            "pessimism": ["pessimistic", "negative", "doubt", "uncertain", "dark"]
        }
        
        text_lower = text.lower()
        emotions = {}
        
        for emotion, keywords in emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            emotions[emotion] = min(1.0, score * 0.2)
        
        return emotions

class SocialMediaAnalyzer:
    """Analyze sentiment from social media platforms"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.session: Optional[aiohttp.ClientSession] = None
        self.sentiment_analyzer = AdvancedSentimentAnalyzer()
        self.cache = Cache()
    
    async def connect(self) -> None:
        """Initialize connections"""
        self.session = aiohttp.ClientSession()
    
    async def disconnect(self) -> None:
        """Close connections"""
        if self.session:
            await self.session.close()
    
    async def analyze_social_sentiment(self, ticker: str, hours_back: int = 24) -> SocialSentiment:
        """Analyze social sentiment for a ticker"""
        
        # Collect posts from multiple platforms
        all_posts = []
        
        # Twitter/X (if API available)
        if "twitter" in self.api_keys:
            twitter_posts = await self._fetch_twitter_posts(ticker, hours_back)
            all_posts.extend(twitter_posts)
        
        # Reddit (if API available)
        if "reddit" in self.api_keys:
            reddit_posts = await self._fetch_reddit_posts(ticker, hours_back)
            all_posts.extend(reddit_posts)
        
        # StockTwits (if API available)
        stocktwits_posts = await self._fetch_stocktwits_posts(ticker, hours_back)
        all_posts.extend(stocktwits_posts)
        
        if not all_posts:
            return self._create_empty_sentiment(ticker)
        
        # Analyze sentiment for each post
        sentiment_results = []
        for post in all_posts:
            try:
                analysis = await self.sentiment_analyzer.analyze_sentiment(post["text"], ticker)
                sentiment_results.append({
                    "post": post,
                    "analysis": analysis
                })
            except Exception as e:
                logger.warning(f"Error analyzing post sentiment: {e}")
                continue
        
        # Aggregate results
        return self._aggregate_social_sentiment(ticker, sentiment_results)
    
    async def _fetch_twitter_posts(self, ticker: str, hours_back: int) -> List[Dict]:
        """Fetch Twitter posts mentioning the ticker"""
        # Mock data for demonstration
        return [
            {
                "text": f"${ticker} looking strong today! Great earnings report.",
                "author": "trader123",
                "followers": 1000,
                "retweets": 5,
                "likes": 15,
                "timestamp": datetime.now()
            }
        ]
    
    async def _fetch_reddit_posts(self, ticker: str, hours_back: int) -> List[Dict]:
        """Fetch Reddit posts from investing subreddits"""
        # Mock data for demonstration  
        return [
            {
                "text": f"What do you think about {ticker}? Seems undervalued.",
                "subreddit": "investing",
                "author": "investor456",
                "upvotes": 25,
                "comments": 10,
                "timestamp": datetime.now()
            }
        ]
    
    async def _fetch_stocktwits_posts(self, ticker: str, hours_back: int) -> List[Dict]:
        """Fetch StockTwits posts"""
        # Mock data for demonstration
        return [
            {
                "text": f"${ticker} breaking out! Target $150",
                "author": "stockpro789",
                "followers": 500,
                "likes": 8,
                "timestamp": datetime.now()
            }
        ]
    
    def _aggregate_social_sentiment(self, ticker: str, sentiment_results: List[Dict]) -> SocialSentiment:
        """Aggregate sentiment results from social media"""
        if not sentiment_results:
            return self._create_empty_sentiment(ticker)
        
        # Count sentiment distribution
        sentiment_counts = defaultdict(int)
        total_sentiment_score = 0.0
        trending_keywords = defaultdict(int)
        influence_weighted_sentiment = 0.0
        total_influence = 0.0
        
        for result in sentiment_results:
            analysis = result["analysis"]
            post = result["post"]
            
            sentiment_counts[analysis.overall_sentiment] += 1
            
            # Calculate numeric sentiment score
            if analysis.overall_sentiment == SentimentScore.VERY_POSITIVE:
                score = 1.0
            elif analysis.overall_sentiment == SentimentScore.POSITIVE:
                score = 0.5
            elif analysis.overall_sentiment == SentimentScore.NEUTRAL:
                score = 0.0
            elif analysis.overall_sentiment == SentimentScore.NEGATIVE:
                score = -0.5
            else:  # VERY_NEGATIVE
                score = -1.0
            
            total_sentiment_score += score
            
            # Weight by influence (followers, engagement)
            influence = post.get("followers", 100) + post.get("likes", 0) * 2
            influence_weighted_sentiment += score * influence
            total_influence += influence
            
            # Collect trending keywords
            for phrase in analysis.key_phrases:
                trending_keywords[phrase] += 1
        
        # Calculate averages
        average_sentiment = total_sentiment_score / len(sentiment_results)
        weighted_sentiment = influence_weighted_sentiment / total_influence if total_influence > 0 else average_sentiment
        
        # Get top trending topics
        trending_topics = [topic for topic, count in Counter(trending_keywords).most_common(10)]
        
        # Sample posts for reference
        sample_posts = [result["post"] for result in sentiment_results[:5]]
        
        return SocialSentiment(
            ticker=ticker,
            platform="aggregated",
            total_mentions=len(sentiment_results),
            sentiment_distribution=dict(sentiment_counts),
            average_sentiment=weighted_sentiment,
            trending_topics=trending_topics,
            influence_score=total_influence / len(sentiment_results),
            timestamp=datetime.now(),
            sample_posts=sample_posts
        )
    
    def _create_empty_sentiment(self, ticker: str) -> SocialSentiment:
        """Create empty sentiment result when no data available"""
        return SocialSentiment(
            ticker=ticker,
            platform="aggregated",
            total_mentions=0,
            sentiment_distribution={},
            average_sentiment=0.0,
            trending_topics=[],
            influence_score=0.0,
            timestamp=datetime.now(),
            sample_posts=[]
        )

# Example usage
async def example_usage():
    """Example of how to use the enhanced sentiment analysis"""
    
    # Initialize sentiment analyzer
    analyzer = AdvancedSentimentAnalyzer()
    
    # Analyze news article
    news_text = "Apple Inc. reported strong quarterly earnings, beating analyst expectations with revenue growth of 15%. The company's stock surged 8% in after-hours trading."
    
    analysis = await analyzer.analyze_sentiment(news_text, "AAPL")
    
    print(f"Overall Sentiment: {analysis.overall_sentiment}")
    print(f"Confidence: {analysis.confidence:.2f}")
    print(f"Key Phrases: {analysis.key_phrases}")
    print(f"Category: {analysis.category}")
    print(f"Market Relevance: {analysis.market_relevance:.2f}")
    
    # Initialize social media analyzer
    api_keys = {
        "twitter": "your_twitter_api_key",
        "reddit": "your_reddit_api_key"
    }
    
    social_analyzer = SocialMediaAnalyzer(api_keys)
    await social_analyzer.connect()
    
    # Analyze social sentiment
    social_sentiment = await social_analyzer.analyze_social_sentiment("AAPL")
    
    print(f"\\nSocial Sentiment for AAPL:")
    print(f"Total Mentions: {social_sentiment.total_mentions}")
    print(f"Average Sentiment: {social_sentiment.average_sentiment:.2f}")
    print(f"Trending Topics: {social_sentiment.trending_topics}")
    
    await social_analyzer.disconnect()

if __name__ == "__main__":
    asyncio.run(example_usage())