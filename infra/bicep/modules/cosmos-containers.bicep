@description('Name of the Cosmos DB account to configure.')
param databaseAccountName string

@description('Name of the SQL database inside the Cosmos account.')
param databaseName string

@description('Container used to persist user portfolio snapshots.')
param portfolioContainerName string

@description('Container storing analyst signal documents per run.')
param analystSignalsContainerName string

@description('Container storing decision documents per run.')
param decisionsContainerName string

@description('Container storing immutable portfolio snapshots for automation jobs.')
param portfolioSnapshotsContainerName string

@description('Container storing queue worker results.')
param runResultsContainerName string

@description('Container storing queue worker status summaries.')
param runStatusContainerName string

@description('Container storing broker order executions.')
param brokerOrdersContainerName string

@description('Container storing market monitor cooldown metadata.')
param monitorCooldownContainerName string

var partitionKeyPartition = {
  kind: 'Hash'
  paths: [
    '/partition_key'
  ]
}

var partitionKeyMessage = {
  kind: 'Hash'
  paths: [
    '/messageId'
  ]
}

var partitionKeyTicker = {
  kind: 'Hash'
  paths: [
    '/ticker'
  ]
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: databaseAccountName
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' existing = {
  name: '${databaseAccountName}/${databaseName}'
}

resource portfolios 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${portfolioContainerName}'
  properties: {
    resource: {
      id: portfolioContainerName
      partitionKey: partitionKeyPartition
      indexingPolicy: {
        indexingMode: 'consistent'
      }
    }
    options: {}
  }
}

resource analystSignals 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${analystSignalsContainerName}'
  properties: {
    resource: {
      id: analystSignalsContainerName
      partitionKey: partitionKeyPartition
      defaultTtl: 2592000
    }
    options: {}
  }
}

resource decisions 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${decisionsContainerName}'
  properties: {
    resource: {
      id: decisionsContainerName
      partitionKey: partitionKeyPartition
      defaultTtl: 2592000
    }
    options: {}
  }
}

resource portfolioSnapshots 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${portfolioSnapshotsContainerName}'
  properties: {
    resource: {
      id: portfolioSnapshotsContainerName
      partitionKey: partitionKeyPartition
    }
    options: {}
  }
}

resource runResults 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${runResultsContainerName}'
  properties: {
    resource: {
      id: runResultsContainerName
      partitionKey: partitionKeyMessage
      defaultTtl: 2592000
    }
    options: {}
  }
}

resource runStatus 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${runStatusContainerName}'
  properties: {
    resource: {
      id: runStatusContainerName
      partitionKey: partitionKeyMessage
      defaultTtl: 2592000
    }
    options: {}
  }
}

resource brokerOrders 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${brokerOrdersContainerName}'
  properties: {
    resource: {
      id: brokerOrdersContainerName
      partitionKey: partitionKeyTicker
    }
    options: {}
  }
}

resource monitorCooldowns 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  name: '${cosmosAccount.name}/${sqlDatabase.name}/${monitorCooldownContainerName}'
  properties: {
    resource: {
      id: monitorCooldownContainerName
      partitionKey: partitionKeyTicker
    }
    options: {}
  }
}
