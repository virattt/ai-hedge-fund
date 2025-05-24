# Customizable Dashboards and KPIs UI Design

This document outlines the functionality for customizable dashboards and the display of Key Performance Indicators (KPIs) within the AI Hedge Fund Platform. It leverages components and concepts from `ui_structure.md`, `market_data_ui.md`, `agent_analysis_ui.md`, `risk_manager_ui.md`, and `portfolio_manager_ui.md`.

## 1. Dashboard Customization Mechanism

The platform will provide users with the ability to create personalized dashboard experiences, tailoring the information display to their specific needs and roles.

*   **Core Concept:** A widget-based system on a responsive grid layout. Users can manage multiple named dashboards.

*   **Creating/Managing Dashboards:**
    *   **"My Dashboards" Menu:** A dropdown or section in the sidebar/header where users can:
        *   See a list of their saved dashboards.
        *   Select a dashboard to view.
        *   Create a new dashboard ("+ New Dashboard" button).
        *   Rename existing dashboards.
        *   Duplicate existing dashboards.
        *   Delete dashboards.
        *   Set a default dashboard to load on login.
    *   **Pre-defined Templates (Optional):** Offer a few default dashboard templates tailored to roles (e.g., "Risk Manager Overview," "Portfolio Trader Quick View," "Agent Performance Monitor") that users can then customize.

*   **Customization Mode:**
    *   **"Edit Dashboard" Button:** When viewing a dashboard, an "Edit Dashboard" or "Customize" button switches the view into an editable mode.
    *   **Grid System:** The dashboard area transforms into a visible grid (e.g., a 12-column responsive grid). Widgets snap to this grid.
    *   **Widget Library/Panel:**
        *   A sidebar or modal window ("Add Widgets" panel) appears, displaying available widgets categorized for easy browsing (e.g., "Market Data," "Portfolio," "Risk," "AI Agents").
        *   Each widget in the library has a name, a brief description, and possibly a small preview icon.
    *   **Adding Widgets:** Users can drag and drop widgets from the library onto the dashboard grid or click an "Add" button on the widget in the library.
    *   **Rearranging Widgets:** In edit mode, existing widgets on the dashboard can be dragged and dropped to different positions on the grid.
    *   **Resizing Widgets:** Widgets can be resized by dragging their corners/edges, constrained by the grid system (e.g., spanning multiple columns or rows). Minimum and maximum sizes for widgets will be predefined to maintain usability.
    *   **Removing Widgets:** Each widget in edit mode will have a "Remove" (X) icon.
    *   **Configuring Widgets:** Some widgets will have specific configuration options (e.g., setting the symbol for a market chart widget, choosing the agent for an agent signal widget). This is accessed via a settings icon (e.g., gear icon) on the widget itself while in edit mode. This opens a small configuration modal for that widget instance.

*   **Saving and Loading Layouts:**
    *   **"Save Dashboard" Button:** In edit mode, this button saves the current arrangement and configuration of widgets for the active dashboard.
    *   **Automatic Saving (Drafts):** Changes might be auto-saved as a draft to prevent accidental loss, with an explicit "Publish" or "Finalize Save" action.
    *   Dashboard layouts are saved per user.

## 2. Available Widgets for Customization

Widgets are the building blocks of customizable dashboards. They are self-contained UI components that display specific pieces of information. Many are derived from the detailed views already designed.

*   **Market Data Widgets:**
    *   **Market Chart Widget:** Displays a real-time price chart for a user-specified instrument (from `market_data_ui.md`). Configurable: symbol, chart type, timeframe, initial indicators.
    *   **Watchlist Widget:** Displays a user-defined watchlist with current prices and changes.
    *   **Market Movers Widget:** Shows top gaining/losing assets for a selected market.
    *   **News Feed Widget:** Displays a news feed (from `market_data_ui.md`). Configurable: keywords, sources, specific assets.
    *   **Economic Calendar Widget:** Shows upcoming economic events. Configurable: impact level, countries.
    *   **Key Market Indices Widget:** Displays a selection of major market indices with current values and changes.

*   **AI Agent Widgets:**
    *   **Agent Signal Widget:** Displays the current signal (BUY/SELL/HOLD) and confidence for a *single, user-selected AI agent* for a *single, user-selected asset*.
    *   **Agent Status Widget:** Shows the status (Active, Idle, Error) and last activity for a selected AI agent.
    *   **Top Agent Signals Widget:** Lists the top N (e.g., 3 or 5) strongest signals from a selected AI agent.
    *   **Aggregated Signal Widget:** Displays the overall consensus signal (from `portfolio_manager_ui.md`) for a specific user-selected asset.

*   **Portfolio Management Widgets:**
    *   **Portfolio P&L Chart Widget:** A chart showing overall portfolio P&L over a selectable time period (1D, 1W, 1M, YTD).
    *   **Portfolio Value Widget:** Displays current total portfolio value and daily P&L.
    *   **Top N Holdings Widget:** Lists top N current holdings by market value or P&L.
    *   **Recent Trades Widget:** A compact list of the last N executed trades.
    *   **Open Positions Summary Widget:** A summarized view of current open positions with key P&L figures.
    *   **Specific Holding P&L Widget:** Tracks P&L for a single, user-selected asset in the portfolio.

