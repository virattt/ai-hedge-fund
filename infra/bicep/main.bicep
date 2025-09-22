// Main Bicep template for AI Hedge Fund deployment
// Provisions core Azure resources required for the autonomous trading assistant

@description('Azure region for all resources')
param location string = 'westeurope'

@description('Base name used as prefix for resource names. Only alphanumeric characters are allowed.')
param namePrefix string = 'hedgefund'

@description('Name of the queue that stores analysis requests.')
param queueName string = 'analysis-requests'

@description('Name of the dead-letter queue for poison messages.')
param deadLetterQueueName string = 'analysis-deadletter'

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

// -----------------------------------------------------------------------------
// Log Analytics workspace
// -----------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: -1
    }
  }
  sku: {
    name: 'PerGB2018'
  }
}

var logAnalyticsSharedKeys = listKeys(logAnalytics.id, '2020-08-01')

// -----------------------------------------------------------------------------
// Application Insights (linked to Log Analytics)
// -----------------------------------------------------------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// -----------------------------------------------------------------------------
// Azure Container Registry
// -----------------------------------------------------------------------------
resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
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

var acrCredentials = listCredentials(acr.id, '2023-01-01-preview')

// -----------------------------------------------------------------------------
// Storage account + queues
// -----------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
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

resource storageQueueService 'Microsoft.Storage/storageAccounts/queueServices@2023-01-01' = {
  name: '${storage.name}/default'
  properties: {
    cors: {
      corsRules: []
    }
  }
  dependsOn: [
    storage
  ]
}

resource analysisQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storage.name}/default/${sanitizedQueueName}'
  properties: {
    metadata: {
      purpose: 'analysis-requests'
    }
  }
  dependsOn: [
    storageQueueService
  ]
}

resource deadLetterQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storage.name}/default/${sanitizedDeadLetterQueueName}'
  properties: {
    metadata: {
      purpose: 'analysis-deadletter'
    }
  }
  dependsOn: [
    storageQueueService
  ]
}

var storageKeys = listKeys(storage.id, '2023-01-01')
var storageAccountKey = storageKeys.keys[0].value
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storageAccountKey};EndpointSuffix=${environment().suffixes.storage}'

// -----------------------------------------------------------------------------
// Cosmos DB account + database + containers
// -----------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    enableAutomaticFailover: false
    enableFreeTier: true
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    backupPolicy: {
      type: 'Continuous'
    }
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  name: '${cosmosAccount.name}/${cosmosDatabaseName}'
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
    options: {}
  }
}

// Helper to declare Cosmos containers
module cosmosContainers 'modules/cosmos-containers.bicep' = {
  name: 'cosmos-containers'
  params: {
    databaseAccountName: cosmosAccount.name
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
  dependsOn: [
    cosmosDatabase
  ]
}

var cosmosKeys = listKeys(cosmosAccount.id, '2023-04-15')

// -----------------------------------------------------------------------------
// Container Apps environment
// -----------------------------------------------------------------------------
resource managedEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalyticsSharedKeys.primarySharedKey
      }
    }
    daprAIInstrumentationKey: appInsights.properties.InstrumentationKey
  }
}

