# UI Components for Market Data Display

This document details the UI components designed for displaying market data within the AI Hedge Fund Platform. These components are intended to be integrated into various views, particularly the Main Dashboard, AI Agent-Specific Views (e.g., Market Data Analyst), and potentially the Portfolio Manager view.

## 1. Real-time Price Charts

Price charts are crucial for visualizing asset price movements and identifying trends. The platform will offer robust charting capabilities.

*   **Chart Types:**
    *   **Candlestick Charts:** Default for assets where open, high, low, and close (OHLC) data are relevant (e.g., stocks, ETFs, some commodities, crypto). Provides a rich visual representation of price action within selected intervals.
    *   **Line Charts:** Suitable for displaying the closing price trend over time, useful for a cleaner view or for assets where only closing price is paramount (e.g., some indices, mutual fund NAVs). Also used for comparing multiple instruments on the same chart.
    *   **OHLC Charts (Bar Charts):** An alternative to candlestick charts, displaying the same OHLC data but with vertical lines and small horizontal ticks for open and close.
    *   **Area Charts:** Similar to line charts but with the area below the line filled, useful for emphasizing the magnitude of price levels or changes.

*   **Interactive Features:**
    *   **Timeframe Selection:**
        *   Buttons/tabs for quick selection of common timeframes (e.g., 1m, 5m, 15m, 1H, 4H, 1D, 1W, 1M).
        *   A date range selector for custom timeframe selection.
        *   Interval selection (e.g., if viewing 1 month of data, the interval could be 1H, 4H, or 1D candles).
    *   **Zoom & Pan:**
        *   Mouse wheel zoom.
        *   Click-and-drag panning.
        *   Zoom buttons (+/-).
        *   "Reset Zoom" button to return to the default view for the selected timeframe.
    *   **Drawing Tools:**
        *   A floating toolbar with common drawing tools:
            *   Trendlines
            *   Horizontal lines (support/resistance)
            *   Fibonacci retracements and extensions
            *   Channels (parallel lines)
            *   Text annotations
            *   Shapes (rectangles, ellipses for highlighting areas)
        *   Ability to customize color and thickness of drawn objects.
        *   Option to save drawn objects per symbol per user.
    *   **Crosshair Tool:** Displays a crosshair cursor that shows the exact price and time/date at the cursor's position, with values displayed on the axes and in a small tooltip.
    *   **Data Window:** A small floating window that displays OHLC values, indicator values, and volume for the data point under the cursor.
    *   **Comparison Feature:** Ability to overlay the price action of another instrument (as a line chart) on the current chart for relative performance analysis.
    *   **Settings:**
        *   Toggle logarithmic vs. linear price scale.
        *   Show/hide grid lines.
        *   Adjust colors for candles, lines, background.

*   **Instrument/Symbol Selection:**
    *   **Primary Search Bar:** A prominent search bar within the charting component or the section it resides in. Users can type a ticker symbol or company name. Autocomplete suggestions will appear.
    *   **Watchlist Integration:** A sidebar or tabbed panel displaying user-defined watchlists. Clicking an instrument in the watchlist loads its chart.
    *   **Recently Viewed:** A dropdown or list showing recently charted symbols for quick access.
    *   **Categorized Browsing (Optional):** For discovery, users might browse instruments by asset class (Equities, Forex, Commodities, Indices), region, or sector.

## 2. Key Market Indicators Display

Technical indicators provide additional context to price action and are essential for many trading strategies.

*   **Display Methods:**
    *   **Overlays:** Indicators plotted directly on the main price chart.
        *   Examples: Moving Averages (SMA, EMA), Bollinger Bands, Parabolic SAR.
        *   Users can add multiple overlays and customize their parameters (e.g., period for MAs, standard deviation for Bollinger Bands) and appearance (color, line style).
    *   **Sub-Charts (Indicator Panes):** Separate chart areas plotted below the main price chart. Each sub-chart displays a specific indicator.
        *   Examples: Relative Strength Index (RSI), Moving Average Convergence Divergence (MACD), Stochastic Oscillator, Average True Range (ATR), Trading Volume.
        *   Users can add multiple sub-charts, resize them, and customize parameters and appearance for each indicator.
    *   **Numerical Displays:**
        *   Key indicator values can be displayed numerically in the Data Window when hovering over the chart.
        *   A summary panel near the chart could show current values for selected key indicators (e.g., current ATR, 52-week high/low).