*   **Risk Management Widgets:**
    *   **VaR Gauge/Value Widget:** Displays current portfolio VaR (from `risk_manager_ui.md`).
    *   **CVaR Gauge/Value Widget:** Displays current portfolio CVaR.
    *   **Max Drawdown Widget:** Shows current or historical max drawdown.
    *   **Risk Limit Utilization Widget:** Displays utilization for a *single, user-selected risk limit* (e.g., "Single Stock Concentration Limit for AAPL").
    *   **Active Risk Alerts Summary Widget:** A compact list of the top N critical active risk alerts.

*   **KPI Widgets:**
    *   **Single KPI Value Widget:** Displays a single selected KPI (e.g., Sharpe Ratio) as a numerical readout, optionally with a small trend indicator (sparkline or arrow). Configurable: KPI to display, timeframe for calculation.
    *   **KPI Table/List Widget:** Displays a table of several user-selected KPIs.

## 3. Key Performance Indicators (KPIs) Definition and Display

KPIs are essential for monitoring performance, effectiveness, and health of trading strategies and the system itself.

*   **Identified KPIs:**

    *   **Portfolio Level KPIs:**
        *   **Overall Portfolio P&L:** Absolute value and percentage. Displayed for various timeframes (Daily, WTD, MTD, YTD, Inception).
        *   **Return on Investment (ROI):** For various timeframes.
        *   **Sharpe Ratio:** Measures risk-adjusted return.
        *   **Sortino Ratio:** Measures downside risk-adjusted return.
        *   **Max Drawdown:** Largest peak-to-trough decline.
        *   **Volatility:** Portfolio volatility (annualized standard deviation of returns).
        *   **Alpha/Beta:** Relative to a benchmark.
        *   **Portfolio Turnover Rate.**
    *   **Trade Level KPIs:**
        *   **Total Number of Trades.**
        *   **Win/Loss Ratio:** Percentage of winning trades vs. losing trades.
        *   **Average Gain per Winning Trade.**
        *   **Average Loss per Losing Trade.**
        *   **Profit Factor:** Gross profit / Gross loss.
        *   **Average Holding Period.**
        *   **Largest Winning Trade.**
        *   **Largest Losing Trade.**
    *   **AI Agent Specific KPIs (per agent):**
        *   **Signal Accuracy (Hit Rate):** Percentage of signals that were "correct" (e.g., a BUY signal followed by a price increase within a defined timeframe). This requires a clear definition of "correctness" and a look-forward period.
        *   **P&L Contribution per Agent:** (If attributable and the model allows for it). This can be complex to calculate fairly.
        *   **Signal Distribution:** Number/percentage of BUY, SELL, HOLD signals generated.
        *   **Signal Frequency:** How often an agent generates signals.
        *   **Average Confidence per Signal.**
        *   **False Positive/False Negative Rate for Signals.**
    *   **Risk Management KPIs:**
        *   **VaR/CVaR History:** Tracking the trend of these metrics.
        *   **Number of Limit Breaches:** Over a period.
        *   **Average Limit Utilization.**
    *   **Operational KPIs:**
        *   **System Uptime.**
        *   **Data Feed Latency/Errors.**
        *   **Order Execution Slippage:** Average difference between expected and actual execution price.

*   **KPI Display Methods:**
    *   **Numerical Readouts:** Simple display of the current KPI value (e.g., "Sharpe Ratio: 1.25"). Often accompanied by the KPI name.
    *   **Sparklines:** Miniature line charts showing the trend of a KPI over time, often displayed next to the numerical value to provide context at a glance.
    *   **Gauges:** For KPIs that have a target range or threshold (e.g., VaR relative to a limit).
    *   **Small Charts:** Compact bar charts, line charts, or pie charts for visualizing distributions (e.g., win/loss ratio as a pie chart) or trends.
    *   **Tables:** Used in dedicated KPI sections or widgets to list multiple KPIs with their values, historical changes, or comparisons.
    *   **Color Coding:** Values can be color-coded (e.g., green for good performance, red for poor) based on predefined thresholds or benchmarks.
    *   **Tooltips:** Hovering over a KPI can reveal more details, such as the exact calculation period, data points used, or definitions.

## 4. User Interface for KPI Selection

Users need an intuitive way to choose which KPIs are important to them and where they appear.

*   **Within Widget Configuration:**
    *   For "Single KPI Value" or "KPI Table/List" widgets, the widget's configuration panel (accessed in dashboard "Edit Mode") will contain:
        *   A searchable list of all available KPIs, categorized (Portfolio, Trade, Agent [Agent Name], Risk).
        *   Checkboxes or a multi-select dropdown to choose the KPIs to display in that widget instance.
        *   Options for each selected KPI (if applicable), such as the timeframe for calculation (e.g., "Portfolio P&L - YTD," "Sharpe Ratio - Trailing 3 Months").
*   **Dedicated "KPI Manager" or "Metrics" Section (Optional, for advanced users):**
    *   A settings area where users can:
        *   View definitions of all available KPIs.
        *   Set default timeframes for certain KPI calculations.
        *   Potentially define custom-calculated KPIs (advanced feature, might involve simple formula building from existing metrics).
        *   Set alert thresholds for specific KPIs (e.g., notify me if Sharpe Ratio drops below 0.5).
*   **In Specific Views:**
    *   For example, within an "AI Agent Performance" view (part of the Historical Performance screen or a dedicated agent analytics section), users might be able to select which agent-specific KPIs are shown in tables or charts for that view.

This design for customizable dashboards and KPIs aims to empower users to create information-rich, personalized views that cater to their specific roles and analytical needs, enhancing their ability to monitor performance and make informed decisions.
