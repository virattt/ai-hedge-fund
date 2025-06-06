# AI Hedge Fund

An AI-powered hedge fund system that uses multiple analyst agents to make trading decisions.

## Features

- Multiple AI analysts with different investment strategies
- Technical and fundamental analysis
- Risk management and portfolio optimization
- Support for multiple markets:
  - US stocks (via Yahoo Finance)
  - Moscow Exchange (MOEX)
  - SPB Exchange (via Tinkoff Investments)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-hedge-fund.git
cd ai-hedge-fund
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```
OPENAI_API_KEY=your_openai_key
TINKOFF_TOKEN=your_tinkoff_token  # Optional, for SPB Exchange access
```

## Usage

### Basic Usage

Run the hedge fund with default settings:
```bash
python src/main.py --tickers AAPL,MSFT,GOOGL
```

### Russian Market Analysis

To analyze Russian stocks from MOEX and SPB Exchange:

```bash
# Analyze MOEX stocks
python src/main.py --tickers SBER,GAZP,LKOH

# Analyze SPB Exchange stocks (requires Tinkoff token)
python src/main.py --tickers AAPL,MSFT,GOOGL --spb
```

### Example Scripts

Check out example scripts in the `src/examples` directory:

- `analyze_stock.py`: Demonstrates MOEX/SPB stock analysis
```bash
python src/examples/analyze_stock.py
```

## Technical Analysis Features

The system provides comprehensive technical analysis:

- Trend Analysis:
  - Multiple timeframe trends (short, medium, long-term)
  - Moving averages (SMA, EMA)
  - Trend strength indicators

- Momentum Analysis:
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Stochastic Oscillator

- Volatility Analysis:
  - Bollinger Bands
  - Volatility state detection
  - Price channel analysis

## Data Sources

### Moscow Exchange (MOEX)
- Real-time and historical market data
- Security information
- Trading status and statistics
- No authentication required

### SPB Exchange
Currently supports data access through:
- Tinkoff Investments API (requires API token)
- More providers coming soon (Finam, Interactive Brokers)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This software is for educational and research purposes only. Do not use it for actual trading without understanding the risks involved. The authors and contributors are not responsible for any financial losses incurred using this software.
