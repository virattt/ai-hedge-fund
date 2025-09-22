# Azure Cosmos DB bootstrap

The application expects a Cosmos DB account that exposes a single database and
three containers. Configuration is supplied through the following environment
variables (see `src/config.py`):

- `COSMOS_ENDPOINT`
- `COSMOS_KEY`
- `COSMOS_DATABASE`
- `COSMOS_PORTFOLIOS_CONTAINER`
- `COSMOS_ANALYST_SIGNALS_CONTAINER`
- `COSMOS_DECISIONS_CONTAINER`

All containers should use a `/partition_key` partition path so the repositories
can efficiently separate user and strategy specific documents. Portfolios are
treated as the source of truth for subsequent runs, while analyst signals and
decisions are stored per execution for downstream analytics.

## Provisioning with the Azure CLI

```bash
# Log in and select the desired subscription
az login
az account set --subscription <subscription-id>

# Variables used throughout the script
COSMOS_ACCOUNT=<cosmos-account-name>
RESOURCE_GROUP=<resource-group>
DATABASE_NAME=${COSMOS_DATABASE:-ai-hedge-fund}
PORTFOLIOS_CONTAINER=${COSMOS_PORTFOLIOS_CONTAINER:-portfolios}
ANALYST_CONTAINER=${COSMOS_ANALYST_SIGNALS_CONTAINER:-analyst-signals}
DECISIONS_CONTAINER=${COSMOS_DECISIONS_CONTAINER:-decisions}

# Create the account and database (skip the first command if the account exists)
az cosmosdb create --name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" \
  --locations regionName=<azure-region> failoverPriority=0 isZoneRedundant=false

az cosmosdb sql database create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --name "$DATABASE_NAME"

# Portfolio container keeps the latest positions for each user/strategy
az cosmosdb sql container create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --database-name "$DATABASE_NAME" \
  --name "$PORTFOLIOS_CONTAINER" --partition-key-path "/partition_key" \
  --throughput 400

# Analyst signals and decisions containers retain recent run artefacts.  TTL of
# 30 days keeps the dataset lightweight while preserving a reasonable audit
# window. Adjust the default TTL to taste.
az cosmosdb sql container create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --database-name "$DATABASE_NAME" \
  --name "$ANALYST_CONTAINER" --partition-key-path "/partition_key" \
  --throughput 400 --default-ttl 2592000

az cosmosdb sql container create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --database-name "$DATABASE_NAME" \
  --name "$DECISIONS_CONTAINER" --partition-key-path "/partition_key" \
  --throughput 400 --default-ttl 2592000
```

### Seeding optional metadata

You can seed baseline documents to verify connectivity:

```bash
partition_key="demo-user::default-strategy"
run_id=$(uuidgen)

az cosmosdb sql container item create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --database-name "$DATABASE_NAME" \
  --container-name "$PORTFOLIOS_CONTAINER" \
  --partition-key "$partition_key" \
  --content '{
    "id": "'$partition_key'",
    "partition_key": "'$partition_key'",
    "user_id": "demo-user",
    "strategy_id": "default-strategy",
    "portfolio": {"cash": 100000.0, "positions": {}},
    "updated_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'

az cosmosdb sql container item create --account-name "$COSMOS_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --database-name "$DATABASE_NAME" \
  --container-name "$DECISIONS_CONTAINER" \
  --partition-key "$partition_key" \
  --content '{
    "id": "'$run_id'",
    "partition_key": "'$partition_key'",
    "user_id": "demo-user",
    "strategy_id": "default-strategy",
    "run_id": "'$run_id'",
    "document_type": "decisions",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "data": {},
    "metadata": {"tickers": ["AAPL"]}
  }'
```

After provisioning, populate the corresponding environment variables (for local
development you can use a `.env` file) so the new Cosmos repositories are able
to hydrate and persist state.

