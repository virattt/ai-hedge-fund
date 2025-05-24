# UI Components for Risk Manager View

This document details the UI components for the Risk Manager view, integrating with the overall platform structure defined in `ui_structure.md` and leveraging principles from other UI design documents. The Risk Manager view is a central hub for monitoring, analyzing, and mitigating portfolio risks.

The view will generally follow a dashboard-style layout, accessible from the main sidebar, as outlined in `ui_structure.md`. The header will state "Risk Manager Dashboard."

## 1. Portfolio Risk Metrics Visualization

This section focuses on providing a clear and comprehensive overview of the portfolio's current and historical risk profile.

*   **Layout:** A dedicated "Risk Overview" or "Key Risk Indicators (KRIs)" section at the top of the Risk Manager view or as a primary tab.

*   **Key Risk Metrics & Display Methods:**

    *   **Value at Risk (VaR):**
        *   **Current VaR:** Displayed prominently as a numerical value (e.g., "$150,000") with its associated confidence level and time horizon (e.g., "99% 1-day VaR").
        *   **Visual Element:** A gauge chart could show the current VaR against a predefined acceptable threshold or historical range.
        *   **Historical VaR Plot:** A time-series line chart showing VaR evolution over a selectable period (e.g., last 30 days, 6 months, YTD), allowing identification of trends in risk.
    *   **Conditional Value at Risk (CVaR) / Expected Shortfall (ES):**
        *   **Current CVaR:** Displayed numerically alongside VaR (e.g., "CVaR (99% 1-day): $220,000").
        *   **Historical CVaR Plot:** Can be overlaid on the historical VaR chart or shown as a separate time-series plot.
    *   **Max Drawdown:**
        *   **Current Max Drawdown Potential:** An estimated figure based on current volatility and market conditions, potentially from recent stress tests.
        *   **Historical Max Drawdown:** Displayed as a percentage or absolute value.
        *   **Visual Element:** A bar chart showing peak-to-trough declines in portfolio value over selected historical periods or a time-series plot of drawdown.
    *   **Portfolio Volatility (Standard Deviation):**
        *   **Current Annualized Volatility:** Displayed as a percentage.
        *   **Historical Volatility Plot:** A time-series line chart showing realized volatility over selectable periods (e.g., 30-day rolling volatility), potentially benchmarked against market index volatility (e.g., VIX).
    *   **Sharpe Ratio / Sortino Ratio:**
        *   **Current Ratios:** Displayed numerically.
        *   **Historical Trend:** A time-series plot showing the evolution of these risk-adjusted return metrics.

*   **General Features for Risk Metric Displays:**
    *   **Time Period Selection:** Dropdowns or buttons (1M, 3M, YTD, All) for all historical charts.
    *   **Tooltips:** Hovering over chart data points or metrics will show exact values and dates.
    *   **Benchmarking (Optional):** Ability to plot a benchmark's risk metrics (e.g., index VaR or volatility) alongside the portfolio's for comparison.

## 2. Position Limits Display

This section clearly shows adherence to predefined risk limits for the overall portfolio and specific segments.

*   **Layout:** A dedicated "Limits Monitoring" tab or section within the Risk Manager view.

