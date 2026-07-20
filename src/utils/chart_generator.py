import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import os

class PerformanceChartGenerator:
    """Generate performance charts for backtesting results."""
    
    def __init__(self, output_dir: str = "charts"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Set matplotlib style for better looking charts
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        
    def generate_portfolio_performance_chart(
        self, 
        portfolio_values: List[Dict], 
        filename: Optional[str] = None,
        show_drawdown: bool = True
    ) -> str:
        """
        Generate a comprehensive portfolio performance chart.
        
        Args:
            portfolio_values: List of portfolio value points from backtesting
            filename: Custom filename for the chart (optional)
            show_drawdown: Whether to include drawdown subplot
            
        Returns:
            Path to the saved chart file
        """
        if not portfolio_values:
            raise ValueError("No portfolio values provided")
            
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(portfolio_values)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        
        # Calculate additional metrics
        df['Daily_Return'] = df['Portfolio Value'].pct_change()
        df['Cumulative_Return'] = (df['Portfolio Value'] / df['Portfolio Value'].iloc[0] - 1) * 100
        
        # Calculate drawdown
        running_max = df['Portfolio Value'].cummax()
        df['Drawdown'] = (df['Portfolio Value'] - running_max) / running_max * 100
        
        # Create the chart
        fig, axes = plt.subplots(2 if show_drawdown else 1, 1, figsize=(12, 8 if show_drawdown else 6))
        if not show_drawdown:
            axes = [axes]
            
        # Portfolio value over time
        axes[0].plot(df.index, df['Portfolio Value'], linewidth=2, color='#2E7D32', label='Portfolio Value')
        axes[0].set_title('Portfolio Performance Over Time', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Portfolio Value ($)', fontsize=12)
        axes[0].grid(True, alpha=0.3)
        axes[0].legend()
        
        # Format y-axis to show currency
        axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Add performance statistics as text box
        total_return = df['Cumulative_Return'].iloc[-1]
        max_drawdown = df['Drawdown'].min()
        volatility = df['Daily_Return'].std() * np.sqrt(252) * 100  # Annualized volatility
        
        stats_text = f'Total Return: {total_return:.1f}%\nMax Drawdown: {max_drawdown:.1f}%\nAnnual Volatility: {volatility:.1f}%'
        axes[0].text(0.02, 0.98, stats_text, transform=axes[0].transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.8),
                    verticalalignment='top', fontsize=10)
        
        if show_drawdown:
            # Drawdown chart
            axes[1].fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.6, label='Drawdown')
            axes[1].set_title('Portfolio Drawdown', fontsize=14, fontweight='bold')
            axes[1].set_ylabel('Drawdown (%)', fontsize=12)
            axes[1].set_xlabel('Date', fontsize=12)
            axes[1].grid(True, alpha=0.3)
            axes[1].legend()
            
            # Highlight max drawdown point
            max_dd_date = df['Drawdown'].idxmin()
            axes[1].scatter(max_dd_date, max_drawdown, color='darkred', s=50, zorder=5)
            axes[1].annotate(f'Max DD: {max_drawdown:.1f}%', 
                           xy=(max_dd_date, max_drawdown), 
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8),
                           fontsize=9)
        
        plt.tight_layout()
        
        # Save the chart
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portfolio_performance_{timestamp}.png"
            
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def generate_agent_signals_chart(
        self, 
        backtest_results: List[Dict], 
        filename: Optional[str] = None
    ) -> str:
        """
        Generate a chart showing agent signal distribution over time.
        
        Args:
            backtest_results: List of daily backtest results
            filename: Custom filename for the chart (optional)
            
        Returns:
            Path to the saved chart file
        """
        if not backtest_results:
            raise ValueError("No backtest results provided")
            
        # Extract signal data
        dates = []
        bullish_counts = []
        bearish_counts = []
        neutral_counts = []
        
        for result in backtest_results:
            dates.append(pd.to_datetime(result['date']))
            
            total_bullish = 0
            total_bearish = 0
            total_neutral = 0
            
            for ticker_detail in result.get('ticker_details', []):
                total_bullish += ticker_detail.get('bullish_count', 0)
                total_bearish += ticker_detail.get('bearish_count', 0)
                total_neutral += ticker_detail.get('neutral_count', 0)
                
            bullish_counts.append(total_bullish)
            bearish_counts.append(total_bearish)
            neutral_counts.append(total_neutral)
        
        # Create the chart
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Stacked area chart
        ax.stackplot(dates, bullish_counts, bearish_counts, neutral_counts,
                    labels=['Bullish Signals', 'Bearish Signals', 'Neutral Signals'],
                    colors=['#4CAF50', '#F44336', '#FF9800'],
                    alpha=0.8)
        
        ax.set_title('Agent Signal Distribution Over Time', fontsize=14, fontweight='bold')
        ax.set_ylabel('Signal Count', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save the chart
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"agent_signals_{timestamp}.png"
            
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def generate_combined_dashboard(
        self, 
        portfolio_values: List[Dict], 
        backtest_results: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        Generate a comprehensive dashboard with multiple charts.
        
        Args:
            portfolio_values: List of portfolio value points
            backtest_results: List of daily backtest results
            filename: Custom filename for the dashboard (optional)
            
        Returns:
            Path to the saved dashboard file
        """
        if not portfolio_values:
            raise ValueError("Portfolio values are required")
            
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
        
        # Convert portfolio data
        df = pd.DataFrame(portfolio_values)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df['Cumulative_Return'] = (df['Portfolio Value'] / df['Portfolio Value'].iloc[0] - 1) * 100
        running_max = df['Portfolio Value'].cummax()
        df['Drawdown'] = (df['Portfolio Value'] - running_max) / running_max * 100
        
        # 1. Portfolio Value
        ax1.plot(df.index, df['Portfolio Value'], linewidth=2, color='#2E7D32')
        ax1.set_title('Portfolio Value', fontweight='bold')
        ax1.set_ylabel('Value ($)')
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        ax1.grid(True, alpha=0.3)
        
        # 2. Cumulative Returns
        ax2.plot(df.index, df['Cumulative_Return'], linewidth=2, color='#1976D2')
        ax2.set_title('Cumulative Returns', fontweight='bold')
        ax2.set_ylabel('Return (%)')
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2.grid(True, alpha=0.3)
        
        # 3. Drawdown
        ax3.fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.6)
        ax3.set_title('Drawdown', fontweight='bold')
        ax3.set_ylabel('Drawdown (%)')
        ax3.grid(True, alpha=0.3)
        
        # 4. Exposure over time (if available)
        if 'Gross Exposure' in df.columns:
            ax4.plot(df.index, df['Gross Exposure'], label='Gross', linewidth=2, color='purple')
            ax4.plot(df.index, df['Net Exposure'], label='Net', linewidth=2, color='orange')
            ax4.set_title('Portfolio Exposure', fontweight='bold')
            ax4.set_ylabel('Exposure')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'Exposure data\nnot available', ha='center', va='center',
                    transform=ax4.transAxes, fontsize=12)
            ax4.set_title('Portfolio Exposure', fontweight='bold')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save the dashboard
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portfolio_dashboard_{timestamp}.png"
            
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath