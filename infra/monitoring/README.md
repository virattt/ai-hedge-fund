# Market Monitoring Azure Function

This Function App polls the Financial Datasets API every five minutes during U.S. equity market hours (9:30am–4:00pm ET). It
evaluates simple price/volume heuristics for the configured watchlist and enqueues downstream analysis jobs only when fresh
signals are detected. Cooldown metadata is stored in Cosmos DB so that identical alerts are not produced repeatedly.

## Project Layout

```
infra/monitoring/
├── .funcignore
├── host.json
├── local.settings.json.sample        # Copy to local.settings.json for local development
├── market_monitor/
│   ├── __init__.py                   # Timer trigger implementation
│   └── function.json                 # Cron schedule (every 5 minutes)
└── requirements.txt
```

The Function imports the existing `src.tools.api.get_prices` helper so that the same Financial Datasets client is reused in the
serverless workload.

## Environment Variables

Set the following application settings (locally in `local.settings.json` or in the Function App configuration):

| Name | Required | Description |
| ---- | -------- | ----------- |
| `AzureWebJobsStorage` | ✅ | General-purpose storage account used by Azure Functions host. The queue connection string falls back to this value if a dedicated one is not provided. |
| `FUNCTIONS_WORKER_RUNTIME` | ✅ | Must be set to `python` when running locally or on Azure. |
| `FINANCIAL_DATASETS_API_KEY` | ✅ (for non-free tickers) | API key forwarded to `src/tools/api.py` when fetching price data. |
| `MARKET_MONITOR_WATCHLIST` | ➖ | Comma-separated tickers to inspect (defaults to `AAPL,MSFT,NVDA`). |
| `MARKET_MONITOR_PERCENT_CHANGE_THRESHOLD` | ➖ | Minimum intraday percentage change (e.g. `0.02` for 2%) required to trigger a signal. |
| `MARKET_MONITOR_VOLUME_SPIKE_MULTIPLIER` | ➖ | Multiplier applied to the trailing average volume when flagging unusual activity (default `1.5`). |
| `MARKET_MONITOR_VOLUME_LOOKBACK` | ➖ | Number of prior sessions used for the average volume baseline (default `10`). |
| `MARKET_MONITOR_ANALYSIS_WINDOW_MINUTES` | ➖ | Width of the window sent to the queue worker for deeper analysis (default `120`). |
| `MARKET_MONITOR_COOLDOWN_SECONDS` | ➖ | Minimum time between alerts for the same ticker (default `1800`, i.e. 30 minutes). |
| `MARKET_MONITOR_LOOKBACK_DAYS` | ➖ | Amount of history retrieved per execution to compute the heuristics (default `30`). |
| `MARKET_MONITOR_QUEUE_CONNECTION_STRING` | ✅ | Connection string for the storage account hosting the downstream queue (falls back to `AzureWebJobsStorage`). |
| `MARKET_MONITOR_QUEUE_NAME` | ✅ | Target queue name consumed by `queue_worker.py`. |
| `COSMOS_ENDPOINT` | ✅ | Cosmos DB account endpoint (e.g. `https://<account>.documents.azure.com:443/`). |
| `COSMOS_KEY` | ✅ | Primary or secondary key for the Cosmos DB account. |
| `COSMOS_DATABASE` | ✅ | Database used to persist ticker cooldown metadata. |
| `COSMOS_CONTAINER` | ✅ | Container (partitioned by `/ticker`) storing the last-trigger timestamps. |

> **Holiday Handling**: The timer trigger executes on every weekday regardless of market holidays. If holiday awareness is
> required, add logic to reference an exchange calendar or pause the Function App via schedules.

## Queue Payload Contract

Messages pushed to the storage queue follow this schema:

```json
{
  "tickers": ["AAPL"],
  "analysis_window": {
    "start": "2024-01-02T14:30:00+00:00",
    "end": "2024-01-02T16:30:00+00:00"
  },
  "correlation_hints": {
    "related_watchlist": ["MSFT", "NVDA"],
    "basis": ["price_breakout", "volume_spike"]
  },
  "signals": ["price_breakout", "volume_spike"],
  "market_snapshot": {
    "percent_change": 0.0234,
    "volume_ratio": 1.78,
    "latest_close": 198.34,
    "previous_close": 194.85,
    "latest_volume": 54200123,
    "average_volume": 30451200.0
  },
  "triggered_at": "2024-01-02T16:35:00+00:00"
}
```

`queue_worker.py` can rely on `tickers`, `analysis_window`, and `correlation_hints` to hydrate deeper pipelines. Additional
fields (`signals`, `market_snapshot`, `triggered_at`) provide diagnostic context.

## Local Development

1. Install Azure Functions Core Tools (v4) and the Python dependencies:
   ```bash
   npm i -g azure-functions-core-tools@4 --unsafe-perm true
   cd infra/monitoring
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy the sample settings file and provide the required secrets:
   ```bash
   cp local.settings.json.sample local.settings.json
   ```
3. Start the Functions host (it will automatically respect the 5-minute cron schedule):
   ```bash
   func start
   ```

> For deterministic testing, you can invoke the timer manually: `func start --javascript` isn't necessary—use
> `func start` and press **Ctrl+C** when finished. Alternatively, call the Python entrypoint with
> `func host start --no-build` or trigger the function via `func run market_monitor`.

## Deployment

### Azure Functions Core Tools

1. Create or reuse the required Azure resources:
   - Storage account with the target queue.
   - Cosmos DB account + database + container (`/ticker` partition key).
   - Function App configured for Python 3.11 (Consumption or Premium plan).
2. Publish the Function App:
   ```bash
   cd infra/monitoring
   func azure functionapp publish <FUNCTION_APP_NAME>
   ```
3. Configure application settings (environment variables listed above) either through the Azure Portal, `az functionapp
   config appsettings set`, or infrastructure-as-code. Ensure the queue and Cosmos DB credentials are present before enabling
the Function.

### GitHub Actions

1. Store the secrets in the repository or organization (`AZURE_FUNCTIONAPP_NAME`, `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`, queue and
   Cosmos settings, API keys, etc.).
2. Add a workflow similar to the snippet below:

   ```yaml
   name: Deploy Monitoring Function
   on:
     push:
       branches: [ main ]
       paths:
         - 'infra/monitoring/**'
   jobs:
     build-and-deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         - name: Install dependencies
           run: |
             cd infra/monitoring
             pip install -r requirements.txt
         - name: Azure Functions deploy
           uses: Azure/functions-action@v1
           with:
             app-name: ${{ secrets.AZURE_FUNCTIONAPP_NAME }}
             publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
             package: infra/monitoring
   ```

3. Configure the Function App application settings via the Azure CLI, ARM/Bicep, or the portal as part of the workflow if
desired (e.g. use `azure/appservice-settings@v2`).

With the Function App deployed, the timer trigger will run every five minutes but only dispatch jobs when market hours are open
and new heuristics cross the configured thresholds.
