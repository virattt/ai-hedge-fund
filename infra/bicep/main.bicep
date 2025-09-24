// infra/bicep/main.bicep
targetScope = 'resourceGroup'

// ------------------------- Parameters -------------------------
@description('Azure region for most resources')
param location string = 'westeurope'

@description('Azure region for Cosmos DB. Defaults to `location`. Use this to bypass regional capacity gates.')
param cosmosLocation string = location

@description('Base name used as prefix for resource names. Alphanumerics only.')
param namePrefix string = 'hedgefund'

@description('Name of the queue that stores analysis requests.')
param queueName string = 'analysis-requests'

@description('Name of the dead-letter queue for poison messages.')
param deadLetterQueueName string = 'analysis-deadletter'

@description('Azure region for Container Registry (defaults to location).')
param acrLocation string = location

@description('Resource group name of an existing Azure Container Registry. Leave blank to create a new registry.')
param existingAcrResourceGroup string = ''

@description('Name of an existing Azure Container Registry. Leave blank to create a new registry.')
param existingAcrName string = ''

@description('Admin username for an existing Azure Container Registry. Required when reusing an existing registry.')
param existingAcrUsername string = ''

@secure()
@description('Admin password for an existing Azure Container Registry. Required when reusing an existing registry.')
param existingAcrPassword string = ''

@description('Resource group name of an existing Cosmos DB account. Leave blank to create a new account.')
param existingCosmosResourceGroup string = ''

@description('Name of an existing Cosmos DB account. Leave blank to create a new account.')
param existingCosmosAccountName string = ''

@description('Name of an existing Cosmos DB database to reuse. Required when reusing an existing Cosmos DB account.')
param existingCosmosDatabaseName string = ''

@description('ACR SKU. Use Standard/Premium for higher throughput where available.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param acrSku string = 'Basic'

@description('Enable Cosmos DB free tier (one account per subscription). Turn off if already consumed.')
param enableCosmosFreeTier bool = true

// ------------------------- Naming -------------------------
var baseName = toLower(replace(replace(namePrefix, '-', ''), '_', ''))
var baseSegment = baseName == '' ? 'hedgefund' : baseName
var unique = toLower(uniqueString(resourceGroup().id, baseSegment))

var storageAccountName = take('${baseSegment}st${unique}', 24)
var containerRegistryName = take('${baseSegment}acr${unique}', 50)
var cosmosAccountName = take('${baseSegment}cosmos${unique}', 44)
var logAnalyticsWorkspaceName = take('${baseSegment}-law', 63)
var appInsightsName = take('${baseSegment}-appi', 63)
var containerAppsEnvironmentName = take('${baseSegment}-cae', 32)
var apiContainerAppName = take('${baseSegment}-api', 32)
var queueWorkerJobName = take('${baseSegment}-queuejob', 32)
var functionPlanName = take('${baseSegment}-func-plan', 40)
var functionAppName = take('${baseSegment}-monitor', 60)
var cosmosDatabaseName = take('${baseSegment}-db', 63)
var portfolioContainerName = 'portfolios'
var analystSignalsContainerName = 'analyst-signals'
var decisionsContainerName = 'decisions'
var portfolioSnapshotsContainerName = 'portfolioSnapshots'
var runResultsContainerName = 'hedgeFundResults'
var runStatusContainerName = 'hedgeFundStatus'
var brokerOrdersContainerName = 'broker-orders'
var monitorCooldownContainerName = 'monitor-cooldowns'

var sanitizedQueueName = toLower(replace(queueName, '_', '-'))
var sanitizedDeadLetterQueueName = toLower(replace(deadLetterQueueName, '_', '-'))

var useExistingAcr = existingAcrName != ''
var useExistingCosmos = existingCosmosAccountName != ''

// ------------------------- Log Analytics -------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  sku: {
    name: 'PerGB2018'
  }
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: -1
    }
  }
}

// ------------------------- Application Insights -------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ------------------------- Azure Container Registry -------------------------
resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' = if (!useExistingAcr) {
  name: containerRegistryName
  location: acrLocation
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: true
    dataEndpointEnabled: false
    policies: {
      retentionPolicy: {
        status: 'enabled'
        days: 7
      }
    }
  }
}

resource acrExisting 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = if (useExistingAcr) {
  scope: resourceGroup(subscription().subscriptionId, existingAcrResourceGroup)
  name: existingAcrName
}

var acrCredentials = !useExistingAcr ? acr.listCredentials() : null
var acrLoginServer = useExistingAcr ? acrExisting.properties.loginServer : acr.properties.loginServer
var acrAdminUsername = useExistingAcr ? existingAcrUsername : acrCredentials.username
var acrAdminPassword = useExistingAcr ? existingAcrPassword : acrCredentials.passwords[0].value


