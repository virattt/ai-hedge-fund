# User Controls for System Parameters and Safeguards

This document details the user interface (UI) components and mechanisms for adjusting system parameters, focusing on risk settings and AI agent influence. It also outlines the necessary safeguards, warning messages, and access control considerations. This design builds upon the overall platform structure and component descriptions in existing `.md` files.

These controls are primarily intended to be located within a dedicated "Settings" area of the platform, accessible via the main sidebar, as outlined in `ui_structure.md`. Some context-specific controls might also appear in relevant views (e.g., Risk Manager) with a clear link back to the main Settings panel for comprehensive adjustments.

## 1. Risk Parameter Adjustments

Users with appropriate permissions can adjust certain risk parameters to align the system's behavior with their risk appetite and strategies.

*   **Location:** Primarily within "Settings > Risk Management Configuration." A summary of key global risk parameters might be displayed (read-only for most) on the Risk Manager dashboard.

*   **Key Adjustable Risk Parameters and UI Elements:**

    *   **Overall Portfolio Risk Tolerance:**
        *   **UI Element:** A dropdown selector or a slider with clearly defined qualitative levels (e.g., "Conservative," "Moderate," "Balanced," "Aggressive," "Highly Aggressive").
        *   **Description:** Each level would correspond to a pre-calibrated set of underlying quantitative targets (e.g., target VaR range, target volatility range) that are explained in a tooltip or adjacent text.
        *   **Safeguard:** Changing this setting would require confirmation and display a warning about the implications (see Section 3).

    *   **Global Stop-Loss Percentage (Portfolio Level):**
        *   **UI Element:** Numerical input field with a percentage sign (e.g., `[ 5.0 ] %`). Input is validated to be within a sensible range (e.g., 0.5% to 20%).
        *   **Description:** "Maximum acceptable loss for the entire portfolio over a defined period (e.g., daily or weekly) before automated risk-reducing measures are triggered (if applicable) or a critical alert is issued."
        *   **Range Limits:** Min/max values enforced. Tooltip suggests typical ranges.

    *   **Maximum Position Size (Single Asset):**
        *   **UI Element:** Numerical input field, as a percentage of total portfolio value (e.g., `[ 10.0 ] %`).
        *   **Description:** "Set the maximum allowable investment in any single asset to control concentration risk."
        *   **Range Limits:** Min/max values enforced (e.g., 1% to 25%).

    *   **Sector Exposure Limits:**
        *   **UI Element:** A table where each row represents a market sector (e.g., "Technology," "Healthcare," "Energy"). Each row has a numerical input field for maximum percentage allocation (e.g., `[ 25.0 ] %`).
        *   **Description:** "Define maximum portfolio exposure to specific market sectors."
        *   **Safeguard:** The sum of all sector limits does not necessarily have to be 100%, but a warning could appear if it's excessively high (e.g., >200%) or if a single sector is set very high.

    *   **VaR Limit (Portfolio Level):**
        *   **UI Element:** Numerical input field for the VaR value (e.g., `[ 100,000 ] USD`) and dropdowns to select confidence level (e.g., 95%, 99%) and time horizon (e.g., 1-day, 1-week).
        *   **Description:** "Set the maximum Value at Risk for the portfolio at the chosen confidence and horizon."
        *   **Safeguard:** Directly linked to the "Overall Portfolio Risk Tolerance." Adjusting one may suggest adjustments to the other. Setting a VaR significantly different from the tolerance profile triggers a warning.

    *   **Automated Stop-Loss per Trade (Optional, if feature exists):**
        *   **UI Element:** Toggle switch (Enable/Disable) and a numerical input field for percentage (e.g., `[ 2.0 ] %` below entry price).
        *   **Description:** "Enable/disable automatic stop-loss orders for individual trades and set the percentage."

*   **Visual Cues:**
    *   Input fields might change color (e.g., yellow border) if a value is near a recommended limit, or red if it's outside a hard limit or considered high-risk.
    *   A small "info" icon next to each parameter can provide a detailed explanation on hover.

## 2. Agent Weighting Adjustments

This allows users (typically senior portfolio managers or admins) to adjust the influence of different AI agents on the aggregated signal used by the Portfolio Manager.

*   **Location:** "Settings > AI Agent Configuration > Weighting Scheme." A read-only display of current weights might be visible in the Portfolio Manager or individual Agent views.

