
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np
import sys
import os
from dotenv import load_dotenv
import matplotlib as mpl

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Import necessary modules from the project
from src.backtester import Backtester
from src.main import run_hedge_fund
from src.llm.models import LLM_ORDER, get_model_info, ModelProvider
from src.utils.analysts import ANALYST_ORDER

# Set up matplotlib to use colors that work in both light and dark mode
plt.style.use('default')  # Reset to default style

# Define a function to get theme-based colors
def get_theme_colors(is_dark_theme=False):
    if is_dark_theme:
        return {
            'primary': '#8ab4f8',       # Light blue for dark theme
            'success': '#81c995',       # Light green for dark theme
            'error': '#f28b82',         # Light red for dark theme
            'warning': '#fdd663',       # Light yellow for dark theme
            'neutral': '#9aa0a6',       # Light gray for dark theme
            'background': '#202124',    # Dark background
            'text': '#e8eaed',          # Light text for dark theme
            'grid': '#5f6368',          # Grid lines for dark theme
        }
    else:
        return {
            'primary': '#1a73e8',       # Blue for light theme
            'success': '#0f9d58',       # Green for light theme
            'error': '#d93025',         # Red for light theme
            'warning': '#f9ab00',       # Yellow/orange for light theme
            'neutral': '#5f6368',       # Gray for light theme
            'background': '#ffffff',    # Light background
            'text': '#202124',          # Dark text for light theme
            'grid': '#dadce0',          # Grid lines for light theme
        }

# Function to detect if Streamlit is in dark mode
def is_dark_theme():
    try:
        # This is a hack to detect dark theme in Streamlit
        # It may not always work, but it's a reasonable approximation
        return st.get_option("theme.base") == "dark"
    except:
        return False

# Get theme colors based on current theme
theme_colors = get_theme_colors(is_dark_theme())

# Set default matplotlib colors based on theme
mpl.rcParams['axes.facecolor'] = 'none'  # Transparent background
mpl.rcParams['figure.facecolor'] = 'none'  # Transparent figure
mpl.rcParams['axes.edgecolor'] = theme_colors['grid']
mpl.rcParams['axes.labelcolor'] = theme_colors['text']
mpl.rcParams['xtick.color'] = theme_colors['text']
mpl.rcParams['ytick.color'] = theme_colors['text']
mpl.rcParams['grid.color'] = theme_colors['grid']
mpl.rcParams['text.color'] = theme_colors['text']

