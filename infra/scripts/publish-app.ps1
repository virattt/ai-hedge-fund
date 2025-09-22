param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [string]$DeploymentInfoPath = '',

    [string]$ApiImageTag = 'latest',

    [string]$WorkerImageTag = 'latest',

    [string]$ConfigPath = ''
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..' '..')
if ([string]::IsNullOrWhiteSpace($DeploymentInfoPath)) {
    $DeploymentInfoPath = Join-Path $scriptRoot 'latest-deployment.json'
}

if (-not (Test-Path $DeploymentInfoPath)) {
    throw "Deployment output file not found at $DeploymentInfoPath. Run deploy-infrastructure.ps1 first."
}

function Get-OutputValue {
    param(
        [Parameter(Mandatory = $true)] [pscustomobject]$Outputs,
        [Parameter(Mandatory = $true)] [string]$Name
    )
    $entry = $Outputs.$Name
    if (-not $entry) {
        throw "Output '$Name' was not found in deployment outputs."
    }
    return $entry.value
}

function Get-ConfigProperties {
    param(
        [Parameter(Mandatory = $false)] $Node
    )
    if ($null -eq $Node) {
        return @()
    }
    return $Node.PSObject.Properties
}

Write-Host "Loading deployment metadata from $DeploymentInfoPath"
$outputContent = Get-Content -Path $DeploymentInfoPath -Raw | ConvertFrom-Json

$acrName = Get-OutputValue -Outputs $outputContent -Name 'containerRegistryName'
$acrServer = Get-OutputValue -Outputs $outputContent -Name 'containerRegistryLoginServer'
$apiAppName = Get-OutputValue -Outputs $outputContent -Name 'apiContainerAppName'
$jobName = Get-OutputValue -Outputs $outputContent -Name 'queueWorkerJobName'
$functionAppName = Get-OutputValue -Outputs $outputContent -Name 'functionAppName'

Write-Host "Authenticating with Azure subscription $SubscriptionId" -ForegroundColor Cyan
az account show *> $null
if ($LASTEXITCODE -ne 0) {
    az login | Out-Null
}
az account set --subscription $SubscriptionId | Out-Null

Write-Host "Logging in to Azure Container Registry '$acrName'" -ForegroundColor Cyan
az acr login --name $acrName | Out-Null

Set-Location $repoRoot

$apiImage = "$acrServer/ai-hedge-fund-api:$ApiImageTag"
$workerImage = "$acrServer/ai-hedge-fund-worker:$WorkerImageTag"

Write-Host "Building API image $apiImage" -ForegroundColor Cyan
docker build --file docker/Dockerfile --tag $apiImage .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build API container image"
}

Write-Host "Building queue worker image $workerImage" -ForegroundColor Cyan
docker build --file docker/worker.Dockerfile --tag $workerImage .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build worker container image"
}

Write-Host "Pushing API image" -ForegroundColor Cyan
docker push $apiImage
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push API container image"
}

Write-Host "Pushing worker image" -ForegroundColor Cyan
docker push $workerImage
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push worker container image"
}

Write-Host "Updating Container App '$apiAppName'" -ForegroundColor Cyan
az containerapp update --name $apiAppName --resource-group $ResourceGroupName --image $apiImage | Out-Null

Write-Host "Updating Container Apps job '$jobName'" -ForegroundColor Cyan
az containerapp job update --name $jobName --resource-group $ResourceGroupName --set-template-containers "queue-worker=$workerImage" | Out-Null

if ($ConfigPath) {
    if (-not (Test-Path $ConfigPath)) {
        Write-Warning "Config file '$ConfigPath' was not found. Skipping secret updates."
    }
    else {
        Write-Host "Applying secrets and environment variables from $ConfigPath" -ForegroundColor Cyan
        $config = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json -Depth 5

        $containerAppSecrets = Get-ConfigProperties $config.containerApp.secrets
        if ($containerAppSecrets.Count -gt 0) {
            $secretPairs = $containerAppSecrets | ForEach-Object { "{0}={1}" -f $_.Name, $_.Value }
            az containerapp secret set --name $apiAppName --resource-group $ResourceGroupName --secrets $secretPairs | Out-Null
        }
        $containerAppVars = Get-ConfigProperties $config.containerApp.environmentVariables
        if ($containerAppVars.Count -gt 0) {
            $envPairs = $containerAppVars | ForEach-Object { "{0}={1}" -f $_.Name, $_.Value }
            az containerapp update --name $apiAppName --resource-group $ResourceGroupName --set-env-vars $envPairs | Out-Null
        }

        $workerSecrets = Get-ConfigProperties $config.queueWorker.secrets
        if ($workerSecrets.Count -gt 0) {
            $workerSecretPairs = $workerSecrets | ForEach-Object { "{0}={1}" -f $_.Name, $_.Value }
            az containerapp job secret set --name $jobName --resource-group $ResourceGroupName --secrets $workerSecretPairs | Out-Null
        }
        $workerVars = Get-ConfigProperties $config.queueWorker.environmentVariables
        if ($workerVars.Count -gt 0) {
            $workerEnvPairs = $workerVars | ForEach-Object { "{0}={1}" -f $_.Name, $_.Value }
            az containerapp job update --name $jobName --resource-group $ResourceGroupName --set-env-vars $workerEnvPairs | Out-Null
        }
    }
}

$functionSource = Join-Path $repoRoot 'infra/monitoring'
$packagePath = Join-Path $scriptRoot 'functionapp.zip'
if (Test-Path $packagePath) {
    Remove-Item $packagePath -Force
}

Write-Host "Packaging Azure Function from $functionSource" -ForegroundColor Cyan
Push-Location $functionSource
Compress-Archive -Path * -DestinationPath $packagePath -Force
Pop-Location

Write-Host "Deploying monitoring Function App '$functionAppName'" -ForegroundColor Cyan
az functionapp deployment source config-zip --name $functionAppName --resource-group $ResourceGroupName --src $packagePath | Out-Null

if ($ConfigPath -and (Test-Path $ConfigPath)) {
    $config = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json -Depth 5
    $functionSettings = Get-ConfigProperties $config.functionApp.appSettings
    if ($functionSettings.Count -gt 0) {
        $settings = $functionSettings | ForEach-Object { "{0}={1}" -f $_.Name, $_.Value }
        Write-Host "Updating Function App application settings" -ForegroundColor Cyan
        az functionapp config appsettings set --name $functionAppName --resource-group $ResourceGroupName --settings $settings | Out-Null
    }
}

Write-Host "Application deployment complete." -ForegroundColor Green
Write-Host "API image:    $apiImage"
Write-Host "Worker image: $workerImage"
