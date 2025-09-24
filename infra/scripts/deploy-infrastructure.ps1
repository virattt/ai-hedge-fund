param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ResourceGroupName,

    [ValidateNotNullOrEmpty()]
    [string]$NamePrefix = 'hedgefund',

    [ValidateNotNullOrEmpty()]
    [string]$Location = 'westeurope',

    [ValidateNotNullOrEmpty()]
    [string]$CosmosLocation = '',

    [ValidateNotNullOrEmpty()]
    [string]$QueueName = 'analysis-requests',

    [ValidateNotNullOrEmpty()]
    [string]$DeadLetterQueueName = 'analysis-deadletter',

    [ValidateSet('Standard', 'Premium')]
    [string]$AcrSku = 'Standard',

    [ValidateNotNullOrEmpty()]
    [string]$AcrLocation = '',


    [switch]$EnableCosmosFreeTier = $true,

    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

try {
    Write-Host "Starting Azure deployment..." -ForegroundColor Green

    # Get script paths
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot   = Resolve-Path (Join-Path (Join-Path $scriptRoot '..') '..')
    $bicepPath  = Join-Path (Join-Path (Join-Path $repoRoot 'infra') 'bicep') 'main.bicep'
    $outputPath = Join-Path $scriptRoot 'latest-deployment.json'

    Write-Host "Script root: $scriptRoot" -ForegroundColor Gray
    Write-Host "Repository root: $repoRoot" -ForegroundColor Gray
    Write-Host "Using Bicep template: $bicepPath" -ForegroundColor Cyan

    # Verify Bicep template exists
    if (-not (Test-Path $bicepPath)) {
        throw "Unable to locate Bicep template at: $bicepPath"
    }

    # Check if Azure CLI is installed and has Bicep extension
    Write-Host "Checking Azure CLI and Bicep..." -ForegroundColor Cyan
    try {
        $azVersion = az --version 2>$null
        if (-not $azVersion) { throw "Azure CLI check failed" }
        
        # Check if Bicep is available
        az bicep version 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Installing Bicep extension..." -ForegroundColor Yellow
            az bicep install --only-show-errors
            if ($LASTEXITCODE -ne 0) { throw "Failed to install Bicep extension" }
        }
        
        Write-Host "Azure CLI and Bicep are available" -ForegroundColor Green
    }
    catch {
        throw "Azure CLI is not installed or not in PATH. Please install Azure CLI first."
    }

    # Authenticate with Azure
    Write-Host "Authenticating with Azure subscription $SubscriptionId..." -ForegroundColor Cyan
    $currentAccount = $null
    try {
        $accountJson = az account show 2>$null
        if ($accountJson) { $currentAccount = $accountJson | ConvertFrom-Json }
    }
    catch {
        Write-Host "No current Azure session found" -ForegroundColor Yellow
    }

    if (-not $currentAccount -or $currentAccount.id -ne $SubscriptionId) {
        Write-Host "Logging into Azure..." -ForegroundColor Yellow
        az login --only-show-errors
        if ($LASTEXITCODE -ne 0) { throw "Azure login failed" }
    }

    # Set the subscription
    Write-Host "Setting subscription to $SubscriptionId..." -ForegroundColor Cyan
    az account set --subscription $SubscriptionId --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Failed to set subscription to $SubscriptionId" }

    # Verify subscription
    $verifyAccount = az account show --only-show-errors | ConvertFrom-Json
    if ($verifyAccount.id -ne $SubscriptionId) {
        throw "Failed to verify subscription setting"
    }
    Write-Host "Subscription verified: $($verifyAccount.name)" -ForegroundColor Green

    # Create resource group
    Write-Host "Ensuring resource group '$ResourceGroupName' exists in $Location..." -ForegroundColor Cyan
    az group create --name $ResourceGroupName --location $Location --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Failed to create resource group $ResourceGroupName" }

    # Generate deployment name
    $deploymentName = "ai-hedge-fund-$(Get-Date -Format 'yyyyMMddHHmmss')"
    Write-Host "Deployment name: $deploymentName" -ForegroundColor Gray

    # Prepare parameters
    $deploymentParams = @(
        "namePrefix=$NamePrefix"
        "location=$Location"
        "queueName=$QueueName"
        "deadLetterQueueName=$DeadLetterQueueName"
        "acrSku=$AcrSku"
        "enableCosmosFreeTier=$($EnableCosmosFreeTier.ToString().ToLower())"
    )

    # Add cosmosLocation parameter if specified
    if ($CosmosLocation) { $deploymentParams += "cosmosLocation=$CosmosLocation" }
    if ($AcrLocation)    { $deploymentParams += "acrLocation=$AcrLocation" }

    # Display parameters
    Write-Host "Deployment Parameters:" -ForegroundColor Gray
    Write-Host " - Name Prefix: $NamePrefix" -ForegroundColor Gray
    Write-Host " - Location: $Location" -ForegroundColor Gray
    if ($CosmosLocation -and $CosmosLocation -ne '') {
        Write-Host " - Cosmos Location: $CosmosLocation" -ForegroundColor Gray
    }
    Write-Host " - Queue Name: $QueueName" -ForegroundColor Gray
    Write-Host " - Dead Letter Queue: $DeadLetterQueueName" -ForegroundColor Gray
    Write-Host " - ACR SKU: $AcrSku" -ForegroundColor Gray
    Write-Host " - Cosmos Free Tier: $EnableCosmosFreeTier" -ForegroundColor Gray

    # Run what-if if requested
    if ($WhatIf) {
        Write-Host "Running what-if analysis for deployment..." -ForegroundColor Yellow
        az deployment group what-if `
            --name $deploymentName `
            --resource-group $ResourceGroupName `
            --template-file $bicepPath `
            --parameters $deploymentParams `
            --only-show-errors
        if ($LASTEXITCODE -ne 0) { throw "What-if analysis failed" }
        Write-Host "What-if analysis completed successfully" -ForegroundColor Green
        return
    }

    # Deploy infrastructure
    Write-Host "Deploying infrastructure (this may take several minutes)..." -ForegroundColor Cyan
    Write-Host "Note: Container Apps and Cosmos DB provisioning can take 5-10 minutes" -ForegroundColor Yellow
    
    $deploymentJson = az deployment group create `
        --name $deploymentName `
        --resource-group $ResourceGroupName `
        --template-file $bicepPath `
        --parameters $deploymentParams `
        --output json --only-show-errors

    if ($LASTEXITCODE -ne 0 -or -not $deploymentJson) {
        throw "Deployment failed. Check the Azure portal for detailed error information."
    }

    # Parse deployment output
    try { $deployment = $deploymentJson | ConvertFrom-Json }
    catch { throw "Failed to parse deployment JSON output: $_" }

    if (-not $deployment) { throw "Deployment completed but no deployment object was returned." }

    # Extract outputs
    $outputs = $deployment.properties.outputs
    if (-not $outputs) {
        throw "Deployment completed but no outputs were returned. Check the Bicep template for output definitions."
    }

    # Save outputs
    Write-Host "Saving deployment outputs..." -ForegroundColor Cyan
    $outputs | ConvertTo-Json -Depth 5 | Out-File -FilePath $outputPath -Encoding UTF8
    Write-Host "Deployment outputs saved to: $outputPath" -ForegroundColor Green

    # Display comprehensive summary
    Write-Host ""
    Write-Host "Deployment Summary:" -ForegroundColor Green
    Write-Host "==================" -ForegroundColor Green
    
    $summary = [ordered]@{}
    if ($outputs.containerRegistryName) { $summary.'Container Registry' = $outputs.containerRegistryName.value }
    if ($outputs.containerRegistryLoginServer) { $summary.'ACR Login Server' = $outputs.containerRegistryLoginServer.value }
    if ($outputs.managedEnvironmentName) { $summary.'Container Apps Environment' = $outputs.managedEnvironmentName.value }
    if ($outputs.apiContainerAppName) { $summary.'API Container App' = $outputs.apiContainerAppName.value }
    if ($outputs.queueWorkerJobName) { $summary.'Queue Worker Job' = $outputs.queueWorkerJobName.value }
    if ($outputs.functionAppName) { $summary.'Function App' = $outputs.functionAppName.value }
    if ($outputs.cosmosAccountName) { $summary.'Cosmos DB Account' = $outputs.cosmosAccountName.value }
    if ($outputs.cosmosDatabaseName) { $summary.'Cosmos Database' = $outputs.cosmosDatabaseName.value }
    if ($outputs.storageAccountName) { $summary.'Storage Account' = $outputs.storageAccountName.value }
    if ($outputs.storageQueueName) { $summary.'Analysis Queue' = $outputs.storageQueueName.value }
    if ($outputs.storageDeadLetterQueueName) { $summary.'Dead Letter Queue' = $outputs.storageDeadLetterQueueName.value }
    if ($outputs.appInsightsName) { $summary.'Application Insights' = $outputs.appInsightsName.value }

    $summary.GetEnumerator() | ForEach-Object {
        Write-Host (" {0}: {1}" -f $_.Key, $_.Value) -ForegroundColor White
    }

    # Display Cosmos containers if available
    if ($outputs.cosmosContainers -and $outputs.cosmosContainers.value) {
        Write-Host ""
        Write-Host "Cosmos DB Containers:" -ForegroundColor Cyan
        $containers = $outputs.cosmosContainers.value
        $containers.PSObject.Properties | ForEach-Object {
            Write-Host (" {0}: {1}" -f $_.Name, $_.Value) -ForegroundColor White
        }
    }

    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Use the following file when publishing application code:" -ForegroundColor Yellow
    Write-Host " $(Resolve-Path $outputPath)" -ForegroundColor White
    Write-Host "2. Build and push your container images to ACR:" -ForegroundColor Yellow
    if ($outputs.containerRegistryLoginServer) {
        Write-Host " docker build -t $($outputs.containerRegistryLoginServer.value)/ai-hedge-fund-api:latest ." -ForegroundColor White
        Write-Host " docker build -t $($outputs.containerRegistryLoginServer.value)/ai-hedge-fund-worker:latest ." -ForegroundColor White
        Write-Host " az acr login --name $($outputs.containerRegistryName.value)" -ForegroundColor White
        Write-Host " docker push $($outputs.containerRegistryLoginServer.value)/ai-hedge-fund-api:latest" -ForegroundColor White
        Write-Host " docker push $($outputs.containerRegistryLoginServer.value)/ai-hedge-fund-worker:latest" -ForegroundColor White
    }
    Write-Host "3. Deploy your Function App code" -ForegroundColor Yellow
    Write-Host "4. Configure any additional application settings as needed" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace:" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
}
finally {
    $ProgressPreference = 'Continue'
}