*   **UI Elements for Adjusting Agent Weights:**

    *   **Slider-Based Adjustment with Sum-to-100% Constraint:**
        *   **UI Element:** A list of all signal-generating AI agents. Each agent has:
            *   Agent Name.
            *   A horizontal slider to adjust its weight.
            *   A numerical input field displaying the current weight (e.g., `[ 30.0 ] %`), which updates with the slider and can also be directly edited.
        *   **Constraint:** The system ensures that the sum of all agent weights always equals 100%. As one slider is increased, others might automatically decrease proportionally, or a "Remaining %" display helps the user balance.
        *   **Visual Feedback:** A pie chart or bar graph dynamically updates to show the current weight distribution.

    *   **Include/Exclude Toggle:**
        *   **UI Element:** A toggle switch (Enabled/Disabled) next to each agent in the weighting list.
        *   **Functionality:** Allows an agent to be temporarily excluded from the aggregated signal calculation (its weight becomes 0%, and the remaining agents' weights are re-normalized to sum to 100%).

    *   **Weighting Profiles/Presets (Optional):**
        *   **UI Element:** A dropdown to select predefined weighting schemes (e.g., "Balanced," "Sentiment-Focused," "Technicals-Heavy," "Risk-Averse Default").
        *   **Functionality:** Selecting a preset automatically adjusts the sliders/inputs to the defined weights. Users can then fine-tune from there.

*   **Clear Indication of Current Scheme:**
    *   The current active weights are always clearly displayed, both numerically and visually (e.g., pie chart).
    *   A timestamp of "Last Weighting Change" is shown.

## 3. Warning Messages and Safeguards

These are crucial for preventing accidental or uninformed decisions that could lead to undesirable outcomes.

*   **General Principles:**
    *   **Contextual Warnings:** Displayed directly next to the parameter being adjusted.
    *   **Clarity:** Messages should be easy to understand, avoid jargon where possible, and clearly state the potential consequences.
    *   **Actionable:** Suggest alternatives or recommended ranges if possible.

*   **Warning Message Examples:**

    *   **For Risk Parameters:**
        *   When increasing "Overall Portfolio Risk Tolerance": *"Warning: Setting risk tolerance to 'Highly Aggressive' significantly increases potential for large losses. This setting is above the recommended range for most strategies. Are you sure you want to proceed?"* (Confirmation Dialog)
        *   When setting "Maximum Position Size" too high: *"Warning: A maximum position size of [value]% is highly concentrated and can lead to substantial losses if that single asset performs poorly. Recommended range: 5-15%."* (Inline message, input field border turns yellow/red).
        *   When setting "VaR Limit" very high: *"Caution: The entered VaR limit of [value] USD is significantly higher than historical levels and may expose the portfolio to extreme risk."*
    *   **For Agent Weighting:**
        *   When significantly reducing the weight of a key agent (e.g., a custom "Risk Overlay Agent" or a primary data-validation agent): *"Warning: Reducing the weight of '[Agent Name]' below [X]% may impair the system's ability to [its function, e.g., 'effectively manage risk' or 'validate data quality']. Consider the impact carefully."*
        *   When disabling an agent: *"You are about to disable '[Agent Name]'. Its signals will no longer contribute to trading decisions. Are you sure?"* (Confirmation Dialog)
    *   **For any critical change:**
        *   A generic confirmation: *"You have made significant changes to system parameters. These changes can materially affect performance and risk. [View Summary of Changes] Are you sure you want to apply these settings?"* (Confirmation Dialog with a link to see what exactly was changed).

*   **Confirmation Dialogs:**
    *   Used for changes that have a high potential impact (e.g., changing overall risk tolerance, disabling key agents, applying a large set of changes).
    *   Typically include "Confirm" and "Cancel" buttons. The "Confirm" button might be disabled for a few seconds to encourage reading the message.

*   **Visual Cues for High-Risk Settings:**
    *   **Color Changes:** Input fields, sliders, or text labels associated with high-risk settings turn yellow (caution) or red (high risk/outside recommended range).
    *   **Warning Icons:** A small warning triangle (⚠️) appears next to parameters set to potentially risky values. Hovering over the icon shows a tooltip with the warning.
    *   **Dashboard Indicators:** If certain global settings are in a "high-risk" state, a persistent but non-intrusive warning icon or banner might appear on the main dashboard or the Settings page header.

## 4. Permissions and Access Control (Conceptual)

While detailed role-based access control (RBAC) is a larger implementation, the UI design should acknowledge its necessity.

*   **Principle:** Not all users should have access to all controls.
*   **UI Implications:**
    *   **Read-Only States:** For users without modification rights, input fields, sliders, and toggles will be disabled (greyed out) and display the current settings in a read-only format.
    *   **Hidden Controls:** Entire sections of the Settings panel might be hidden for users with limited roles (e.g., a "Junior Analyst" might not see "Agent Weighting Adjustments" at all).
    *   **Role Information:** A small, non-editable text field might indicate the user's current role (e.g., "Logged in as: Portfolio Manager") to provide context for available controls.
    *   **"Request Change" Workflow (Optional):** For users without direct edit rights, a button like "Request Parameter Change" could initiate a workflow where they can propose changes for review by an administrator or senior manager.

## 5. Reset to Defaults

Provides a safety net, allowing users to revert to a known, stable configuration.

*   **UI Element:**
    *   A clearly labeled "Reset to Default Settings" button within each major section of the Settings panel (e.g., "Reset Risk Parameters," "Reset Agent Weights").
    *   A global "Reset All Settings to Defaults" button might also be available, with a more stringent confirmation.
*   **Functionality:**
    *   Restores all parameters in that section (or globally) to their system-defined default values. These defaults should be sensible, conservative, and well-tested.
*   **Confirmation:**
    *   A confirmation dialog is essential: *"Are you sure you want to reset all [section name] settings to their default values? Any custom configurations will be lost."*

This framework for user controls aims to balance flexibility with safety, providing expert users with the means to tune the system while guiding them with clear warnings and safeguards to prevent unintended consequences. The conceptual inclusion of permissions ensures that such powerful controls are appropriately managed.
