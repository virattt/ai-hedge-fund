# Enhanced AI Hedge Fund Features Guide

This guide explains how to use the new enhanced features including trading universes, advanced sentiment analysis, economic indicators, and political signals monitoring.

## 🌟 Overview of Enhanced Features

The enhanced AI hedge fund now includes:

1. **🎯 Trading Universe System** - Define investment universes with specific criteria
2. **📊 Advanced Sentiment Analysis** - NLP analysis of news and social media
3. **📈 Economic Indicators** - Real-time economic data and Fed policy tracking
4. **🏛️ Political Signals** - Political event monitoring and impact assessment
5. **⚡ Real-Time Data Pipeline** - Live market data and options Greeks
6. **🧠 Enhanced Portfolio Management** - Comprehensive analysis integration

## 🎯 Trading Universe System

### What is a Trading Universe?

A trading universe defines the set of securities your hedge fund can trade, with specific filters and constraints:

```python
from src.data.trading_universes import get_trading_universe

# Get the S&P 500 universe
sp500_universe = get_trading_universe("sp500")
print(f"Description: {sp500_universe.description}")
print(f"Max positions: {sp500_universe.max_positions}")
print(f"Min market cap: {sp500_universe.min_market_cap}B")
```

### Available Trading Universes

| Universe | Description | Focus | Max Positions |
|----------|-------------|-------|---------------|
| `sp500` | S&P 500 companies | Large cap, high liquidity | 50 |
| `tech` | High-volume tech stocks | Technology sector | 30 |
| `sector_etf` | Sector-based ETFs | Sector rotation | 15 |
| `options` | Options trading universe | Liquid options markets | 25 |
| `conservative` | Conservative large cap | Blue-chip dividends | 40 |
| `aggressive_growth` | Tech + Options combo | Maximum returns | 55 |
| `balanced` | S&P 500 + Sector ETFs | Diversified approach | 65 |

### How Trading Universes Are Used

1. **Security Filtering**: Only stocks meeting universe criteria are considered
2. **Position Limits**: Maximum number of positions enforced
3. **Sector Allocation**: Target sector weightings applied
4. **Risk Management**: Universe-specific risk parameters
5. **Strategy Alignment**: Investment approach matched to universe

### Using Different Universes

```bash
# Use tech universe for growth focus
poetry run python src/enhanced_main.py --tickers AAPL,MSFT,GOOGL --universe tech

# Use conservative universe for stable returns
poetry run python src/enhanced_main.py --tickers JNJ,PG,KO --universe conservative

# Use options universe for complex strategies
poetry run python src/enhanced_main.py --tickers SPY,QQQ,AAPL --universe options
```

## 📊 Enhanced Sentiment Analysis

### Advanced NLP Features

The enhanced sentiment analyzer provides:

- **Financial Lexicon**: 500+ finance-specific sentiment terms
- **Entity Extraction**: Automatic ticker, company, and number recognition
- **News Categorization**: Earnings, M&A, regulatory, management changes
- **Emotion Detection**: Fear, greed, optimism, pessimism indicators
- **Market Relevance Scoring**: Direct market impact assessment

### How Sentiment Analysis Works

```python
from src.agents.enhanced_sentiment import AdvancedSentimentAnalyzer

analyzer = AdvancedSentimentAnalyzer()

# Analyze news article
news_text = "Apple Inc. reported strong quarterly earnings, beating analyst expectations..."
analysis = await analyzer.analyze_sentiment(news_text, "AAPL")

print(f"Overall Sentiment: {analysis.overall_sentiment}")
print(f"Confidence: {analysis.confidence:.2f}")
print(f"Key Phrases: {analysis.key_phrases}")
print(f"Market Relevance: {analysis.market_relevance:.2f}")
```

### Social Media Integration

The system analyzes sentiment from:
- **Twitter/X**: Real-time tweets and engagement
- **Reddit**: Investment subreddit discussions
- **StockTwits**: Financial social network posts

Metrics include:
- Average sentiment score (-1 to 1)
- Total mentions and engagement
- Trending topics and hashtags
- Influence-weighted analysis

## 📈 Economic Indicators Integration

### Federal Reserve Economic Data (FRED)

The system tracks key economic indicators:

| Indicator | Frequency | Impact Level |
|-----------|-----------|--------------|
| Fed Funds Rate | Monthly | High |
| Unemployment Rate | Monthly | High |
| Core CPI | Monthly | High |
| GDP Growth | Quarterly | High |
| Consumer Confidence | Monthly | Medium |
| Initial Claims | Weekly | Medium |
| 10Y Treasury Yield | Daily | High |

### Economic Health Scoring

The system calculates an overall economic health score (0-100) based on:

- **Unemployment Rate**: Lower is better (target <4%)
- **GDP Growth**: Positive growth preferred (target >2%)
- **Inflation**: Target around 2% (1.5-2.5% optimal)
- **Consumer Confidence**: Higher is better (>100 preferred)

### Fed Policy Analysis

The system analyzes Federal Reserve communications for:
- **Policy Tone**: Hawkish, dovish, or neutral sentiment
- **Rate Change Probability**: Market expectations
- **Key Themes**: Inflation, employment, economic outlook
- **Market Impact Scoring**: Expected volatility

## 🏛️ Political Signals Monitoring

### Event Types Tracked

The system monitors various political events:

| Event Type | Examples | Market Impact |
|------------|----------|---------------|
| Elections | Presidential, Congressional | High |
| Policy Announcements | Tax policy, healthcare | Medium-High |
| Sanctions | Trade restrictions | High |
| Regulatory Changes | SEC, FDA rulings | Medium |
| Geopolitical Tensions | Wars, conflicts | High |
| Debt Ceiling | Government funding | High |

### Political Risk Assessment

Each event receives:
- **Impact Level**: High, Medium, Low
- **Affected Sectors**: Technology, Healthcare, Energy, etc.
- **Sentiment Score**: -1 (negative) to 1 (positive)
- **Market Impact Score**: 0-10 scale
- **Urgency Score**: Time-sensitive prioritization

### Integration with Trading Decisions

Political signals influence:
- **Sector Allocation**: Adjust exposure based on policy changes
- **Risk Management**: Increase cash during high uncertainty
- **Timing**: Delay trades during major political events
- **Hedging**: Use defensive positions during tensions

## ⚡ Real-Time Data Pipeline

### Market Data Sources

The system supports multiple data providers:
- **Alpha Vantage**: Basic market data
- **Polygon.io**: Real-time quotes and options
- **Interactive Brokers**: Professional data feeds
- **Tradier**: Options chains and Greeks

### Options Greeks Calculation

For options strategies, the system calculates:
- **Delta**: Price sensitivity to underlying
- **Gamma**: Delta change rate
- **Theta**: Time decay
- **Vega**: Volatility sensitivity
- **Rho**: Interest rate sensitivity

### Implied Volatility

The system uses Black-Scholes models to calculate:
- Real-time implied volatility
- Volatility surface modeling
- IV percentile rankings
- Volatility forecasting

## 🧠 Enhanced Portfolio Management

### Comprehensive Decision Framework

The enhanced portfolio manager considers:

1. **Traditional Analysis**: Fundamental, technical, sentiment
2. **Economic Context**: GDP, inflation, employment
3. **Political Environment**: Policy changes, elections
4. **Market Regime**: Bull, bear, sideways, volatile
5. **Social Sentiment**: Crowd psychology indicators
6. **Risk Assessment**: VaR, correlation, concentration

### Market Regime Detection

The system identifies four market regimes:

| Regime | Characteristics | Strategy |
|--------|----------------|----------|
| Bull Market | Rising prices, optimism | Growth stocks, momentum |
| Bear Market | Falling prices, pessimism | Defensive, quality, shorts |
| Sideways Market | Range-bound trading | Value plays, covered calls |
| Volatile Market | High uncertainty | Reduced size, options |

### Sector Allocation

Based on the trading universe, the system applies:
- **Target Weightings**: Optimal sector allocation
- **Deviation Limits**: Maximum over/underweight
- **Rebalancing Triggers**: When to adjust positions
- **Risk Budgets**: Sector-specific risk limits

## 🚀 Getting Started with Enhanced Features

### 1. Setup API Keys

Add to your `.env` file:

```bash
# Required: At least one LLM API key
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key

# Enhanced Features (Optional)
FRED_API_KEY=your_fred_key          # Economic indicators (free)
NEWSAPI_KEY=your_newsapi_key        # Political signals
REDDIT_API_KEY=your_reddit_key      # Social sentiment
TWITTER_API_KEY=your_twitter_key    # Social sentiment
FINANCIAL_DATASETS_API_KEY=your_key # Extended stock data
```

### 2. Run Enhanced Analysis

```bash
# Basic enhanced analysis
poetry run python src/enhanced_main.py --tickers AAPL,MSFT,GOOGL --universe tech

# Full features with reasoning
poetry run python src/enhanced_main.py --tickers AAPL,MSFT,GOOGL --universe tech --show-reasoning

# Demo mode with sample data
poetry run python src/enhanced_main.py --demo --show-reasoning
```

### 3. Web Interface Integration

The enhanced features integrate with the web application:

```bash
# Start web app with enhanced backend
cd app && ./run.sh
```