// ------------------------- Storage + Queues -------------------------
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource storageQueueService 'Microsoft.Storage/storageAccounts/queueServices@2025-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

resource analysisQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-01-01' = {
  parent: storageQueueService
  name: sanitizedQueueName
  properties: {
    metadata: { purpose: 'analysis-requests' }
  }
}

resource deadLetterQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-01-01' = {
  parent: storageQueueService
  name: sanitizedDeadLetterQueueName
  properties: {
    metadata: { purpose: 'analysis-deadletter' }
  }
}

var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

// ------------------------- Cosmos DB (Serverless) -------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' = if (!useExistingCosmos) {
  name: cosmosAccountName
  location: cosmosLocation
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    enableAutomaticFailover: false
    enableFreeTier: enableCosmosFreeTier
    locations: [
      {
        locationName: cosmosLocation
        failoverPriority: 0
        isZoneRedundant: false // keep non-AZ to bypass zone capacity gates
      }
    ]
    capabilities: [
      { name: 'EnableServerless' }
    ]
    backupPolicy: {
      type: 'Continuous'
    }
  }
}

resource cosmosAccountRefNew 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' existing = if (!useExistingCosmos) {
  name: cosmosAccount.name
}

resource cosmosAccountRefExisting 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' existing = if (useExistingCosmos) {
  scope: resourceGroup(subscription().subscriptionId, existingCosmosResourceGroup)
  name: existingCosmosAccountName
}

var effectiveCosmosAccountName = useExistingCosmos ? existingCosmosAccountName : cosmosAccount.name
var effectiveCosmosDatabaseName = useExistingCosmos && existingCosmosDatabaseName != '' ? existingCosmosDatabaseName : cosmosDatabaseName
var cosmosKeys = useExistingCosmos ? cosmosAccountRefExisting.listKeys() : cosmosAccountRefNew.listKeys()
var cosmosDocumentEndpoint = useExistingCosmos ? cosmosAccountRefExisting.properties.documentEndpoint : cosmosAccountRefNew.properties.documentEndpoint

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-04-15' = if (!useExistingCosmos) {
  parent: cosmosAccount
  name: cosmosDatabaseName
  properties: {
    resource: { id: cosmosDatabaseName }
    options: {}
  }
}

// Containers module
module cosmosContainers 'modules/cosmos-containers.bicep' = if (!useExistingCosmos) {
  name: 'cosmos-containers'
  params: {
    databaseAccountName: effectiveCosmosAccountName
    databaseName: cosmosDatabaseName
    portfolioContainerName: portfolioContainerName
    analystSignalsContainerName: analystSignalsContainerName
    decisionsContainerName: decisionsContainerName
    portfolioSnapshotsContainerName: portfolioSnapshotsContainerName
    runResultsContainerName: runResultsContainerName
    runStatusContainerName: runStatusContainerName
    brokerOrdersContainerName: brokerOrdersContainerName
    monitorCooldownContainerName: monitorCooldownContainerName
  }
  dependsOn: [ cosmosDatabase ]
}

// ------------------------- Container Apps Environment -------------------------
resource managedEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    daprAIInstrumentationKey: appInsights.properties.InstrumentationKey
  }
}

