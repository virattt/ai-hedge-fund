> **Disclaimer**: This repository is for educational and research purposes only; it provides no investment advice or guarantees.
# Polygon.io Integration Specification

## Background
The current code fetches market prices, fundamentals, insider trades, and news from the Financial Datasets API. Users may prefer to source this information from Polygon.io instead. Polygon offers extensive price data and fundamental statements but lacks certain datasets available from financialdatasets.ai.

## Goal
Enable the project to retrieve data from Polygon.io rather than financialdatasets.ai. Maintain existing functionality where possible and document any missing capabilities.

## Data Coverage Differences
- **Available from Polygon**
  - Historical OHLC prices and volumes.
  - Company news articles.
  - Standardized financial statements (income statement, balance sheet, cash flow).
- **Not Provided by Polygon**
  - Insider trading transactions used by `get_insider_trades`.
  - The line‑item search endpoint used by `search_line_items` (Polygon only exposes full statements).
  - Some aggregated metrics (PEG ratio, free cash flow yield, etc.) may need to be calculated locally from fundamentals.

## Implementation Overview
1. **Environment Variables**
   - Add `POLYGON_API_KEY` in `.env.example` and remove `FINANCIAL_DATASETS_API_KEY` references.
   - Update `README.md` instructions accordingly.

2. **API Wrapper (`src/tools/api.py`)**
   - Replace URL construction to call Polygon endpoints.
     - Prices: `https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}?apiKey=...`
     - Financial statements: `https://api.polygon.io/vX/reference/financials?ticker={ticker}&timeframe=annual` (adapt parameters as needed).
     - Company news: `https://api.polygon.io/v2/reference/news?ticker={ticker}&published_utc.gte={start}`.
   - Compute derived metrics (e.g., ratios) from the financial statement data.
   - For `search_line_items`, fetch the entire statement from Polygon and filter for the requested fields.
   - Remove or replace `get_insider_trades` since Polygon does not supply this information.
   - Update `get_market_cap` to use Polygon’s ticker details or calculate `shares_outstanding * latest_price` if a direct field is unavailable.

3. **Data Models (`src/data/models.py`)**
   - Adjust Pydantic models if Polygon’s response fields differ.
   - Add helper functions for transforming Polygon responses into the existing structures.

4. **Caching Layer (`src/data/cache.py`)**
   - No major changes; cached data should store the transformed Polygon responses.

5. **Agents and Other Modules**
   - Review code that relies on insider trades or specific metrics. If Polygon lacks those fields, consider alternative data sources or omit those features.
   - Ensure all calls to the old API wrapper still succeed with the new Polygon implementation.

6. **Testing**
   - Run the existing unit tests and the full workflow to verify data is fetched correctly from Polygon.
   - Validate that price DataFrames and fundamental metrics load as expected.

## File Changes Summary
- `.env.example` – add `POLYGON_API_KEY` and remove `FINANCIAL_DATASETS_API_KEY`.
- `README.md` – update setup instructions for Polygon.
- `src/tools/api.py` – rewrite API calls for Polygon and drop unsupported endpoints.
- `src/data/models.py` – tweak models if necessary for Polygon’s response format.
- `docs/specs/*` – this document.