# Set page configuration
st.set_page_config(
    page_title="AI Hedge Fund Backtester",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Add custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: var(--primary-color, #4CAF50);
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: var(--secondary-background-color, #2196F3);
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: rgba(128, 128, 128, 0.1);
        border-radius: 5px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    .positive {
        color: var(--success-color, #4CAF50);
        font-weight: bold;
    }
    .negative {
        color: var(--error-color, #F44336);
        font-weight: bold;
    }
    .decision-card {
        background-color: rgba(128, 128, 128, 0.05);
        border-left: 4px solid var(--primary-color, #2196F3);
        border-radius: 3px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    .decision-date {
        font-weight: bold;
        color: var(--text-color, #333);
        margin-bottom: 0.5rem;
    }
    .decision-ticker {
        font-weight: bold;
        color: var(--primary-color, #1976D2);
    }
    .decision-action-buy {
        color: var(--success-color, #4CAF50);
        font-weight: bold;
    }
    .decision-action-sell {
        color: var(--error-color, #F44336);
        font-weight: bold;
    }
    .decision-action-short {
        color: var(--warning-color, #9C27B0);
        font-weight: bold;
    }
    .decision-action-cover {
        color: var(--warning-color, #FF9800);
        font-weight: bold;
    }
    .decision-action-hold {
        color: var(--text-color, #607D8B);
        font-weight: bold;
    }
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    /* Additional styles for better dark/light mode compatibility */
    div[data-testid="stExpander"] {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 5px;
    }
    div.stDataFrame {
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    /* Ensure background colors for analyst cards are adaptive */
    div[style*="background-color: #f0f7ff"],
    div[style*="background-color: #fff8f0"],
    div[style*="background-color: #f0fff8"],
    div[style*="background-color: #f5f5f5"],
    div[style*="background-color: #f9f9f9"] {
        background-color: rgba(128, 128, 128, 0.1) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar for inputs
st.sidebar.markdown('<div class="sub-header">Configuration</div>', unsafe_allow_html=True)

# Ticker input
ticker_input = st.sidebar.text_input(
    "Stock Tickers (comma-separated)",
    value="AAPL,MSFT",
    help="Enter stock tickers separated by commas (e.g., AAPL,MSFT,GOOGL)"
)
tickers = [ticker.strip() for ticker in ticker_input.split(",") if ticker.strip()]

# Date range selection
today = datetime.now()
day_before_yesterday = today - timedelta(days=2)
default_end_date = day_before_yesterday.strftime("%Y-%m-%d")
default_start_date = (today - relativedelta(days=3)).strftime("%Y-%m-%d")

col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.strptime(default_start_date, "%Y-%m-%d"),
        max_value=today - timedelta(days=1),
    )
with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.strptime(default_end_date, "%Y-%m-%d"),
        max_value=day_before_yesterday,
    )

# Convert date inputs to string format
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# Initial capital
initial_capital = st.sidebar.number_input(
    "Initial Capital ($)",
    min_value=1000.0,
    max_value=10000000.0,
    value=100000.0,
    step=10000.0,
    help="Initial capital amount for the backtest"
)

# Margin requirement
margin_requirement = st.sidebar.slider(
    "Margin Requirement (%)",
    min_value=0.0,
    max_value=100.0,
    value=0.0,
    step=5.0,
    help="Margin ratio for short positions (e.g., 50% means 50% margin required)"
) / 100.0

# LLM model selection
# Filter LLM_ORDER to only include DeepSeek models
deepseek_models = [(display, value, provider) for display, value, provider in LLM_ORDER if provider == ModelProvider.DEEPSEEK.value]

# Check if there are any DeepSeek models available
if not deepseek_models:
    st.error("No DeepSeek models are available. Please check your configuration.")
    st.stop()

model_options = [display for display, value, _ in deepseek_models]
model_values = [value for display, value, _ in deepseek_models]
model_display_to_value = {display: value for display, value, _ in deepseek_models}

# Add a note about DeepSeek models
st.sidebar.info("Only DeepSeek models are available for selection.")

selected_model_display = st.sidebar.selectbox(
    "LLM Model",
    options=model_options,
    index=0,
    help="Select the LLM model to use for trading decisions"
)
selected_model = model_display_to_value[selected_model_display]

# Get model provider
model_info = get_model_info(selected_model)
model_provider = model_info.provider.value if model_info else "Unknown"

# Analyst selection
analyst_options = [display for display, value in ANALYST_ORDER]
analyst_values = [value for display, value in ANALYST_ORDER]
analyst_display_to_value = {display: value for display, value in ANALYST_ORDER}

selected_analyst_displays = st.sidebar.multiselect(
    "Select Analysts",
    options=analyst_options,
    default=analyst_options[:3],  # Default to first 3 analysts
    help="Select the analysts to include in the backtest"
)
selected_analysts = [analyst_display_to_value[display] for display in selected_analyst_displays]

# Run backtest button
run_button = st.sidebar.button("Run Backtest", type="primary")

# Main content area
if not tickers:
    st.warning("Please enter at least one ticker symbol.")
elif start_date >= end_date:
    st.warning("Start date must be before end date.")
elif not selected_analysts:
    st.warning("Please select at least one analyst.")
elif end_date > day_before_yesterday.date():
    st.warning("End date cannot be later than the day before yesterday. Please select a valid end date.")
elif run_button:
    # Store the fact that we've run a backtest
    st.session_state.backtest_run = True

    with st.spinner("Running backtest..."):
        # Create progress bar
        progress_bar = st.progress(0)
        progress_value = 0.0

        # Create and run the backtester
        backtester = Backtester(
            agent=run_hedge_fund,
            tickers=tickers,
            start_date=start_date_str,
            end_date=end_date_str,
            initial_capital=initial_capital,
            model_name=selected_model,
            model_provider=model_provider,
            selected_analysts=selected_analysts,
            initial_margin_requirement=margin_requirement,
        )

        # Override the print function to update progress
        original_print = print
        # Create a class to store and update progress value
        class ProgressTracker:
            def __init__(self, initial_value=0.0):
                self.value = initial_value

            def increment(self):
                self.value = min(0.9, self.value + 0.05)
                return self.value

        # Initialize progress tracker
        progress_tracker = ProgressTracker()

        def progress_print(*args, **kwargs):
            original_print(*args, **kwargs)
            # Update progress bar (this is approximate since we don't know total steps)
            progress_bar.progress(progress_tracker.increment())

        # Monkey patch print function
        import builtins
        builtins.print = progress_print

        try:
            # Run the backtest
            performance_metrics = backtester.run_backtest()
            performance_df = backtester.analyze_performance()

            # Store results in session state for later use
            st.session_state.performance_metrics = performance_metrics
            st.session_state.performance_df = performance_df
            st.session_state.backtester = backtester
            st.session_state.initial_capital = initial_capital

            # Set progress to complete
            progress_bar.progress(1.0)

        finally:
            # Restore original print function
            builtins.print = original_print

# Display results if a backtest has been run
if 'backtest_run' in st.session_state and st.session_state.backtest_run:
    # Get stored results from session state
    performance_metrics = st.session_state.performance_metrics
    performance_df = st.session_state.performance_df
    backtester = st.session_state.backtester
    initial_capital = st.session_state.initial_capital

    # Display results
    st.markdown('<div class="sub-header">Backtest Results</div>', unsafe_allow_html=True)

    # Performance metrics in cards
    col1, col2, col3 = st.columns(3)

    # Calculate total return
    if not performance_df.empty:
        final_portfolio_value = performance_df["Portfolio Value"].iloc[-1]
        total_return = ((final_portfolio_value - initial_capital) / initial_capital) * 100

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total Return</h3>
                <p class="{'positive' if total_return >= 0 else 'negative'}">{total_return:.2f}%</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            sharpe_ratio = performance_metrics.get('sharpe_ratio', 0) if performance_metrics else 0
            st.markdown(f"""
            <div class="metric-card">
                <h3>Sharpe Ratio</h3>
                <p class="{'positive' if sharpe_ratio is not None and sharpe_ratio >= 1 else 'negative'}">{sharpe_ratio if sharpe_ratio is not None else 0:.2f}</p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            max_drawdown = performance_metrics.get('max_drawdown', 0) if performance_metrics else 0
            st.markdown(f"""
            <div class="metric-card">
                <h3>Max Drawdown</h3>
                <p class="negative">{max_drawdown if max_drawdown is not None else 0:.2f}%</p>
            </div>
            """, unsafe_allow_html=True)

        # Portfolio value chart
        st.markdown("### Portfolio Value Over Time")
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(performance_df.index, performance_df["Portfolio Value"], color=theme_colors['primary'])
        ax.set_title("Portfolio Value Over Time")
        ax.set_ylabel("Portfolio Value ($)")
        ax.set_xlabel("Date")
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

        # Daily returns chart
        st.markdown("### Daily Returns")
        fig, ax = plt.subplots(figsize=(12, 6))
        # Ensure we have valid data for the daily returns
        if "Daily Return" in performance_df.columns and not performance_df["Daily Return"].isnull().all():
            performance_df["Daily Return"].plot(kind="bar", ax=ax, color=performance_df["Daily Return"].apply(
                lambda x: theme_colors['success'] if x >= 0 else theme_colors['error']))
            ax.set_title("Daily Returns")
            ax.set_ylabel("Return (%)")
            ax.set_xlabel("Date")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
        else:
            st.warning("No daily return data available.")

        # Exposure chart
        if "Long Exposure" in performance_df.columns and "Short Exposure" in performance_df.columns:
            st.markdown("### Long/Short Exposure")
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(performance_df.index, performance_df["Long Exposure"], color=theme_colors['success'], label="Long Exposure")
            ax.plot(performance_df.index, performance_df["Short Exposure"], color=theme_colors['error'], label="Short Exposure")
            ax.plot(performance_df.index, performance_df["Net Exposure"], color=theme_colors['primary'], label="Net Exposure")
            ax.set_title("Portfolio Exposure Over Time")
            ax.set_ylabel("Exposure ($)")
            ax.set_xlabel("Date")
            ax.legend()
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)

        # Detailed performance table
        st.markdown("### Detailed Performance")
        st.dataframe(performance_df)

        # Portfolio Manager Decisions
        st.markdown("### Portfolio Manager Decisions")

        # Get the trading decisions from the backtester
        if hasattr(backtester, 'trading_decisions') and backtester.trading_decisions:
            # Group decisions by date
            decisions_by_date = {}
            for date, ticker_decisions in backtester.trading_decisions.items():
                if date not in decisions_by_date:
                    decisions_by_date[date] = []

                if ticker_decisions:  # Check if ticker_decisions is not None
                    for ticker, decision in ticker_decisions.items():
                        if decision and (decision.get('action') != 'hold' or decision.get('quantity', 0) > 0):
                            decisions_by_date[date].append({
                                'ticker': ticker,
                                'action': decision.get('action', 'hold'),
                                'quantity': decision.get('quantity', 0),
                                'confidence': decision.get('confidence', 0),
                                'reasoning': decision.get('reasoning', 'No reasoning provided')
                            })

            # Display decisions by date
            if decisions_by_date:  # Check if we have any decisions to display
                # Get all trading dates
                trading_dates = sorted(decisions_by_date.keys())

                # Initialize session state for selected trading day if not already set
                if 'selected_trading_day' not in st.session_state:
                    st.session_state.selected_trading_day = trading_dates[0] if trading_dates else ""

                # Create callback function to update session state
                def update_trading_day():
                    st.session_state.selected_trading_day = st.session_state.trading_day_selector

                # Create a date selector with key and on_change callback
                trading_day_selector = st.selectbox(
                    "Select Trading Day",
                    trading_dates,
                    index=trading_dates.index(st.session_state.selected_trading_day) if st.session_state.selected_trading_day in trading_dates else 0,
                    key="trading_day_selector",
                    on_change=update_trading_day
                )

                # Use the value from session state
                selected_trading_day = st.session_state.selected_trading_day

                # Create a container for the decisions to avoid refreshing the entire page
                decisions_container = st.container()

                with decisions_container:
                    st.markdown(f"#### Trading Day: {selected_trading_day}")

                    if not decisions_by_date[selected_trading_day]:
                        st.info("No trading actions taken on this day.")
                    else:
                        for decision in decisions_by_date[selected_trading_day]:
                            action_class = f"decision-action-{decision['action']}"

                            st.markdown(f"""
                            <div class="decision-card">
                                <div class="decision-ticker">{decision['ticker']}</div>
                                <div><span class="{action_class}">{decision['action'].upper()}</span> {decision['quantity']} shares (Confidence: {decision['confidence']:.1f}%)</div>
                                <div><strong>Reasoning:</strong> {decision['reasoning']}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("No trading decisions were made during the backtest period.")
        else:
            st.info("No detailed trading decisions available. This may be because the backtester didn't store the decision reasoning.")

            # Suggest a modification to the backtester
            with st.expander("How to enable detailed decision tracking"):
                st.markdown("""
                To track detailed portfolio manager decisions, you need to modify the backtester to store the decision reasoning:

                1. In `src/backtester.py`, add a dictionary to store decisions in the `__init__` method:
                ```python
                self.trading_decisions = {}
                ```

                2. In the `run_backtest` method, store the decisions with their reasoning:
                ```python
                # Store decisions with reasoning for this date
                self.trading_decisions[current_date_str] = {
                    ticker: {
                        'action': decision.get('action', 'hold'),
                        'quantity': decision.get('quantity', 0),
                        'confidence': decision.get('confidence', 0),
                        'reasoning': decision.get('reasoning', '')
                    }
                    for ticker, decision in decisions.items()
                }
                ```
                """)

        # Signal Explanation Section
        st.markdown("### Signal Analysis and Weighting")

        # Add a brief introduction outside the expander
        st.markdown("""
        The AI Hedge Fund uses a multi-analyst approach where different specialists analyze stocks from various perspectives.
        Each analyst produces a signal (bullish, bearish, or neutral) with a confidence level.
        The Portfolio Manager then considers all these signals to make the final trading decision.
        """)

        # Create tabs for different aspects of signal analysis
        signal_tabs = st.tabs(["Analysts Overview", "Technical Analysis", "Sentiment Analysis", "Decision Process"])

        with signal_tabs[0]:
            st.markdown("""
            ## Available Analysts

            The AI Hedge Fund incorporates perspectives from multiple analysts, each with their own specialty and approach:
            """)

            # Create columns for different analyst categories
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("""
                ### Value Investors

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Warren Buffett</strong><br>
                    Focuses on companies with strong competitive advantages, good management, and reasonable valuations
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Charlie Munger</strong><br>
                    Emphasizes mental models and avoiding psychological biases in investment decisions
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Ben Graham</strong><br>
                    The father of value investing, focuses on margin of safety and quantitative analysis
                </div>

                ### Active Investors

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Bill Ackman</strong><br>
                    Activist investor approach, looking for companies with potential for significant operational improvements
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Cathie Wood</strong><br>
                    Growth-focused, emphasizing disruptive innovation and technological trends
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Stanley Druckenmiller</strong><br>
                    Macro-focused approach with emphasis on capital preservation and concentrated positions
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown("""
                ### Specialized Analysts

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Technical Analyst</strong><br>
                    Uses price patterns and technical indicators to generate trading signals
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Fundamentals Analyst</strong><br>
                    Analyzes financial statements and business fundamentals
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Sentiment Analyst</strong><br>
                    Evaluates market sentiment from news and insider trading activity
                </div>

                <div style="background-color: rgba(128, 128, 128, 0.1); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid rgba(128, 128, 128, 0.2);">
                    <strong>Valuation Analyst</strong><br>
                    Focuses specifically on valuation metrics and fair value estimates
                </div>
                """, unsafe_allow_html=True)

        with signal_tabs[1]:
            st.markdown("""
            ## Technical Analysis Methodology

            The Technical Analyst combines multiple strategies to generate trading signals:
            """)

            # Create a DataFrame for the technical strategies
            tech_strategies = pd.DataFrame({
                "Strategy": ["Trend Following", "Momentum", "Mean Reversion", "Volatility", "Statistical Arbitrage"],
                "Weight": [25, 25, 20, 15, 15],
                "Description": [
                    "Identifies directional price movements using moving averages and ADX",
                    "Measures the rate of price changes using RSI and other momentum indicators",
                    "Identifies overbought/oversold conditions using Bollinger Bands",
                    "Analyzes price volatility patterns using ATR and other volatility measures",
                    "Uses statistical methods to identify pricing inefficiencies"
                ]
            })

            # Display the strategies as a table
            st.table(tech_strategies)

            # Create a pie chart for the weights
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(tech_strategies["Weight"], labels=tech_strategies["Strategy"], autopct='%1.1f%%',
                startangle=90, shadow=True, explode=[0.05, 0.05, 0, 0, 0],
                colors=[theme_colors['error'], theme_colors['primary'], theme_colors['success'],
                        theme_colors['warning'], theme_colors['neutral']])
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
            ax.set_title("Technical Analysis Strategy Weights")
            st.pyplot(fig)

            st.markdown("""
            ### How Technical Signals Are Combined

            The Technical Analyst calculates individual signals for each strategy, then combines them using a weighted average approach.
            The final signal (bullish, bearish, or neutral) is determined by the weighted score:

            - Score > 0.2: Bullish
            - Score < -0.2: Bearish
            - Otherwise: Neutral

            The confidence level is derived from the absolute value of the final score.
            """)

        with signal_tabs[2]:
            st.markdown("""
            ## Sentiment Analysis Methodology

            The Sentiment Analyst evaluates market sentiment from multiple sources:
            """)

            # Create a DataFrame for the sentiment sources
            sentiment_sources = pd.DataFrame({
                "Source": ["News Sentiment", "Insider Trading"],
                "Weight": [70, 30],
                "Description": [
                    "Analyzes sentiment from recent news articles about the company",
                    "Evaluates recent insider buying and selling patterns"
                ]
            })

            # Display the sources as a table
            st.table(sentiment_sources)

            # Create a pie chart for the weights
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(sentiment_sources["Weight"], labels=sentiment_sources["Source"], autopct='%1.1f%%',
                startangle=90, shadow=True, explode=[0.05, 0],
                colors=[theme_colors['primary'], theme_colors['error']])
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
            ax.set_title("Sentiment Analysis Source Weights")
            st.pyplot(fig)

            st.markdown("""
            ### How Sentiment Signals Are Generated

            The Sentiment Analyst:

            1. Collects recent news articles and insider trading data
            2. Classifies each news article as positive, negative, or neutral
            3. Classifies insider transactions as bullish (buying) or bearish (selling)
            4. Applies weights to each source
            5. Determines the final signal based on which weighted count is higher
            6. Calculates confidence based on the proportion of the dominant signal
            """)

        with signal_tabs[3]:
            st.markdown("""
            ## Portfolio Manager Decision Process

            The Portfolio Manager is the final decision-maker that considers all analyst signals along with portfolio constraints:
            """)

            st.markdown("""
            <div style="background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 5px; margin-bottom: 15px; border: 1px solid rgba(128, 128, 128, 0.2);">
                <h3 style="margin-top: 0;">Inputs to the Decision Process</h3>
                <ul>
                    <li><strong>Analyst Signals:</strong> All signals from the selected analysts with their confidence levels</li>
                    <li><strong>Current Portfolio:</strong> Existing positions (long and short) and available cash</li>
                    <li><strong>Risk Limits:</strong> Maximum position sizes determined by the Risk Management Agent</li>
                    <li><strong>Current Prices:</strong> Latest market prices for all tickers</li>
                    <li><strong>Margin Requirements:</strong> Requirements for short positions</li>
                </ul>
            </div>

            <div style="background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 5px; margin-bottom: 15px; border: 1px solid rgba(128, 128, 128, 0.2);">
                <h3 style="margin-top: 0;">Trading Rules</h3>
                <ul>
                    <li><strong>For Long Positions:</strong>
                        <ul>
                            <li>Only buy if you have available cash</li>
                            <li>Only sell if you currently hold long shares of that ticker</li>
                            <li>Sell quantity must be ≤ current long position shares</li>
                            <li>Buy quantity must be ≤ max shares allowed by risk management</li>
                        </ul>
                    </li>
                    <li><strong>For Short Positions:</strong>
                        <ul>
                            <li>Only short if you have available margin</li>
                            <li>Only cover if you currently have short shares of that ticker</li>
                            <li>Cover quantity must be ≤ current short position shares</li>
                            <li>Short quantity must respect margin requirements</li>
                        </ul>
                    </li>
                </ul>
            </div>

            <div style="background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 5px; margin-bottom: 15px; border: 1px solid rgba(128, 128, 128, 0.2);">
                <h3 style="margin-top: 0;">Available Actions</h3>
                <ul>
                    <li><strong style="color: var(--success-color, #4CAF50);">Buy:</strong> Open or add to long position</li>
                    <li><strong style="color: var(--error-color, #F44336);">Sell:</strong> Close or reduce long position</li>
                    <li><strong style="color: var(--warning-color, #9C27B0);">Short:</strong> Open or add to short position</li>
                    <li><strong style="color: var(--warning-color, #FF9800);">Cover:</strong> Close or reduce short position</li>
                    <li><strong style="color: var(--text-color, #607D8B);">Hold:</strong> No action</li>
                </ul>
            </div>

            <div style="background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 5px; border: 1px solid rgba(128, 128, 128, 0.2);">
                <h3 style="margin-top: 0;">Output Decision</h3>
                <p>For each ticker, the Portfolio Manager outputs:</p>
                <ul>
                    <li><strong>Action:</strong> buy, sell, short, cover, or hold</li>
                    <li><strong>Quantity:</strong> Number of shares to trade</li>
                    <li><strong>Confidence:</strong> Confidence level in the decision (0-100%)</li>
                    <li><strong>Reasoning:</strong> Detailed explanation of the decision</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        # Signal Visualization
        if hasattr(backtester, 'trading_decisions') and backtester.trading_decisions:
            st.markdown("### Analyst Signal Visualization")

            # Check if analyst signals are available
            if hasattr(backtester, 'analyst_signals') and backtester.analyst_signals:
                # Get a list of all dates
                all_dates = sorted(backtester.analyst_signals.keys())

                if all_dates:
                    # Create tabs for different visualization modes
                    viz_tabs = st.tabs(["Single Date View", "Date Comparison", "Signal Trend"])

                    # Initialize session state for selected date and ticker if not already set
                    if 'selected_date' not in st.session_state:
                        st.session_state.selected_date = all_dates[0]
                    if 'selected_ticker' not in st.session_state:
                        st.session_state.selected_ticker = tickers[0] if tickers else ""
                    if 'comparison_date' not in st.session_state and len(all_dates) > 1:
                        st.session_state.comparison_date = all_dates[1] if len(all_dates) > 1 else all_dates[0]
                    if 'selected_analyst' not in st.session_state:
                        st.session_state.selected_analyst = "All Analysts"

                    # Create callback functions to update session state
                    def update_selected_date():
                        st.session_state.selected_date = st.session_state.date_selector

                    def update_selected_ticker():
                        st.session_state.selected_ticker = st.session_state.ticker_selector

                    def update_comparison_date():
                        st.session_state.comparison_date = st.session_state.comparison_date_selector

                    def update_selected_analyst():
                        st.session_state.selected_analyst = st.session_state.analyst_selector

                    # Single Date View Tab
                    with viz_tabs[0]:
                        # Create a date selector with key and on_change callback
                        date_selector = st.selectbox(
                            "Select Trading Day",
                            all_dates,
                            index=all_dates.index(st.session_state.selected_date) if st.session_state.selected_date in all_dates else 0,
                            key="date_selector",
                            on_change=update_selected_date
                        )

                        # Create a ticker selector with key and on_change callback
                        ticker_selector = st.selectbox(
                            "Select Ticker",
                            tickers,
                            index=tickers.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in tickers else 0,
                            key="ticker_selector",
                            on_change=update_selected_ticker
                        )

                        # Use the values from session state for visualization
                        selected_date = st.session_state.selected_date
                        selected_ticker = st.session_state.selected_ticker

                        # Get the analyst signals for the selected date
                        date_signals = backtester.analyst_signals.get(selected_date, {})

                        # Create a DataFrame for the signals
                        signal_data = []

                        # Process signals for each analyst
                        for analyst_name, signals in date_signals.items():
                            if analyst_name != "risk_management_agent" and isinstance(signals, dict):
                                # Get the signal for the selected ticker
                                ticker_signal = signals.get(selected_ticker, {})
                                if isinstance(ticker_signal, dict):
                                    signal = ticker_signal.get("signal", "N/A")
                                    confidence = ticker_signal.get("confidence", 0)
                                    signal_data.append({
                                        "Analyst": analyst_name.replace("_agent", "").replace("_", " ").title(),
                                        "Signal": signal.title() if signal else "N/A",
                                        "Confidence": confidence if confidence else 0,
                                        "Color": theme_colors['success'] if signal == "bullish" else (theme_colors['error'] if signal == "bearish" else theme_colors['neutral'])
                                    })

                        if signal_data:
                            signal_df = pd.DataFrame(signal_data)

                            # Create a horizontal bar chart
                            fig, ax = plt.subplots(figsize=(10, len(signal_data) * 0.5 + 2))
                            bars = ax.barh(signal_df["Analyst"], signal_df["Confidence"], color=signal_df["Color"])
                            ax.set_xlabel("Confidence (%)")
                            ax.set_title(f"Analyst Signals for {selected_ticker} on {selected_date}")
                            ax.set_xlim(0, 100)

                            # Add the signal labels to the bars
                            for i, bar in enumerate(bars):
                                ax.text(
                                    bar.get_width() + 2,
                                    bar.get_y() + bar.get_height()/2,
                                    signal_df["Signal"].iloc[i],
                                    va='center'
                                )

                            st.pyplot(fig)

                            # Display the signal data in a table
                            st.dataframe(signal_df[["Analyst", "Signal", "Confidence"]])
                        else:
                            st.info(f"No analyst signals available for {selected_ticker} on {selected_date}")

                    # Date Comparison Tab
                    with viz_tabs[1]:
                        # Create two columns for date selection
                        date_col1, date_col2 = st.columns(2)

                        with date_col1:
                            # Create a date selector with key and on_change callback
                            comparison_date1_selector = st.selectbox(
                                "Date 1",
                                all_dates,
                                index=all_dates.index(st.session_state.selected_date) if st.session_state.selected_date in all_dates else 0,
                                key="comparison_date1_selector",
                                on_change=update_selected_date
                            )

                        with date_col2:
                            # Create a comparison date selector
                            comparison_date2_selector = st.selectbox(
                                "Date 2",
                                all_dates,
                                index=all_dates.index(st.session_state.comparison_date) if st.session_state.comparison_date in all_dates else (1 if len(all_dates) > 1 else 0),
                                key="comparison_date_selector",
                                on_change=update_comparison_date
                            )

                        # Create a ticker selector for comparison
                        comparison_ticker_selector = st.selectbox(
                            "Select Ticker",
                            tickers,
                            index=tickers.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in tickers else 0,
                            key="comparison_ticker_selector",
                            on_change=update_selected_ticker
                        )

                        # Use the values from session state for visualization
                        selected_date = st.session_state.selected_date
                        comparison_date = st.session_state.comparison_date
                        selected_ticker = st.session_state.selected_ticker

                        # Create two columns for side-by-side comparison
                        viz_col1, viz_col2 = st.columns(2)

                        # Function to create signal visualization for a date
                        def create_signal_viz(date, container):
                            with container:
                                st.subheader(f"Signals for {selected_ticker} on {date}")

                                # Get the analyst signals for the selected date
                                date_signals = backtester.analyst_signals.get(date, {})

                                # Create a DataFrame for the signals
                                signal_data = []

                                # Process signals for each analyst
                                for analyst_name, signals in date_signals.items():
                                    if analyst_name != "risk_management_agent" and isinstance(signals, dict):
                                        # Get the signal for the selected ticker
                                        ticker_signal = signals.get(selected_ticker, {})
                                        if isinstance(ticker_signal, dict):
                                            signal = ticker_signal.get("signal", "N/A")
                                            confidence = ticker_signal.get("confidence", 0)
                                            signal_data.append({
                                                "Analyst": analyst_name.replace("_agent", "").replace("_", " ").title(),
                                                "Signal": signal.title() if signal else "N/A",
                                                "Confidence": confidence if confidence else 0,
                                                "Color": theme_colors['success'] if signal == "bullish" else (theme_colors['error'] if signal == "bearish" else theme_colors['neutral'])
                                            })

                                if signal_data:
                                    signal_df = pd.DataFrame(signal_data)

                                    # Create a horizontal bar chart
                                    fig, ax = plt.subplots(figsize=(6, len(signal_data) * 0.5 + 2))
                                    bars = ax.barh(signal_df["Analyst"], signal_df["Confidence"], color=signal_df["Color"])
                                    ax.set_xlabel("Confidence (%)")
                                    ax.set_xlim(0, 100)

                                    # Add the signal labels to the bars
                                    for i, bar in enumerate(bars):
                                        ax.text(
                                            bar.get_width() + 2,
                                            bar.get_y() + bar.get_height()/2,
                                            signal_df["Signal"].iloc[i],
                                            va='center'
                                        )

                                    st.pyplot(fig)

                                    # Display the signal data in a table
                                    st.dataframe(signal_df[["Analyst", "Signal", "Confidence"]])
                                else:
                                    st.info(f"No analyst signals available for {selected_ticker} on {date}")

                        # Create visualizations for both dates
                        create_signal_viz(selected_date, viz_col1)
                        create_signal_viz(comparison_date, viz_col2)

                        # Add a section to show changes between dates
                        st.subheader("Signal Changes Analysis")

                        # Get signals for both dates
                        date1_signals = backtester.analyst_signals.get(selected_date, {})
                        date2_signals = backtester.analyst_signals.get(comparison_date, {})

                        # Find all analysts that appear in either date
                        all_analysts = set()
                        for signals in [date1_signals, date2_signals]:
                            for analyst_name in signals.keys():
                                if analyst_name != "risk_management_agent":
                                    all_analysts.add(analyst_name)

                        # Create a DataFrame to track changes
                        changes_data = []

                        for analyst_name in all_analysts:
                            # Get signals for the selected ticker from both dates
                            signal1 = None
                            confidence1 = None
                            if analyst_name in date1_signals and selected_ticker in date1_signals[analyst_name]:
                                ticker_signal = date1_signals[analyst_name].get(selected_ticker, {})
                                if isinstance(ticker_signal, dict):
                                    signal1 = ticker_signal.get("signal", "N/A")
                                    confidence1 = ticker_signal.get("confidence", 0)

                            signal2 = None
                            confidence2 = None
                            if analyst_name in date2_signals and selected_ticker in date2_signals[analyst_name]:
                                ticker_signal = date2_signals[analyst_name].get(selected_ticker, {})
                                if isinstance(ticker_signal, dict):
                                    signal2 = ticker_signal.get("signal", "N/A")
                                    confidence2 = ticker_signal.get("confidence", 0)

                            # Only add to changes if we have data for both dates
                            if signal1 and signal2:
                                signal_changed = signal1 != signal2
                                confidence_change = (confidence2 - confidence1) if confidence1 is not None and confidence2 is not None else None

                                changes_data.append({
                                    "Analyst": analyst_name.replace("_agent", "").replace("_", " ").title(),
                                    "Signal Date 1": signal1.title() if signal1 else "N/A",
                                    "Confidence Date 1": confidence1 if confidence1 is not None else 0,
                                    "Signal Date 2": signal2.title() if signal2 else "N/A",
                                    "Confidence Date 2": confidence2 if confidence2 is not None else 0,
                                    "Signal Changed": signal_changed,
                                    "Confidence Change": confidence_change if confidence_change is not None else 0
                                })

                        if changes_data:
                            changes_df = pd.DataFrame(changes_data)

                            # Style the DataFrame to highlight changes
                            def highlight_changes(val):
                                if isinstance(val, bool) and val:
                                    return 'background-color: yellow'
                                elif isinstance(val, (int, float)) and val != 0:
                                    return 'color: green' if val > 0 else 'color: red'
                                return ''

                            styled_changes = changes_df.style.map(highlight_changes, subset=['Signal Changed', 'Confidence Change'])
                            st.dataframe(styled_changes)
                        else:
                            st.info("No comparable signals available for both dates.")

                    # Signal Trend Tab
                    with viz_tabs[2]:
                        # Create a ticker selector for trend analysis
                        trend_ticker_selector = st.selectbox(
                            "Select Ticker",
                            tickers,
                            index=tickers.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in tickers else 0,
                            key="trend_ticker_selector",
                            on_change=update_selected_ticker
                        )

                        # Get all analysts from the signals
                        all_analysts = set()
                        for date, date_signals in backtester.analyst_signals.items():
                            for analyst_name in date_signals.keys():
                                if analyst_name != "risk_management_agent":
                                    all_analysts.add(analyst_name.replace("_agent", "").replace("_", " ").title())

                        # Create a list of analysts with "All Analysts" as the first option
                        analyst_options = ["All Analysts"] + sorted(list(all_analysts))

                        # Create an analyst selector
                        analyst_selector = st.selectbox(
                            "Select Analyst",
                            analyst_options,
                            index=analyst_options.index(st.session_state.selected_analyst) if st.session_state.selected_analyst in analyst_options else 0,
                            key="analyst_selector",
                            on_change=update_selected_analyst
                        )

                        # Use the values from session state for visualization
                        selected_ticker = st.session_state.selected_ticker
                        selected_analyst = st.session_state.selected_analyst

                        # Create a DataFrame to track signals over time
                        trend_data = []

                        for date in all_dates:
                            date_signals = backtester.analyst_signals.get(date, {})

                            if selected_analyst == "All Analysts":
                                # Aggregate signals from all analysts
                                bullish_count = 0
                                bearish_count = 0
                                neutral_count = 0
                                total_confidence = 0
                                analyst_count = 0

                                for analyst_name, signals in date_signals.items():
                                    if analyst_name != "risk_management_agent" and isinstance(signals, dict):
                                        ticker_signal = signals.get(selected_ticker, {})
                                        if isinstance(ticker_signal, dict):
                                            signal = ticker_signal.get("signal", "")
                                            confidence = ticker_signal.get("confidence", 0)

                                            if signal == "bullish":
                                                bullish_count += 1
                                            elif signal == "bearish":
                                                bearish_count += 1
                                            elif signal == "neutral":
                                                neutral_count += 1

                                            total_confidence += confidence
                                            analyst_count += 1

                                if analyst_count > 0:
                                    # Calculate consensus signal
                                    if bullish_count > bearish_count and bullish_count > neutral_count:
                                        consensus_signal = "Bullish"
                                    elif bearish_count > bullish_count and bearish_count > neutral_count:
                                        consensus_signal = "Bearish"
                                    else:
                                        consensus_signal = "Neutral"

                                    # Calculate average confidence
                                    avg_confidence = total_confidence / analyst_count

                                    trend_data.append({
                                        "Date": date,
                                        "Signal": consensus_signal,
                                        "Confidence": avg_confidence,
                                        "Bullish Count": bullish_count,
                                        "Bearish Count": bearish_count,
                                        "Neutral Count": neutral_count,
                                        "Analyst Count": analyst_count
                                    })
                            else:
                                # Get signals for the selected analyst
                                for analyst_name, signals in date_signals.items():
                                    analyst_display = analyst_name.replace("_agent", "").replace("_", " ").title()

                                    if analyst_display == selected_analyst and isinstance(signals, dict):
                                        ticker_signal = signals.get(selected_ticker, {})
                                        if isinstance(ticker_signal, dict):
                                            signal = ticker_signal.get("signal", "")
                                            confidence = ticker_signal.get("confidence", 0)

                                            if signal:
                                                trend_data.append({
                                                    "Date": date,
                                                    "Signal": signal.title(),
                                                    "Confidence": confidence
                                                })

                        if trend_data:
                            trend_df = pd.DataFrame(trend_data)

                            # Create a figure with two subplots
                            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2, 1]})

                            # Convert signals to numeric values for plotting
                            signal_values = {"Bullish": 1, "Neutral": 0, "Bearish": -1}
                            trend_df["Signal Value"] = trend_df["Signal"].map(signal_values)

                            # Plot signal trend
                            ax1.plot(trend_df["Date"], trend_df["Signal Value"], marker='o', linestyle='-', color=theme_colors['primary'])
                            ax1.set_ylabel("Signal")
                            ax1.set_title(f"Signal Trend for {selected_ticker}" + (f" - {selected_analyst}" if selected_analyst != "All Analysts" else " - Consensus"))
                            ax1.set_ylim([-1.5, 1.5])
                            ax1.set_yticks([-1, 0, 1])
                            ax1.set_yticklabels(["Bearish", "Neutral", "Bullish"])
                            ax1.grid(True)

                            # Plot confidence trend
                            ax2.bar(trend_df["Date"], trend_df["Confidence"], color=trend_df["Signal"].map({
                                "Bullish": theme_colors['success'],
                                "Neutral": theme_colors['neutral'],
                                "Bearish": theme_colors['error']
                            }))
                            ax2.set_ylabel("Confidence (%)")
                            ax2.set_xlabel("Date")
                            ax2.set_ylim([0, 100])
                            ax2.grid(True)

                            plt.tight_layout()
                            st.pyplot(fig)

                            # Display additional information for "All Analysts"
                            if selected_analyst == "All Analysts" and "Bullish Count" in trend_df.columns:
                                # Create a stacked bar chart of analyst counts
                                fig, ax = plt.subplots(figsize=(12, 6))

                                # Create the stacked bars
                                ax.bar(trend_df["Date"], trend_df["Bullish Count"], label="Bullish", color=theme_colors['success'])
                                ax.bar(trend_df["Date"], trend_df["Neutral Count"], bottom=trend_df["Bullish Count"], label="Neutral", color=theme_colors['neutral'])
                                ax.bar(trend_df["Date"], trend_df["Bearish Count"], bottom=trend_df["Bullish Count"] + trend_df["Neutral Count"], label="Bearish", color=theme_colors['error'])

                                ax.set_ylabel("Analyst Count")
                                ax.set_xlabel("Date")
                                ax.set_title(f"Analyst Signal Distribution for {selected_ticker}")
                                ax.legend()
                                ax.grid(True)

                                st.pyplot(fig)

                            # Display the trend data in a table
                            st.dataframe(trend_df)
                        else:
                            st.info(f"No trend data available for {selected_ticker}" + (f" with analyst {selected_analyst}" if selected_analyst != "All Analysts" else ""))
            else:
                st.info("No analyst signals data available for visualization.")
        else:
            st.warning("No performance data available. The backtest may not have completed successfully.")
else:
    # Display instructions when not running
    st.info("""
    ### How to use this backtester:

    1. Enter stock tickers separated by commas in the sidebar
    2. Select the date range for your backtest
    3. Set your initial capital amount
    4. Choose a margin requirement percentage (for short selling)
    5. Select the LLM model to use for trading decisions
    6. Choose which analysts to include in your strategy
    7. Click "Run Backtest" to start the simulation

    The backtest will simulate trading based on the AI analysts' recommendations and display performance metrics when complete.
    """)

    # Display sample visualization
    st.markdown("### Sample Portfolio Performance")

    # Generate sample data
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    sample_data = pd.DataFrame({
        'Date': dates,
        'Portfolio Value': initial_capital * (1 + np.cumsum(np.random.normal(0.001, 0.02, size=len(dates))))
    }).set_index('Date')

    # Plot sample data
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(sample_data.index, sample_data["Portfolio Value"], color=theme_colors['primary'], alpha=0.7)
    ax.set_title("Sample Portfolio Performance (Simulated Data)")
    ax.set_ylabel("Portfolio Value ($)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
