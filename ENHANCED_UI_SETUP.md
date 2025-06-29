# Enhanced UI Setup Guide

## 🎉 What's New

The AI Hedge Fund now includes a **comprehensive web interface** with all enhanced features accessible through an intuitive menu system!

### ✨ New Features Available in Web UI:

1. **📊 Portfolio Dashboard** - Real-time portfolio analysis and performance metrics
2. **🎯 Universe Selection** - Interactive trading universe configuration 
3. **📈 Economic Indicators** - Live economic data and Fed policy tracking
4. **🏛️ Political Signals** - Political event monitoring and impact assessment
5. **💬 Sentiment Analysis** - Social media and news sentiment tracking
6. **📊 Market Overview** - Comprehensive market regime analysis

### 🔄 Dual Interface

The platform now offers **two modes**:
- **Trading Dashboard** - Enhanced features with professional trading interface
- **Workflow Builder** - Original visual workflow system

## 🚀 Quick Setup

### 1. Install New Dependencies

```bash
cd app/frontend
npm install
```

New dependencies added:
- `@radix-ui/react-navigation-menu` - Navigation system
- `@radix-ui/react-dropdown-menu` - Dropdown menus
- `@radix-ui/react-label` - Form labels
- `@radix-ui/react-toggle-group` - Toggle controls
- `recharts` - Interactive charts and graphs

### 2. Configure API Keys (Optional for Enhanced Features)

Add to your `.env` file in the project root:

```bash
# Enhanced Features API Keys (Optional)
FRED_API_KEY=your_fred_api_key                    # Economic indicators
NEWSAPI_KEY=your_newsapi_key                      # Political signals  
REDDIT_API_KEY=your_reddit_key                    # Social sentiment
TWITTER_API_KEY=your_twitter_key                  # Social sentiment
FINANCIAL_DATASETS_API_KEY=your_financial_key     # Extended data
```

### 3. Start the Application

```bash
# From the app directory
cd app && ./run.sh

# Or manually:
cd app/backend && poetry run uvicorn app.backend.main:app --reload --port 8000 &
cd app/frontend && npm run dev
```

### 4. Access the Enhanced Interface

1. Open http://localhost:5173
2. Click **"Trading Dashboard"** in the top toggle
3. Use the navigation menu to access all features

## 📱 User Interface Overview

### Navigation Menu

The main navigation is organized into 4 sections:

#### 1. **Portfolio** 📊
- **Dashboard** - Real-time portfolio overview
- **Holdings** - Current positions and allocations  
- **Performance** - Historical returns and metrics
- **Risk Analysis** - Risk exposure and VaR analysis

#### 2. **Trading Universe** 🎯
- **Universe Selection** - Choose investment focus
- **Screener** - Screen securities by criteria
- **Sector Analysis** - Sector rotation and allocation

#### 3. **Market Intelligence** 🧠
- **Economic Indicators** - Fed policy, GDP, inflation
- **Political Signals** - Elections, policy changes
- **Sentiment Analysis** - Social media sentiment
- **Market Overview** - Comprehensive market view

#### 4. **AI Agents** 🤖
- **Agent Performance** - AI analyst accuracy tracking
- **Agent Configuration** - Customize AI behavior
- **Decision Flow** - Visual workflow builder

### Feature Status Indicator

At the top of the interface, a status bar shows which features are available:
- 🟢 **Green** - Feature fully enabled with API key
- 🟡 **Yellow** - Feature available with mock data
- 🔴 **Red** - Feature unavailable

## 🎯 Feature Highlights

### Portfolio Dashboard
- **Real-time Metrics** - Total value, returns, cash balance
- **Market Context** - Economic health, sentiment, political events
- **Interactive Charts** - Performance trends and allocation breakdown
- **Position Details** - Current holdings with P&L tracking

### Universe Selection
- **Pre-configured Universes** - S&P 500, Tech, Sector ETFs, Options, Conservative
- **Custom Configuration** - Set market cap, sector, and position limits
- **Visual Selection** - Card-based interface with feature highlights
- **Real-time Analysis** - Immediate universe composition analysis

### Economic Indicators
- **Key Metrics** - Fed funds rate, unemployment, CPI, GDP
- **Health Scoring** - Algorithmic economic assessment (0-100)
- **Trend Analysis** - Historical context and forecasts
- **Fed Policy Tracking** - FOMC decisions and tone analysis

