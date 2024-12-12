import pandas as pd
import numpy as np
import os

def generate_sample_data(output_path):
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Generate sample price data
    dates = pd.date_range(start='2024-01-01', end='2024-03-01')
    np.random.seed(42)
    prices = np.random.normal(loc=100, scale=2, size=len(dates)).cumsum()
    volume = np.random.randint(1000000, 5000000, size=len(dates))

    # Create DataFrame
    df = pd.DataFrame({
        'time': dates,
        'open': prices + np.random.normal(0, 0.5, len(dates)),
        'close': prices + np.random.normal(0, 0.5, len(dates)),
        'high': prices + 1 + np.random.normal(0, 0.2, len(dates)),
        'low': prices - 1 + np.random.normal(0, 0.2, len(dates)),
        'volume': volume
    })

    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f'Created sample price data in {output_path}')

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'sample_prices.csv')
    generate_sample_data(output_path)
