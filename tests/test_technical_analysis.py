import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

# Add src directory to Python path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root_dir, 'src'))

from tools import (
    calculate_macd,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_obv,
    prices_to_df
)

def load_sample_data():
    """Load sample price data."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    sample_file = os.path.join(data_dir, 'sample_prices.csv')

    # Generate sample data if it doesn't exist
    if not os.path.exists(sample_file):
        print("Generating sample data...")
        from tests.data.generate_sample_data import generate_sample_data
        generate_sample_data(sample_file)

    df = pd.read_csv(sample_file)
    return prices_to_df(df.to_dict('records'))

def test_technical_indicators():
    """Test and visualize technical indicators."""
    print("Loading sample data...")
    df = load_sample_data()

    # Calculate indicators
    print("\nCalculating technical indicators...")
    macd_line, signal_line = calculate_macd(df)
    rsi = calculate_rsi(df)
    upper_band, lower_band = calculate_bollinger_bands(df)
    obv = calculate_obv(df)

    # Create visualization
    plt.style.use('default')  # Use default style instead of seaborn
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # Plot MACD
    ax1.plot(macd_line, label='MACD Line')
    ax1.plot(signal_line, label='Signal Line')
    ax1.set_title('MACD')
    ax1.legend()

    # Plot RSI
    ax2.plot(rsi)
    ax2.axhline(y=70, color='r', linestyle='--')
    ax2.axhline(y=30, color='g', linestyle='--')
    ax2.set_title('RSI')

    # Plot Bollinger Bands
    ax3.plot(df['close'], label='Close Price')
    ax3.plot(upper_band, label='Upper Band')
    ax3.plot(lower_band, label='Lower Band')
    ax3.set_title('Bollinger Bands')
    ax3.legend()

    # Plot OBV
    ax4.plot(obv)
    ax4.set_title('On-Balance Volume')

    plt.tight_layout()
    plt.savefig('tests/data/technical_analysis.png')
    print("\nTechnical analysis visualization saved to tests/data/technical_analysis.png")

    # Print summary statistics
    print("\nSummary Statistics:")
    print(f"MACD Range: {macd_line.min():.2f} to {macd_line.max():.2f}")
    print(f"RSI Range: {rsi.min():.2f} to {rsi.max():.2f}")
    print(f"Bollinger Band Width: {(upper_band - lower_band).mean():.2f}")
    print(f"OBV Final Value: {obv.iloc[-1]:,.0f}")

if __name__ == "__main__":
    # Create tests directory if it doesn't exist
    os.makedirs('tests', exist_ok=True)
    os.makedirs('tests/data', exist_ok=True)

    test_technical_indicators()
