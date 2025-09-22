param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [string]$NamePrefix = 'hedgefund',

    [string]$Location = 'westeurope',

    [string]$QueueName = 'analysis-requests',

    [string]$DeadLetterQueueName = 'analysis-deadletter',

    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..' '..')
$bicepPath = Join-Path $repoRoot 'infra/bicep/main.bicep'
$outputPath = Join-Path $scriptRoot 'latest-deployment.json'

Write-Host "Using Bicep template: $bicepPath"
if (-not (Test-Path $bicepPath)) {
    throw "Unable to locate Bicep template at $bicepPath"
}

Write-Host "Authenticating with Azure subscription $SubscriptionId" -ForegroundColor Cyan
az account show *> $null
if ($LASTEXITCODE -ne 0) {
    az login | Out-Null
}
az account set --subscription $SubscriptionId | Out-Null

Write-Host "Ensuring resource group '$ResourceGroupName' exists in $Location" -ForegroundColor Cyan
az group create --name $ResourceGroupName --location $Location | Out-Null

$deploymentName = "ai-hedge-fund-$(Get-Date -Format 'yyyyMMddHHmmss')"

if ($WhatIf) {
    Write-Host "Running what-if for deployment $deploymentName" -ForegroundColor Yellow
    az deployment group what-if \
        --name $deploymentName \
        --resource-group $ResourceGroupName \
        --template-file $bicepPath \
        --parameters "namePrefix=$NamePrefix" \
                     "location=$Location" \
                     "queueName=$QueueName" \
                     "deadLetterQueueName=$DeadLetterQueueName"
    return
}

Write-Host "Deploying infrastructure (this may take several minutes)..." -ForegroundColor Cyan
$deployment = az deployment group create \
    --name $deploymentName \
    --resource-group $ResourceGroupName \
    --template-file $bicepPath \
    --parameters "namePrefix=$NamePrefix" \
                 "location=$Location" \
                 "queueName=$QueueName" \
                 "deadLetterQueueName=$DeadLetterQueueName" |
    ConvertFrom-Json

if (-not $deployment) {
    throw "Deployment failed. Inspect the Azure CLI output for details."
}

$outputs = $deployment.properties.outputs
if (-not $outputs) {
    throw "Deployment completed but no outputs were returned."
}

$outputs | ConvertTo-Json -Depth 5 | Out-File -FilePath $outputPath -Encoding utf8

Write-Host "Deployment outputs saved to $outputPath" -ForegroundColor Green
Write-Host "Key resource names:" -ForegroundColor Green
$summary = [ordered]@{
    ContainerRegistry = $outputs.containerRegistryName.value
    ManagedEnvironment = $outputs.managedEnvironmentName.value
    ApiContainerApp = $outputs.apiContainerAppName.value
    QueueWorkerJob = $outputs.queueWorkerJobName.value
    FunctionApp = $outputs.functionAppName.value
    CosmosAccount = $outputs.cosmosAccountName.value
    StorageAccount = $outputs.storageAccountName.value
    AnalysisQueue = $outputs.storageQueueName.value
}
$summary.GetEnumerator() | ForEach-Object {
    Write-Host ("  {0}: {1}" -f $_.Key, $_.Value)
}

Write-Host "Use $(Resolve-Path $outputPath) when publishing application code." -ForegroundColor Cyan