### Political Signals
- **Event Monitoring** - Elections, policy changes, sanctions
- **Impact Assessment** - Market impact scoring (0-10)
- **Sector Mapping** - Which sectors affected by events
- **Risk Scoring** - Political stability assessment

### Sentiment Analysis
- **Multi-Platform** - Twitter, Reddit, StockTwits aggregation
- **Ticker-Specific** - Individual stock sentiment tracking
- **Trending Topics** - What's driving sentiment
- **Influence Weighting** - Quality-adjusted sentiment scores

## 🛠 Development Notes

### Backend API Endpoints

New enhanced endpoints at `/api/v1/enhanced/`:

```
GET /status                     # Feature availability
GET /universes                  # Trading universes
GET /universes/{name}           # Universe details
GET /economic-indicators        # Economic data
GET /economic-summary          # Economic overview
GET /political-events          # Political events
GET /sentiment/{ticker}        # Ticker sentiment
POST /sentiment/batch          # Batch sentiment
POST /portfolio-analysis       # Enhanced analysis
GET /market-overview           # Market summary
WebSocket /ws/live-data        # Real-time updates
```

### Frontend Architecture

```
app/frontend/src/
├── components/
│   ├── navigation/
│   │   └── main-nav.tsx           # Main navigation menu
│   ├── dashboard/
│   │   └── portfolio-dashboard.tsx # Portfolio dashboard
│   ├── universe/
│   │   └── universe-selection.tsx  # Universe selection
│   ├── enhanced-layout.tsx         # Enhanced layout wrapper
│   └── ui/                         # Shared UI components
├── App.tsx                         # Main app with mode toggle
└── ...
```

### State Management

- **Local State** - React useState for component state
- **API Integration** - Direct fetch calls to backend
- **Real-time Updates** - WebSocket for live data
- **Caching** - Browser localStorage for preferences

## 🔧 Customization

### Adding New Universe Types

1. **Backend** - Add to `src/data/trading_universes.py`:
```python
CUSTOM_UNIVERSE = TradingUniverse(
    name="custom",
    description="Custom investment universe",
    asset_classes=[AssetClass.EQUITY],
    max_positions=25,
    included_tickers=["AAPL", "MSFT"]
)
```

2. **Frontend** - Add to universe cards in `universe-selection.tsx`

### Adding New Dashboard Widgets

1. Create component in `components/dashboard/`
2. Add to `enhanced-layout.tsx` navigation
3. Integrate with backend API endpoints

### Styling Customization

- **Theme** - Modify `tailwind.config.ts`
- **Colors** - Update color constants in components
- **Layout** - Adjust spacing in layout components

## 📊 Data Sources

### Real-time Data
- **Economic** - Federal Reserve Economic Data (FRED)
- **Political** - NewsAPI, RSS feeds
- **Sentiment** - Reddit API, Twitter API, StockTwits
- **Market** - Financial Datasets API, Alpha Vantage, Polygon

### Mock Data Fallbacks
When API keys aren't configured, the system provides:
- Sample economic indicators
- Mock political events  
- Simulated sentiment data
- Generated market overviews

## 🚨 Troubleshooting

### Common Issues

1. **Navigation Menu Not Showing**
   ```bash
   npm install @radix-ui/react-navigation-menu
   ```

2. **Charts Not Rendering**
   ```bash
   npm install recharts
   ```

3. **Backend API Errors**
   - Check backend is running on port 8000
   - Verify API keys in `.env` file
   - Check browser console for CORS issues

4. **Feature Status All Red**
   - Add API keys to `.env` in project root
   - Restart backend server
   - Check `/api/v1/enhanced/status` endpoint

### Debug Mode

Add to browser console:
```javascript
localStorage.setItem('debug', 'true');
```

This enables detailed logging for API calls and state changes.

## 🎯 Next Steps

1. **Install Dependencies** - `npm install` in frontend
2. **Add API Keys** - Configure `.env` for full features  
3. **Start Application** - `./run.sh` from app directory
4. **Explore Features** - Switch to "Trading Dashboard" mode
5. **Customize** - Add your own analysis and universes

## 📞 Support

- **Documentation** - Check `ENHANCED_FEATURES_GUIDE.md`
- **API Reference** - Visit http://localhost:8000/docs
- **Troubleshooting** - See `BACKEND_TROUBLESHOOTING.md`

---

🎉 **Congratulations!** You now have a professional-grade hedge fund interface with comprehensive analysis capabilities!