*   **Display Components:**

    *   **Overall Portfolio Limits Table:**
        *   A table listing key global limits set by the Risk Manager.
        *   **Columns:**
            *   **Limit Type:** (e.g., Total Portfolio VaR, Max Gross Exposure, Max Net Exposure, Max Drawdown Limit).
            *   **Limit Value:** The predefined threshold.
            *   **Current Value:** The portfolio's current standing against this metric.
            *   **Utilization:** A visual representation of current value relative to the limit.
                *   **Progress Bar:** Color-coded (e.g., green for low utilization, yellow for approaching limit, red for breach).
                *   **Percentage Fill:** e.g., "75% of VaR Limit".
            *   **Status:** (e.g., "Nominal," "Watch," "Breached").

    *   **Asset/Sector/Strategy Specific Limits:**
        *   If limits are defined for sub-categories (e.g., max concentration in a single stock, max exposure to a specific sector like "Technology," max allocation to a particular AI agent's strategy).
        *   **Display:** Can be a similar table structure as above, or a series of card views, one for each category with its limits.
        *   **Hierarchical View (Optional):** For complex limit structures, a tree map or sunburst chart could visually represent allocations and their proximity to limits across different hierarchical categories.

    *   **Visual Cues:**
        *   Prominent color-coding (green, yellow, red) for limit statuses throughout the section.
        *   Alert icons next to any limit that is near or in breach.

## 3. Risk Alerts and Flagged Potentials

This section is for highlighting immediate risk concerns and potential future issues identified by the Risk Manager or the system. This is more detailed than the global notifications and specific to the Risk Manager's purview.

*   **Layout:** A dedicated "Active Alerts & Issues" tab or a prominent panel on the main Risk Manager dashboard.

*   **Components:**

    *   **Active Risk Alerts List/Table:**
        *   Displays alerts that require attention or action.
        *   **Columns:**
            *   **Severity:** (e.g., Critical, High, Medium, Low - color-coded icons).
            *   **Timestamp:** When the alert was triggered.
            *   **Alert Type:** (e.g., "VaR Limit Breach," "Volatility Spike," "High Asset Correlation," "Concentration Breach").
            *   **Description:** A concise summary of the issue (e.g., "Portfolio VaR (99%, 1-day) of $165,000 exceeds limit of $150,000," or "Correlation between Asset X and Asset Y increased to 0.85").
            *   **Affected Asset(s)/Metric:** Specific instruments or metrics involved.
            *   **Status:** (e.g., "New," "Investigating," "Actioned," "Resolved").
            *   **Action Button:** (e.g., "View Details," "Acknowledge," "Create Mitigation Plan").
        *   **Sorting & Filtering:** By severity, timestamp, type, status.

    *   **Flagged Potential Risks Section:**
        *   This area is for less immediate but noteworthy observations or potential future risks that the Risk Manager or system has flagged for monitoring.
        *   **Display:** Could be a list or card view.
        *   **Content for each flagged item:**
            *   **Risk Title/Description:** e.g., "Increasing correlation between tech sector and energy sector," "Potential liquidity issues in Asset Z during market stress."
            *   **Reasoning/Evidence:** Brief explanation of why it's flagged.
            *   **Potential Impact:** Qualitative or quantitative assessment.
            *   **Recommended Monitoring Actions:** e.g., "Monitor daily correlation," "Review bid-ask spreads for Asset Z."
            *   **Severity/Priority (Optional):** For internal tracking.

    *   **Drill-Down Capability:** Clicking an alert or flagged potential should provide a more detailed view, possibly including:
        *   Relevant charts showing the metric leading to the alert (e.g., a chart of the VaR leading up to the breach).
        *   Links to affected positions or market data.
        *   Space for logging investigation notes and actions taken.

## 4. Stress Testing / Scenario Analysis Display

This section allows the Risk Manager to define, run, and review the results of stress tests and scenario analyses.

*   **Layout:** A dedicated "Stress Testing" or "Scenario Analysis" tab.

*   **Components:**

    *   **Scenario Definition Interface (Input Area):**
        *   **Predefined Scenarios List:** A selection of built-in scenarios (e.g., "2008 Financial Crisis Repeat," "Interest Rate Shock +2%," "Tech Bubble Burst," "Specific Geopolitical Event").
        *   **Custom Scenario Builder:**
            *   Input fields for defining shocks to various factors:
                *   Market indices (e.g., S&P 500 down X%).
                *   Interest rates (e.g., parallel shift up/down by X bps).
                *   Volatility (e.g., VIX up X points).
                *   FX rates (e.g., EUR/USD down X%).
                *   Commodity prices (e.g., Oil price up/down X%).
                *   Specific asset price shocks.
            *   Option to define correlation shifts during the scenario.
            *   Ability to save custom scenarios for reuse.
        *   **"Run Test" Button.**

    *   **Results Display Area:**
        *   After running a test, results are displayed clearly:
            *   **Scenario Name/Parameters Used:** Clearly states what was tested.
            *   **Overall Portfolio Impact:**
                *   Projected P&L change (absolute and percentage).
                *   Projected VaR/CVaR under the scenario.
            *   **Impact on Key Metrics:** Table showing changes to volatility, liquidity metrics, etc.
            *   **Worst Hit Positions/Sectors:** List of assets or sectors that would be most affected, with their individual projected P&L.
            *   **Visualizations:**
                *   Bar chart showing P&L impact by asset, sector, or strategy.
                *   A "before vs. after" comparison of the portfolio's risk profile (e.g., VaR gauge).
        *   **Comparison Tool:** Ability to select and compare results from multiple stress tests side-by-side.
        *   **Historical Test Log:** A table listing previously run stress tests with their summary results and a link to the full detailed report.

This detailed structure for the Risk Manager view aims to provide a powerful and intuitive interface for managing diverse aspects of portfolio risk, from real-time monitoring to proactive scenario analysis. Clear visualizations and actionable alerts are prioritized.