// ------------------------- API Container App -------------------------
resource apiContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiContainerAppName
  location: location
  properties: {
    managedEnvironmentId: managedEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrAdminUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password', value: acrAdminPassword }
        { name: 'cosmos-key', value: cosmosKeys.primaryMasterKey }
        { name: 'queue-account-key', value: storage.listKeys().keys[0].value }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/ai-hedge-fund-api:latest'
          command: [ 'python' ]
          args: [ '-m', 'uvicorn', 'app.backend.main:app', '--host', '0.0.0.0', '--port', '8000' ]
          env: [
            { name: 'PORT', value: '8000' }
            { name: 'COSMOS_ENDPOINT', value: cosmosDocumentEndpoint }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'COSMOS_DATABASE', value: effectiveCosmosDatabaseName }
            { name: 'COSMOS_PORTFOLIOS_CONTAINER', value: portfolioContainerName }
            { name: 'COSMOS_ANALYST_SIGNALS_CONTAINER', value: analystSignalsContainerName }
            { name: 'COSMOS_DECISIONS_CONTAINER', value: decisionsContainerName }
            { name: 'COSMOS_SNAPSHOT_CONTAINER', value: portfolioSnapshotsContainerName }
            { name: 'COSMOS_RESULTS_CONTAINER', value: runResultsContainerName }
            { name: 'COSMOS_STATUS_CONTAINER', value: runStatusContainerName }
            { name: 'COSMOS_CONTAINER', value: brokerOrdersContainerName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          resources: { cpu: 1, memory: '2Gi' }
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

// ------------------------- Queue Worker Job (Event-driven) -------------------------
resource queueWorkerJob 'Microsoft.App/jobs@2024-03-01' = {
  name: queueWorkerJobName
  location: location
  properties: {
    environmentId: managedEnv.id
    configuration: {
      replicaTimeout: 900
      registries: [
        {
          server: acrLoginServer
          username: acrAdminUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password', value: acrAdminPassword }
        { name: 'cosmos-key', value: cosmosKeys.primaryMasterKey }
        { name: 'queue-account-key', value: storage.listKeys().keys[0].value }
        // Secret used by the scaler (matches triggerParameter 'connection')
        { name: 'queue-connection-string', value: storageConnectionString }
      ]
      triggerType: 'Event'
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 10
          pollingInterval: 30
          rules: [
            {
              name: 'storage-queue-trigger'
              type: 'azure-queue' // correct scaler type for Container Apps Jobs
              metadata: {
                accountName: storage.name
                queueName: sanitizedQueueName
                queueLength: '1'
              }
              auth: [
                {
                  secretRef: 'queue-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          ]
        }
      }
    }
    template: {
      containers: [
        {
          name: 'queue-worker'
          image: '${acrLoginServer}/ai-hedge-fund-worker:latest'
          env: [
            { name: 'COSMOS_ENDPOINT', value: cosmosDocumentEndpoint }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'COSMOS_DATABASE', value: effectiveCosmosDatabaseName }
            { name: 'COSMOS_SNAPSHOT_CONTAINER', value: portfolioSnapshotsContainerName }
            { name: 'COSMOS_RESULTS_CONTAINER', value: runResultsContainerName }
            { name: 'COSMOS_STATUS_CONTAINER', value: runStatusContainerName }
            { name: 'QUEUE_ACCOUNT', value: storage.name }
            { name: 'QUEUE_NAME', value: sanitizedQueueName }
            // This is the data-plane key (naming kept from your original env)
            { name: 'QUEUE_SAS', secretRef: 'queue-account-key' }
            { name: 'QUEUE_DEAD_LETTER_NAME', value: sanitizedDeadLetterQueueName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          resources: { cpu: 1, memory: '2Gi' }
        }
      ]
    }
  }
}

// ------------------------- Function App (Linux Consumption) -------------------------
resource functionPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: { name: 'Y1', tier: 'Dynamic' }
  properties: { reserved: true } // Linux
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage', value: storageConnectionString }
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'MARKET_MONITOR_QUEUE_CONNECTION_STRING', value: storageConnectionString }
        { name: 'MARKET_MONITOR_QUEUE_NAME', value: sanitizedQueueName }
        { name: 'COSMOS_ENDPOINT', value: cosmosDocumentEndpoint }
        { name: 'COSMOS_KEY', value: cosmosKeys.primaryMasterKey }
        { name: 'COSMOS_DATABASE', value: effectiveCosmosDatabaseName }
        { name: 'COSMOS_CONTAINER', value: monitorCooldownContainerName }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
      ]
      linuxFxVersion: 'Python|3.11'
    }
  }
  tags: { displayName: 'MarketMonitoringFunction' }
}

// ------------------------- Outputs -------------------------
output containerRegistryName string = useExistingAcr ? existingAcrName : containerRegistryName
output containerRegistryLoginServer string = acrLoginServer
output storageAccountName string = storage.name
output storageQueueName string = sanitizedQueueName
output storageDeadLetterQueueName string = sanitizedDeadLetterQueueName
output storageConnectionString string = storageConnectionString
output cosmosAccountName string = effectiveCosmosAccountName
output cosmosEndpoint string = cosmosDocumentEndpoint
output cosmosDatabaseName string = effectiveCosmosDatabaseName
output cosmosContainers object = {
  portfolios: portfolioContainerName
  analystSignals: analystSignalsContainerName
  decisions: decisionsContainerName
  snapshots: portfolioSnapshotsContainerName
  runResults: runResultsContainerName
  runStatus: runStatusContainerName
  brokerOrders: brokerOrdersContainerName
  monitorCooldowns: monitorCooldownContainerName
}
output managedEnvironmentName string = containerAppsEnvironmentName
output apiContainerAppName string = apiContainerAppName
output queueWorkerJobName string = queueWorkerJobName
output functionAppName string = functionAppName
output functionPlanName string = functionPlanName
output logAnalyticsWorkspaceId string = logAnalytics.id
output appInsightsName string = appInsights.name