Access the enhanced features through:
- **Portfolio Dashboard**: Real-time analysis
- **Universe Selection**: Choose trading focus
- **Sentiment Monitor**: Track market mood
- **Economic Dashboard**: Monitor macro indicators
- **Political Tracker**: Watch policy developments

## 📊 Example Enhanced Analysis Output

```
🎯 ENHANCED TRADING ANALYSIS RESULTS
=========================================

📊 Portfolio-Level Analysis:
   🌡️  Market Sentiment: 0.35
   🏥 Economic Health: 72.5/100
   🏛️  Political Stability: 68.0/100
   📈 Market Regime: Bull Market
   ⚠️  Risk Level: Medium

📈 Economic Indicators:
   📊 Health Score: 72.5/100
   📝 Summary: Economic outlook appears positive

🏛️ Political Signals:
   ⚡ High Impact Events: 1
   📰 Total Events: 12

💬 Social Sentiment:
   AAPL: 0.45 (1,234 mentions)
   MSFT: 0.23 (892 mentions)
   GOOGL: 0.12 (567 mentions)

🎯 Trading Decisions:
   AAPL: BUY 50 shares (Confidence: 85.2%)
     📊 Sentiment: 0.45
     🏛️ Economic Impact: 0.23
     ⚠️ Political Risk: -0.12
   
   MSFT: BUY 30 shares (Confidence: 78.1%)
   GOOGL: HOLD 0 shares (Confidence: 65.4%)
```

## 🔧 Advanced Configuration

### Custom Trading Universe

Create your own universe:

```python
from src.data.models import TradingUniverse, AssetClass, Sector

custom_universe = TradingUniverse(
    name="Custom Tech Universe",
    description="High-growth technology companies",
    asset_classes=[AssetClass.EQUITY],
    sectors=[Sector.TECHNOLOGY],
    min_market_cap=10.0,  # $10B minimum
    max_positions=20,
    included_tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
)
```

### Custom Sentiment Analysis

Extend the sentiment analyzer:

```python
from src.agents.enhanced_sentiment import AdvancedSentimentAnalyzer

class CustomSentimentAnalyzer(AdvancedSentimentAnalyzer):
    def __init__(self):
        super().__init__()
        # Add custom financial terms
        self.preprocessor.financial_sentiment_lexicon.update({
            "moonshot": 0.8,
            "diamond_hands": 0.7,
            "paper_hands": -0.6,
            "to_the_moon": 0.9
        })
```

### Economic Indicator Alerts

Set up custom alerts:

```python
from src.data.economic_indicators import EconomicDataManager

async def check_economic_alerts(manager):
    indicators = await manager.get_all_indicators()
    
    # Alert on high unemployment
    if indicators["unemployment_rate"].value > 5.0:
        print("⚠️ Unemployment above 5%")
    
    # Alert on high inflation
    if indicators["core_cpi"].change_percent > 3.0:
        print("⚠️ Core inflation above 3%")
```

## 🔍 Troubleshooting Enhanced Features

### Common Issues

1. **API Rate Limits**
   ```bash
   # Reduce request frequency
   export REQUEST_DELAY=2  # 2 second delay between requests
   ```

2. **Missing Data**
   ```python
   # Check data availability
   features = check_enhanced_features_availability(api_keys)
   print(features)
   ```

3. **Memory Usage**
   ```bash
   # Monitor memory for large universes
   poetry run python -c "
   import psutil
   print(f'Memory usage: {psutil.virtual_memory().percent}%')
   "
   ```

### Performance Optimization

1. **Cache Configuration**
   - Economic data: 1 hour TTL
   - Political events: 4 hours TTL
   - Sentiment analysis: 30 minutes TTL
   - Options data: 5 minutes TTL

2. **Parallel Processing**
   - Sentiment analysis runs in parallel for multiple tickers
   - Economic and political data fetched concurrently
   - Real-time data uses async WebSocket connections

3. **Data Prioritization**
   - High-impact political events processed first
   - Economic indicators weighted by importance
   - Social sentiment filtered by influence score

## 📚 Further Reading

- [Trading Universe Configuration](src/data/trading_universes.py)
- [Enhanced Sentiment Analysis](src/agents/enhanced_sentiment.py)
- [Economic Indicators Integration](src/data/economic_indicators.py)
- [Political Signals Monitoring](src/data/political_signals.py)
- [Real-Time Data Pipeline](src/data/realtime_data.py)
- [Enhanced Portfolio Manager](src/agents/enhanced_portfolio_manager.py)

---

**Next Steps:**
1. Set up your API keys in `.env`
2. Choose your trading universe
3. Run the enhanced analysis
4. Monitor the comprehensive insights
5. Iterate and refine your strategy

The enhanced AI hedge fund provides institutional-grade analysis capabilities while remaining accessible to individual investors. Start with the demo mode to explore all features!