// -----------------------------------------------------------------------------
// API container app (FastAPI backend)
// -----------------------------------------------------------------------------
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
          server: acr.properties.loginServer
          username: acrCredentials.username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrCredentials.passwords[0].value
        }
        {
          name: 'cosmos-key'
          value: cosmosKeys.primaryMasterKey
        }
        {
          name: 'queue-account-key'
          value: storageAccountKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acr.properties.loginServer}/ai-hedge-fund-api:latest'
          command: [
            'python'
          ]
          args: [
            '-m'
            'uvicorn'
            'app.backend.main:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8000'
          ]
          env: [
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosAccount.properties.documentEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDatabaseName
            }
            {
              name: 'COSMOS_PORTFOLIOS_CONTAINER'
              value: portfolioContainerName
            }
            {
              name: 'COSMOS_ANALYST_SIGNALS_CONTAINER'
              value: analystSignalsContainerName
            }
            {
              name: 'COSMOS_DECISIONS_CONTAINER'
              value: decisionsContainerName
            }
            {
              name: 'COSMOS_SNAPSHOT_CONTAINER'
              value: portfolioSnapshotsContainerName
            }
            {
              name: 'COSMOS_RESULTS_CONTAINER'
              value: runResultsContainerName
            }
            {
              name: 'COSMOS_STATUS_CONTAINER'
              value: runStatusContainerName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: brokerOrdersContainerName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

// -----------------------------------------------------------------------------
// Queue worker Container Apps job
// -----------------------------------------------------------------------------
resource queueWorkerJob 'Microsoft.App/jobs@2024-03-01' = {
  name: queueWorkerJobName
  location: location
  properties: {
    environmentId: managedEnv.id
    configuration: {
      registries: [
        {
          server: acr.properties.loginServer
          username: acrCredentials.username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrCredentials.passwords[0].value
        }
        {
          name: 'cosmos-key'
          value: cosmosKeys.primaryMasterKey
        }
        {
          name: 'queue-account-key'
          value: storageAccountKey
        }
        {
          name: 'queue-connection'
          value: storageConnectionString
        }
      ]
      triggerType: 'Event'
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 10
          pollingInterval: 'PT30S'
          rules: [
            {
              name: 'storage-queue-trigger'
              type: 'azure-storage-queue'
              metadata: {
                accountName: storage.name
                queueName: sanitizedQueueName
              }
              auth: [
                {
                  secretRef: 'queue-connection'
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
          image: '${acr.properties.loginServer}/ai-hedge-fund-worker:latest'
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosAccount.properties.documentEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDatabaseName
            }
            {
              name: 'COSMOS_SNAPSHOT_CONTAINER'
              value: portfolioSnapshotsContainerName
            }
            {
              name: 'COSMOS_RESULTS_CONTAINER'
              value: runResultsContainerName
            }
            {
              name: 'COSMOS_STATUS_CONTAINER'
              value: runStatusContainerName
            }
            {
              name: 'QUEUE_ACCOUNT'
              value: storage.name
            }
            {
              name: 'QUEUE_NAME'
              value: sanitizedQueueName
            }
            {
              name: 'QUEUE_SAS'
              secretRef: 'queue-account-key'
            }
            {
              name: 'QUEUE_DEAD_LETTER_NAME'
              value: sanitizedDeadLetterQueueName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
          ]
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
        }
      ]
    }
  }
}

// -----------------------------------------------------------------------------
// Consumption plan and Function App for monitoring
// -----------------------------------------------------------------------------
resource functionPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'PYTHON_VERSION'
          value: '3.11'
        }
        {
          name: 'MARKET_MONITOR_QUEUE_CONNECTION_STRING'
          value: storageConnectionString
        }
        {
          name: 'MARKET_MONITOR_QUEUE_NAME'
          value: sanitizedQueueName
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosAccount.properties.documentEndpoint
        }
        {
          name: 'COSMOS_KEY'
          value: cosmosKeys.primaryMasterKey
        }
        {
          name: 'COSMOS_DATABASE'
          value: cosmosDatabaseName
        }
        {
          name: 'COSMOS_CONTAINER'
          value: monitorCooldownContainerName
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
      ]
      linuxFxVersion: 'Python|3.11'
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: {
    'displayName': 'MarketMonitoringFunction'
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output containerRegistryName string = containerRegistryName
output containerRegistryLoginServer string = acr.properties.loginServer
output storageAccountName string = storage.name
output storageQueueName string = sanitizedQueueName
output storageDeadLetterQueueName string = sanitizedDeadLetterQueueName
output storageConnectionString string = storageConnectionString
output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosDatabaseName string = cosmosDatabaseName
output cosmosKey string = cosmosKeys.primaryMasterKey
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
