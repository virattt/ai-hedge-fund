# UI Components for Portfolio Manager View

This document details the UI components for the Portfolio Manager view, a central hub for decision-making based on AI agent inputs and risk considerations. It integrates with the overall platform structure (`ui_structure.md`) and leverages elements from `agent_analysis_ui.md` and `risk_manager_ui.md`.

The Portfolio Manager view is accessed from the main sidebar. Its header will state "Portfolio Manager Dashboard." The view will likely be organized into tabs or distinct sections for clarity.

## 1. Aggregated Agent Signals View

This section provides a consolidated view of trading signals from all active AI agents, allowing the Portfolio Manager to gauge overall sentiment and identify consensus or divergence.

*   **Layout:** A dedicated "Aggregated Signals" tab or a prominent section on the main Portfolio Manager dashboard.

*   **Components:**

    *   **Asset-Centric Aggregation Table/Dashboard:**
        *   **Primary View:** A table where each row represents an asset (e.g., AAPL, EUR/USD, BTC).
        *   **Columns:**
            *   **Asset:** Symbol and Name.
            *   **Current Price:** Real-time price.
            *   **[Agent 1 Name (e.g., Sentiment Agent)] Signal:** Displays the current signal (BUY, SELL, HOLD, N/A) from this agent for the asset. Color-coded for clarity (Green for BUY, Red for SELL, Gray for HOLD).
            *   **[Agent 1 Name] Confidence:** Displays the confidence level (e.g., percentage, High/Med/Low) for that agent's signal.
            *   **[Agent 2 Name (e.g., Technical Agent)] Signal:** Similar to above.
            *   **[Agent 2 Name] Confidence:** Similar to above.
            *   *(Repeat for all relevant AI agents)*
            *   **Overall Consensus Signal:** A calculated signal based on a configurable weighting of agent signals (e.g., "Strong BUY", "Weak SELL", "Neutral"). This is the raw, pre-risk-adjustment consensus.
            *   **Consensus Strength/Agreement Level:** A visual indicator (e.g., a bar, number of agents in agreement like "3/4 Agents BUY") showing how many agents agree on the consensus signal, or the weighted strength of the consensus.
            *   **Last Signal Update (Overall):** Timestamp of the latest signal update from any agent for that asset.
        *   **Filtering & Sorting:**
            *   Filter by asset class, specific agent signals (e.g., show all assets where Sentiment Agent is "BUY"), or consensus strength.
            *   Sort by asset name, consensus strength, or last signal update.
        *   **Drill-Down:** Clicking on an asset row could expand to show more details, such as the rationale from each agent for their signal (linking to the detailed views in `agent_analysis_ui.md`).

    *   **Agent-Centric View (Alternative or Supplementary):**
        *   A view where each primary card or section represents an AI agent.
        *   Within each agent's card, it lists its top current signals (e.g., top 5 BUYs, top 5 SELLs) with asset, signal strength, and confidence.
        *   Useful for understanding what each agent is "pushing" most strongly.

    *   **Visualizing Consensus/Disagreement:**
        *   **Heatmap Overlay:** In the asset-centric table, cells can be color-coded more intensely based on confidence, making strong-conviction signals stand out.
        *   **Disagreement Flags:** Assets with significant disagreement among high-weight agents could be flagged with an icon (e.g., a warning triangle).
        *   **Dedicated "High Disagreement" Widget:** A small panel highlighting assets where agents have strong but opposing signals.

## 2. Risk-Adjusted Recommendations Display

This section presents the final trading recommendations after the system (or the Portfolio Manager using system aids) has considered the raw aggregated signals in conjunction with inputs from the Risk Manager view (e.g., limits, stress test insights).

*   **Layout:** A dedicated "Trade Recommendations" or "Proposed Actions" tab/section. This is a crucial decision-support area.

*   **Components:**

    *   **Recommendations Table/List:**
        *   Displays actionable trading recommendations.
        *   **Columns:**
            *   **Asset:** Symbol and Name.
            *   **Proposed Action:** (e.g., "BUY", "SELL", "HOLD", "REDUCE EXPOSURE", "INCREASE EXPOSURE"). Color-coded.
            *   **Recommended Quantity/Size:** Specific number of shares, contracts, or notional value.
            *   **Target Price (Optional):** If applicable.
            *   **Priority/Conviction:** (e.g., High, Medium, Low) based on the combined strength of signals and risk assessment.
            *   **Aggregated Agent Signal:** The raw consensus signal (e.g., "Strong BUY") for comparison.
            *   **Risk Adjustment Rationale:** A concise explanation if the Proposed Action or size differs from the raw Aggregated Agent Signal. This is critical for transparency.
                *   Examples:
                    *   "Reduced BUY quantity from 1000 to 500 shares due to approaching single-stock concentration limit."
                    *   "HOLDING asset despite BUY signal due to high overall portfolio VaR; awaiting market stabilization."
                    *   "SELL recommendation downgraded from Strong to Weak due to conflicting Technical Agent signal."
                    *   "No action despite BUY signal; current market volatility exceeds risk tolerance for new positions in this sector."
            *   **Key Supporting Factors:** Brief list of positive/negative factors (e.g., "Strong Sentiment, Positive Fundamentals, Breaching Volatility Limit").
            *   **Action Buttons:** (e.g., "Execute Trade," "Analyze Further," "Dismiss for Now").

    *   **Pre-Trade Risk Impact Assessment Widget:**
        *   When a specific recommendation is selected or a trade is being modeled:
            *   Displays the potential impact of the proposed trade on key portfolio risk metrics *before execution*.
            *   **Pro-forma Metrics:** Shows current vs. projected VaR, sector exposure, concentration, drawdown risk, etc.
            *   Visual cues (green/yellow/red) if the trade would bring any metric closer to or in breach of limits.
            *   This directly links to the capabilities described in `risk_manager_ui.md`.

    *   **Rationale Pop-ups/Expandable Sections:**
        *   Clicking on the "Risk Adjustment Rationale" cell or an info icon could reveal more detailed explanations, referencing specific risk limits, market conditions, or stress test results that influenced the decision.

