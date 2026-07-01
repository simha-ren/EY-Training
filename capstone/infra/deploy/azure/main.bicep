// Azure infra for ProposalForge Pro: ACR + Linux App Service Plan + Web App for Containers.
@description('Base name for resources')
param appName string = 'proposalforge'
param location string = resourceGroup().location
@description('Container image (e.g. myacr.azurecr.io/proposalforge:latest)')
param containerImage string
@secure()
param adminPassword string
@description('Notification webhook (Logic App / Teams). Optional.')
param notifyWebhookUrl string = ''

var acrName = toLower('${appName}acr')
var planName = '${appName}-plan'
var siteName = '${appName}-app'
var aiName = '${appName}-insights'

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: aiName
  location: location
  kind: 'web'
  properties: { Application_Type: 'web' }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: true }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: { name: 'P1v3', tier: 'PremiumV3' }   // needs RAM for embeddings; scale as needed
  kind: 'linux'
  properties: { reserved: true }
}

resource site 'Microsoft.Web/sites@2023-12-01' = {
  name: siteName
  location: location
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${containerImage}'
      alwaysOn: true
      healthCheckPath: '/health'
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8080' }
        { name: 'WEBSITES_CONTAINER_START_TIME_LIMIT', value: '600' }
        { name: 'REQUIRE_AUTH', value: 'true' }
        { name: 'DEFAULT_ADMIN_PASSWORD', value: adminPassword }
        { name: 'VECTOR_BACKEND', value: 'faiss' }   // or qdrant/pgvector with a managed service
        { name: 'EMBEDDING_MODEL', value: 'BAAI/bge-small-en-v1.5' }
        { name: 'PROMETHEUS_MULTIPROC_DIR', value: '/tmp/pf_metrics' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'NOTIFY_WEBHOOK_URL', value: notifyWebhookUrl }
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://${acr.properties.loginServer}' }
      ]
    }
  }
}

output acrLoginServer string = acr.properties.loginServer
output siteUrl string = 'https://${site.properties.defaultHostName}'
