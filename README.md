# AI Hedge Fund Plus

 <a href="https://buy.stripe.com/5kA3dy2xF5370YE145" target="_blank">
            <svg width="150" height="40" viewBox="0 0 150 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="150" height="40" rx="8" fill="#635BFF"/>
                <text x="75" y="24" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="white" text-anchor="middle">Support This Project</text>
            </svg>
        </a>

This is an enhanced version of the AI-powered hedge fund proof of concept. The goal of this project is to explore the use of AI to make trading decisions with an interactive web interface. This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
2. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
3. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
4. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
5. Stanley Druckenmiller Agent - Macro trading legend who hunts for asymmetric opportunities with explosive growth potential
6. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
7. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
8. Sentiment Agent - Analyzes market sentiment and generates trading signals
9. Fundamentals Agent - Analyzes fundamental data and generates trading signals
10. Technicals Agent - Analyzes technical indicators and generates trading signals
11. Risk Manager - Calculates risk metrics and sets position limits
12. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1020" alt="Screenshot 2025-03-08 at 4 45 22 PM" src="https://github.com/user-attachments/assets/d8ab891e-a083-4fed-b514-ccc9322a3e57" />

**Note**: the system simulates trading decisions, it does not actually trade.

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Past performance does not indicate future results
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [Setup](#setup)
- [Usage](#usage)
  - [Running the Web App](#running-the-web-app)
  - [Running the Hedge Fund CLI](#running-the-hedge-fund-cli)
  - [Running the Backtester CLI](#running-the-backtester-cli)
- [Payment Integration](#payment-integration)
  - [Stripe Setup](#stripe-setup)
  - [Paddle Setup](#paddle-setup)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## Setup

Clone the repository:
```bash
git clone https://github.com/virattt/ai-hedge-fund-plus.git
cd ai-hedge-fund-plus
```

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

3. Set up your environment variables:
```bash
# Create .env file for your API keys
cp .env.example .env
```

4. Set your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
# Get your OpenAI API key from https://platform.openai.com/
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
# Get your Groq API key from https://groq.com/
GROQ_API_KEY=your-groq-api-key

# For running LLMs hosted by Anthropic (claude-3-opus, etc.)
# Get your Anthropic API key from https://anthropic.com/
ANTHROPIC_API_KEY=your-anthropic-api-key

# For running LLMs hosted by DeepSeek
# Get your DeepSeek API key from https://deepseek.com/
DEEPSEEK_API_KEY=your-deepseek-api-key

# For getting financial data to power the hedge fund
# Get your Financial Datasets API key from https://financialdatasets.ai/
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important**: You must set at least one of `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY` for the hedge fund to work. If you want to use LLMs from all providers, you will need to set all API keys.

Financial data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key.

For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## Usage

### Running the Web App

The AI Hedge Fund Plus comes with an interactive Streamlit web interface that allows you to:
- Configure and run backtests with different parameters
- Visualize portfolio performance
- Analyze trading decisions and signals
- Compare different analysts' perspectives

To run the web app:

```bash
# Using the provided script
./run_app.sh

# Or directly with Poetry
poetry run streamlit run app.py
```

The web app will be available at http://localhost:8501 in your browser.

### Running the Hedge Fund CLI

For command-line usage:

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

You can also specify a `--show-reasoning` flag to print the reasoning of each agent to the console.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --show-reasoning
```
You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 
```

### Running the Backtester CLI

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

You can optionally specify the start and end dates to backtest over a specific time period.

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

## Payment Integration

You can monetize the AI Hedge Fund Plus application by integrating a payment system. This section provides instructions for setting up either Stripe or Paddle as your payment processor.

### Stripe Setup

1. **Create a Stripe Account**:
   - Sign up at [stripe.com](https://stripe.com)
   - Complete the verification process
   - Set up your business details

2. **Install Stripe Dependencies**:
   ```bash
   poetry add stripe streamlit-stripe
   ```

3. **Configure Stripe Keys**:
   Add these to your `.env` file:
   ```
   STRIPE_PUBLISHABLE_KEY=your_publishable_key
   STRIPE_SECRET_KEY=your_secret_key
   STRIPE_PRICE_ID=your_price_id
   ```

4. **Create Products and Pricing**:
   - Log into your Stripe Dashboard
   - Go to Products > Create Product
   - Set up subscription tiers (e.g., Basic, Pro, Enterprise)
   - Note the Price IDs for each tier

5. **Implement Stripe in Your App**:
   Create a new file `src/payment/stripe_integration.py`:
   ```python
   import os
   import stripe
   import streamlit as st
   from dotenv import load_dotenv

   load_dotenv()

   stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

   def create_checkout_session(price_id, success_url, cancel_url):
       try:
           checkout_session = stripe.checkout.Session.create(
               payment_method_types=["card"],
               line_items=[{"price": price_id, "quantity": 1}],
               mode="subscription",
               success_url=success_url,
               cancel_url=cancel_url,
           )
           return checkout_session
       except Exception as e:
           return str(e)

   def display_payment_options():
       st.header("Choose Your Subscription Plan")
       
       col1, col2, col3 = st.columns(3)
       
       with col1:
           st.subheader("Basic")
           st.write("$9.99/month")
           st.write("- Access to basic features")
           st.write("- Limited number of stocks")
           if st.button("Subscribe to Basic"):
               session = create_checkout_session(
                   os.getenv("STRIPE_BASIC_PRICE_ID"),
                   "http://localhost:8501/success",
                   "http://localhost:8501/cancel"
               )
               st.markdown(f"[Proceed to Payment]({{session.url}})")
       
       with col2:
           st.subheader("Pro")
           st.write("$19.99/month")
           st.write("- All basic features")
           st.write("- Unlimited stocks")
           st.write("- Advanced analytics")
           if st.button("Subscribe to Pro"):
               session = create_checkout_session(
                   os.getenv("STRIPE_PRO_PRICE_ID"),
                   "http://localhost:8501/success",
                   "http://localhost:8501/cancel"
               )
               st.markdown(f"[Proceed to Payment]({{session.url}})")
       
       with col3:
           st.subheader("Enterprise")
           st.write("$49.99/month")
           st.write("- All pro features")
           st.write("- Priority support")
           st.write("- Custom analytics")
           if st.button("Subscribe to Enterprise"):
               session = create_checkout_session(
                   os.getenv("STRIPE_ENTERPRISE_PRICE_ID"),
                   "http://localhost:8501/success",
                   "http://localhost:8501/cancel"
               )
               st.markdown(f"[Proceed to Payment]({{session.url}})")
   ```

6. **Integrate with Your Streamlit App**:
   Update `app.py` to include the payment page:
   ```python
   # Add this import at the top
   from src.payment.stripe_integration import display_payment_options
   
   # Add this to your sidebar or as a separate page
   if st.sidebar.button("Subscription Plans"):
       display_payment_options()
   ```

7. **Set Up Webhook for Subscription Management**:
   - Create a webhook endpoint in your application
   - Configure the webhook in your Stripe Dashboard
   - Handle events like `customer.subscription.created`, `customer.subscription.updated`, etc.

## Project Structure 
```
ai-hedge-fund-plus/
├── app.py                      # Streamlit web application
├── run_app.sh                  # Script to run the web app
├── src/
│   ├── agents/                 # Agent definitions and workflow
│   │   ├── bill_ackman.py      # Bill Ackman agent
│   │   ├── fundamentals.py     # Fundamental analysis agent
│   │   ├── portfolio_manager.py # Portfolio management agent
│   │   ├── risk_manager.py     # Risk management agent
│   │   ├── sentiment.py        # Sentiment analysis agent
│   │   ├── technicals.py       # Technical analysis agent
│   │   ├── valuation.py        # Valuation analysis agent
│   │   ├── warren_buffett.py   # Warren Buffett agent
│   │   ├── ben_graham.py        # Ben Graham agent
│   │   ├── cathie_wood.py       # Cathie Wood agent
│   │   ├── charlie_munger.py    # Charlie Munger agent
│   │   ├── stanley_druckenmiller.py # Stanley Druckenmiller agent
│   │   ├── warren_buffett.py    # Warren Buffett agent
│   │   ├── valuation.py         # Valuation analysis agent
│   │   ├── sentiment.py         # Sentiment analysis agent
│   │   ├── fundamentals.py      # Fundamental analysis agent
│   │   ├── technicals.py        # Technical analysis agent
│   │   ├── risk_manager.py      # Risk management agent
│   │   ├── portfolio_manager.py  # Portfolio management agent
│   │   ├── ben_graham.py         # Ben Graham agent
│   │   ├── cathie_wood.py         # Cathie Wood agent
│   │   ├── charlie_munger.py      # Charlie Munger agent
│   │   ├── stanley_druckenmiller.py # Stanley Druckenmiller agent
│   │   ├── warren_buffett.py      # Warren Buffett agent
│   │   └── valuation.py           # Valuation analysis agent
│   ├── data/                   # Data handling and processing
│   ├── graph/                  # Visualization components
│   ├── llm/                    # LLM integration and models
│   ├── tools/                  # Agent tools
│   │   ├── api.py              # API tools
│   ├── utils/                  # Utility functions
│   ├── backtester.py           # Backtesting engine
│   ├── main.py                 # Main CLI entry point
├── backtester.py               # CLI backtester entry point
├── pyproject.toml              # Poetry configuration
├── .env.example                # Example environment variables
├── LICENSE                     # MIT License
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused. This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund-plus/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