## 3. Executed Trades and Current Portfolio Holdings

This section provides a transparent view of trading activity and the current state of the portfolio.

*   **Layout:** Two distinct tabs or sub-sections: "Trade Log" and "Current Holdings."

*   **A. Trade Log Components:**
    *   **Table View:**
        *   **Columns:**
            *   **Timestamp (Execution):** Date and time of trade execution.
            *   **Asset:** Symbol and Name.
            *   **Direction:** BUY / SELL.
            *   **Quantity:** Number of shares/contracts.
            *   **Execution Price:** Price at which the trade was filled.
            *   **Notional Value:** Total value of the trade.
            *   **Fees/Commissions (Optional):** If available.
            *   **Strategy/Agent(s) Triggering:** Which agent(s) or strategy led to this trade.
            *   **Order ID:** From the execution venue.
            *   **Status:** (e.g., Filled, Partially Filled - though typically only filled trades shown here).
        *   **Filtering:** By date range, asset, direction, triggering agent.
        *   **Sorting:** By any column.
        *   **Export Functionality:** Option to export the trade log (e.g., to CSV).

*   **B. Current Portfolio Holdings Components:**
    *   **Table View:**
        *   **Columns:**
            *   **Asset:** Symbol and Name.
            *   **Quantity:** Current number of shares/contracts held.
            *   **Average Cost Price:** The weighted average price of acquisition.
            *   **Current Market Price:** Real-time price.
            *   **Market Value:** Quantity * Current Market Price.
            *   **Unrealized P&L:** (Market Value - (Quantity * Average Cost Price)). Displayed as absolute value and percentage. Color-coded (green for profit, red for loss).
            *   **% of Portfolio:** Percentage this holding represents of the total portfolio market value.
            *   **Daily P&L:** Profit or loss for the current trading day.
            *   **Asset Class/Sector:** For grouping and risk analysis.
        *   **Filtering:** By asset class, sector, performance (e.g., show only losing positions).
        *   **Sorting:** By asset name, market value, % of portfolio, unrealized P&L.
        *   **Summary Row/Panel:** Shows total portfolio market value, total unrealized P&L, total daily P&L.
    *   **Visualizations (Optional, in a dashboard section above or alongside the table):**
        *   **Pie Chart:** Showing portfolio allocation by asset class or sector.
        *   **Treemap:** Visualizing position sizes by market value.

## 4. Audit Trail Display

This section provides a comprehensive and searchable log of all significant decisions, actions, and system events related to portfolio management. This is crucial for compliance, review, and debugging.

*   **Layout:** A dedicated "Audit Log" or "Decision History" tab.

*   **Components:**

    *   **Comprehensive Log Table:**
        *   **Columns:**
            *   **Timestamp:** Precise date and time of the event/decision.
            *   **Event ID:** Unique identifier for the log entry.
            *   **Category/Type:** (e.g., "Signal Generation," "Risk Assessment," "Trade Recommendation," "Order Placement," "Parameter Change," "User Action").
            *   **Source/Actor:** Who or what initiated the event (e.g., "Sentiment Agent," "Risk Manager System," "Portfolio Manager [User Name]," "Technical Agent").
            *   **Asset(s) Involved (if any):** Specific instruments affected.
            *   **Summary/Description:** A concise human-readable description of the event.
                *   *Signal:* "Sentiment Agent generated BUY signal for AAPL, Confidence: 78%, Rationale: Positive news spike."
                *   *Recommendation:* "System recommended BUY 100 AAPL. Risk Adjustment: None. Supporting Agents: Sentiment, Fundamentals."
                *   *Risk Adjustment:* "System adjusted BUY 100 AAPL to BUY 50 AAPL. Rationale: Approaching single-stock concentration limit (Current: 8%, Limit: 10%, Post-Trade Projection: 9.5%)."
                *   *User Action:* "Portfolio Manager [User Name] executed BUY 50 AAPL at $150.20."
                *   *Parameter Change:* "User [Admin Name] changed Sentiment Agent weight from 0.3 to 0.4 in portfolio model 'AlphaMax'."
            *   **Key Data Points/Context:** Snapshot of critical data influencing the event (e.g., "VaR at time: $120k," "Sentiment Score: +0.65," "Relevant Limit: Sector Exposure < 20%"). This might be a JSON blob or a summarized text.
            *   **Previous Value / New Value (for changes):** If applicable.
        *   **Advanced Filtering:**
            *   By date/time range.
            *   By Category/Type.
            *   By Source/Actor.
            *   By Asset(s) Involved.
            *   By specific keywords in the Description or Key Data Points.
        *   **Sorting:** By timestamp (default), category, source.
        *   **Drill-Down/View Details:** Clicking a log entry could open a modal or a separate pane showing all associated data in a more structured format, including links to relevant agent analyses or risk reports at that point in time.
        *   **Export Functionality:** For compliance and external review.

    *   **Integrity Features:**
        *   The audit log should be immutable or have strong controls to prevent tampering.
        *   Regular backups.

This detailed design for the Portfolio Manager view aims to provide a powerful, transparent, and auditable interface for making informed trading decisions based on AI-driven insights and comprehensive risk management.
