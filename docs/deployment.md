# Automated Azure Deployment

This guide explains how to provision the minimum Azure footprint for the AI Hedge Fund project and publish the application code with a single-run script. Infrastructure is described in Bicep and the deployment workflow uses simple PowerShell wrappers around the Azure CLI, so you do not need to stand up a dedicated CI/CD system.

## Architecture

The `infra/bicep/main.bicep` template provisions the following resources in **West Europe** by default:

| Layer | Azure resource | Purpose |
| ----- | -------------- | ------- |
| Container Registry | Azure Container Registry (Basic SKU) | Stores container images for the FastAPI backend and queue worker. |
| Compute | Azure Container Apps environment | Hosts the public API container app and the queue-triggered worker job. |
| State | Azure Cosmos DB (serverless, SQL API) | Persists portfolios, analyst decisions, run artefacts, broker orders, and monitoring cooldown metadata. |
| Messaging | Storage account + Azure Storage queues | Holds market-monitor alerts and dead-letter messages for failed jobs. |
| Monitoring | Log Analytics workspace + Application Insights | Centralises diagnostics for Container Apps, Functions, and custom telemetry. |
| Serverless | Azure Function App (Consumption plan) | Runs the five-minute market monitor timer trigger. |

> The template also wires up the required application settings: queue connection strings, Cosmos DB credentials, and Application Insights connection strings are stored as secrets in Container Apps and the Function App.

## Prerequisites

- Azure CLI 2.56.0 or later
- Docker Engine (for building images locally)
- PowerShell 7 (scripts assume cross-platform PowerShell)
- An Azure subscription where you have at least **Contributor** rights
- Logged-in Azure CLI session (`az login`)

## 1. Provision infrastructure

Use `infra/scripts/deploy-infrastructure.ps1` to compile the Bicep template and apply it to a resource group. The script creates the resource group if necessary and saves all deployment outputs to `infra/scripts/latest-deployment.json` for subsequent steps.

```powershell
# Example: deploy into subscription 00000000-0000-0000-0000-000000000000
# Resources will land in West Europe and use the prefix "hedgefund"

./infra/scripts/deploy-infrastructure.ps1 `
    -SubscriptionId "a604d967-963b-4ff5-acb7-f0aaec811978" `
    -ResourceGroupName "rg-ai-hedge-fund" `
    -NamePrefix "hedgefund" `
    -Location "westeurope" `
    -CosmosLocation "northeurope" `
    -AcrSku "Standard" `
    -AcrLocation "northeurope"
```

Optional: append `-WhatIf` to preview the changes without creating resources.

On success the script prints the key resource names (registry, container app, job, function app, etc.) and stores every output in `infra/scripts/latest-deployment.json`.

## 2. Populate secret values (optional but recommended)

Create a copy of `infra/scripts/deployment-settings.example.json`, fill in your API keys, and save it alongside the scripts:

```bash
cp infra/scripts/deployment-settings.example.json infra/scripts/deployment-settings.json
```

You can remove any keys you do not need; the publish script only pushes the values that are present. Secrets are injected as Container App secrets/app settings, while plain environment variables are set with `--set-env-vars`.

## 3. Publish containers and Functions code

`infra/scripts/publish-app.ps1` builds both Docker images, pushes them to the registry, updates the Container Apps resources to use the new tags, zips the Azure Function code, and deploys it with `az functionapp deployment source config-zip`.

```powershell
./infra/scripts/publish-app.ps1 \`
    -SubscriptionId "a604d967-963b-4ff5-acb7-f0aaec811978" `
    -ResourceGroupName "rg-ai-hedge-fund" `
    -ApiImageTag "v1" `
    -WorkerImageTag "v1" `
    -ConfigPath "infra/scripts/deployment-settings.json"
```

The script reuses `infra/scripts/latest-deployment.json` by default. If you stored the Bicep outputs elsewhere, pass `-DeploymentInfoPath <path>`.

### What the publish script does

1. Logs into the subscription and Azure Container Registry.
2. Builds and pushes `ai-hedge-fund-api:<tag>` and `ai-hedge-fund-worker:<tag>` from the repository root.
3. Updates the Container App and queue worker job to reference the new images.
4. Applies optional secrets/app settings defined in the JSON config file.
5. Packages the `infra/monitoring` Function App and deploys it via zip deploy.

## Validation checklist

After the scripts finish, verify the deployment:

- **Cosmos DB** contains the expected containers (`portfolios`, `analyst-signals`, `decisions`, `portfolioSnapshots`, `hedgeFundResults`, `hedgeFundStatus`, `broker-orders`, `monitor-cooldowns`).
- **Storage account** hosts the queues `<prefix>analysis-requests` and `<prefix>analysis-deadletter`.
- **Container Apps** show healthy revisions for the API and the queue worker job (the job idles until new messages arrive).
- **Function App** has the monitoring function deployed and scheduled (check Application Insights logs for heartbeat events).

You can rerun `publish-app.ps1` whenever you update code or change secrets. Re-run `deploy-infrastructure.ps1` only when you modify the Bicep template or need to recreate the environment.