*   **List of Key Indicators (configurable by user):**
    *   **Volume:** Trading volume displayed as a bar chart in a sub-pane.
    *   **Moving Averages (MAs):** SMA, EMA, WMA. Configurable periods. Plotted as overlays.
    *   **Bollinger Bands:** Overlay on the price chart, showing volatility bands. Configurable period and standard deviations.
    *   **Average True Range (ATR):** Sub-chart, showing market volatility.
    *   **Relative Strength Index (RSI):** Sub-chart, momentum oscillator.
    *   **MACD:** Sub-chart, trend-following momentum indicator.
    *   **Stochastic Oscillator:** Sub-chart, momentum indicator showing overbought/oversold conditions.
    *   **Fibonacci Levels:** Can be drawn manually or automatically plotted based on significant highs/lows.
    *   **Pivot Points:** Calculated daily, weekly, or monthly; displayed as horizontal lines on the chart.

*   **Indicator Management:**
    *   An "Indicators" button/menu allowing users to search, add, remove, and configure indicators on their charts.
    *   Ability to save indicator templates (a specific combination and configuration of indicators) for quick application to different charts.

## 3. News Feeds and Economic Calendar

Timely information is critical in financial markets. Integrating news and economic events directly into the platform enhances decision-making.

*   **Real-time Financial News Feed:**
    *   **Display Area:**
        *   A dedicated panel or section, often a sidebar or a tab within a "Market Overview" or "Research" section.
        *   Can also be a compact, scrollable widget on the main dashboard.
    *   **Content:**
        *   **Headlines:** Displayed in a list, most recent first.
        *   **Timestamp:** Time of news release.
        *   **Source:** (e.g., Reuters, Bloomberg, specific financial news outlets).
        *   **Summaries (Optional):** Short AI-generated or provider-supplied summaries available on hover or by expanding a headline.
        *   **Links to Full Articles:** Clicking a headline opens the full article in a new browser tab or a modal window within the platform.
        *   **Sentiment Indicator (Optional):** A small icon or color code next to headlines indicating AI-assessed sentiment (positive, negative, neutral) if available from the Sentiment Agent.
    *   **Filtering and Search:**
        *   Search bar for keywords within news.
        *   Filter by:
            *   **Relevance to Portfolio:** News directly impacting assets in the current portfolio.
            *   **Asset Class:** (e.g., Equities, Forex, Commodities).
            *   **Specific Symbol/Instrument:** Show news only for AAPL, EUR/USD, etc.
            *   **Source:** Select preferred news providers.
            *   **Region/Country.**
            *   **Keywords/Topics.**

*   **Economic Calendar:**
    *   **Display Area:**
        *   A dedicated tab or section, often alongside the news feed.
        *   Can also be summarized in a small "Upcoming Events" widget on the dashboard.
    *   **Content for Each Event:**
        *   **Time/Date:** Scheduled time of release.
        *   **Event Name:** (e.g., "Non-Farm Payrolls," "CPI m/m," "Fed Interest Rate Decision").
        *   **Country/Currency:** The region/currency the event pertains to.
        *   **Impact Level:** Visual indicator of expected market impact (e.g., Low, Medium, High, often color-coded).
        *   **Previous:** The data from the previous period.
        *   **Forecast/Consensus:** Market expectation for the upcoming release.
        *   **Actual:** The actual figure, updated in real-time upon release. (Visually distinct from forecast, e.g., green if better than forecast, red if worse).
    *   **Filtering and Views:**
        *   Filter by:
            *   **Date Range:** (Today, Tomorrow, This Week, Custom).
            *   **Impact Level.**
            *   **Country/Currency.**
            *   **Event Category:** (e.g., Inflation, Employment, Central Banks, GDP).
        *   **"My Portfolio Events":** A filter to show only events relevant to assets held in the portfolio.
    *   **Alerts:** Users can set reminders for specific high-impact events.

**Integration and Contextual Display:**

*   **Chart Annotations:** Significant news releases or economic events relevant to the charted instrument could be optionally displayed as icons or vertical lines directly on the price chart at the time they occurred. Hovering over the icon would show the event details.
*   **Linking:** When an AI agent (e.g., Sentiment Agent) mentions a news item or event, it should link directly to the item in the news feed or economic calendar for further details.

This detailed description of market data UI components aims to provide a comprehensive and user-friendly experience, enabling users to effectively monitor market movements, analyze trends, and stay informed about critical market-moving information.
