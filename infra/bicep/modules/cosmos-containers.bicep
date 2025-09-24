// Cosmos DB containers module

@description('Name of the Cosmos DB account')
param databaseAccountName string

@description('Name of the database')
param databaseName string

@description('Name of the portfolio container')
param portfolioContainerName string

@description('Name of the analyst signals container')
param analystSignalsContainerName string

@description('Name of the decisions container')
param decisionsContainerName string

@description('Name of the portfolio snapshots container')
param portfolioSnapshotsContainerName string

@description('Name of the run results container')
param runResultsContainerName string

@description('Name of the run status container')
param runStatusContainerName string

@description('Name of the broker orders container')
param brokerOrdersContainerName string

@description('Name of the monitor cooldown container')
param monitorCooldownContainerName string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' existing = {
  name: databaseAccountName
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-04-15' existing = {
  parent: cosmosAccount
  name: databaseName
}

resource portfolioContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: portfolioContainerName
  properties: { resource: { id: portfolioContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource analystSignalsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: analystSignalsContainerName
  properties: { resource: { id: analystSignalsContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource decisionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: decisionsContainerName
  properties: { resource: { id: decisionsContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource portfolioSnapshotsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: portfolioSnapshotsContainerName
  properties: { resource: { id: portfolioSnapshotsContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource runResultsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: runResultsContainerName
  properties: { resource: { id: runResultsContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource runStatusContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: runStatusContainerName
  properties: { resource: { id: runStatusContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource brokerOrdersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: brokerOrdersContainerName
  properties: { resource: { id: brokerOrdersContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

resource monitorCooldownContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: monitorCooldownContainerName
  properties: { resource: { id: monitorCooldownContainerName, partitionKey: { paths: ['/id'], kind: 'Hash' } } }
}

output portfolioContainerName string = portfolioContainer.name
output analystSignalsContainerName string = analystSignalsContainer.name
output decisionsContainerName string = decisionsContainer.name
output portfolioSnapshotsContainerName string = portfolioSnapshotsContainer.name
output runResultsContainerName string = runResultsContainer.name
output runStatusContainerName string = runStatusContainer.name
output brokerOrdersContainerName string = brokerOrdersContainer.name
output monitorCooldownContainerName string = monitorCooldownContainer.name
