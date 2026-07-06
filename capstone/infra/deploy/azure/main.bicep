// Azure infra for ProposalForge Pro:
//   ACR + Linux App Service Plan (+autoscale) + Web App for Containers
//   + Application Insights (observability) + Azure OpenAI (LLM connector)
//   + Azure Load Testing.
@description('Base name for resources')
param appName string = 'proposalforge'
param location string = resourceGroup().location
@description('Container image (e.g. myacr.azurecr.io/proposalforge:latest)')
param containerImage string
@secure()
param adminPassword string
@description('Notification webhook (Logic App / Teams). Optional.')
param notifyWebhookUrl string = ''

// ---- LLM connector: Azure OpenAI ----
@description('Provision Azure OpenAI + a model deployment')
param deployAzureOpenAI bool = true
@description('Model to deploy (must be available in your region)')
param azureOpenAiModel string = 'gpt-4o-mini'
@description('Model version (region-dependent; adjust if deploy fails)')
param azureOpenAiModelVersion string = '2024-07-18'
@description('Deployment (TPM) capacity, in thousands of tokens/min')
param azureOpenAiCapacity int = 20

// ---- Vector DB: Pinecone (optional; falls back to faiss when empty) ----
@secure()
param pineconeApiKey string = ''
param pineconeIndex string = 'proposalforge'

// ---- Load testing ----
param deployLoadTesting bool = true

var acrName = toLower('${appName}acr')
var planName = '${appName}-plan'
var siteName = '${appName}-app'
var aiName = '${appName}-insights'
var aoaiName = toLower('${appName}-aoai')
var loadTestName = '${appName}-loadtest'
var aoaiDeploymentName = azureOpenAiModel

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

// ---------------- Azure OpenAI (LLM connector) ----------------
resource aoai 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployAzureOpenAI) {
  name: aoaiName
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    // Custom subdomain is required for key-based data-plane auth.
    customSubDomainName: aoaiName
    publicNetworkAccess: 'Enabled'
  }
}

resource aoaiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployAzureOpenAI) {
  parent: aoai
  name: aoaiDeploymentName
  sku: { name: 'Standard', capacity: azureOpenAiCapacity }
  properties: {
    model: { format: 'OpenAI', name: azureOpenAiModel, version: azureOpenAiModelVersion }
  }
}

// ---------------- App Service Plan + autoscale ----------------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: { name: 'P1v3', tier: 'PremiumV3' }   // RAM for embeddings; scale as needed
  kind: 'linux'
  properties: { reserved: true }
}

// Scale out on sustained CPU (target RPS is bounded by per-request LLM latency,
// so CPU + instance count is the practical autoscale signal for this workload).
resource autoscale 'Microsoft.Insights/autoscalesettings@2022-10-01' = {
  name: '${appName}-autoscale'
  location: location
  properties: {
    enabled: true
    targetResourceUri: plan.id
    profiles: [
      {
        name: 'cpu-based'
        capacity: { minimum: '1', maximum: '5', default: '2' }
        rules: [
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: plan.id
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT5M'
              timeAggregation: 'Average'
              operator: 'GreaterThan'
              threshold: 70
            }
            scaleAction: { direction: 'Increase', type: 'ChangeCount', value: '1', cooldown: 'PT5M' }
          }
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: plan.id
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT10M'
              timeAggregation: 'Average'
              operator: 'LessThan'
              threshold: 30
            }
            scaleAction: { direction: 'Decrease', type: 'ChangeCount', value: '1', cooldown: 'PT10M' }
          }
        ]
      }
    ]
  }
}

// ---------------- Web App for Containers ----------------
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
      webSocketsEnabled: true   // Streamlit needs WebSockets
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8080' }
        { name: 'WEBSITES_CONTAINER_START_TIME_LIMIT', value: '600' }
        { name: 'REQUIRE_AUTH', value: 'true' }
        { name: 'DEFAULT_ADMIN_PASSWORD', value: adminPassword }
        // Vector DB: 'auto' uses Pinecone when a key is present, else faiss.
        { name: 'VECTOR_BACKEND', value: 'auto' }
        { name: 'PINECONE_API_KEY', value: pineconeApiKey }
        { name: 'PINECONE_INDEX', value: pineconeIndex }
        { name: 'EMBEDDING_MODEL', value: 'BAAI/bge-small-en-v1.5' }
        { name: 'PROMETHEUS_MULTIPROC_DIR', value: '/tmp/pf_metrics' }
        // Observability (production default): Azure Monitor / App Insights tracing.
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        // LLM connector: Azure OpenAI (get_llm_client() picks this up first).
        { name: 'AZURE_OPENAI_ENDPOINT', value: deployAzureOpenAI ? aoai.properties.endpoint : '' }
        { name: 'AZURE_OPENAI_API_KEY', value: deployAzureOpenAI ? aoai.listKeys().key1 : '' }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: deployAzureOpenAI ? aoaiDeploymentName : '' }
        { name: 'AZURE_OPENAI_API_VERSION', value: '2024-06-01' }
        { name: 'NOTIFY_WEBHOOK_URL', value: notifyWebhookUrl }
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://${acr.properties.loginServer}' }
        { name: 'DOCKER_REGISTRY_SERVER_USERNAME', value: acr.listCredentials().username }
        { name: 'DOCKER_REGISTRY_SERVER_PASSWORD', value: acr.listCredentials().passwords[0].value }
      ]
    }
  }
}

// ---------------- Azure Load Testing ----------------
resource loadTest 'Microsoft.LoadTestService/loadTests@2022-12-01' = if (deployLoadTesting) {
  name: loadTestName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: { description: 'Load + latency-threshold tests for ProposalForge Pro' }
}

output acrLoginServer string = acr.properties.loginServer
output siteUrl string = 'https://${site.properties.defaultHostName}'
output appInsightsName string = aiName
output azureOpenAiEndpoint string = deployAzureOpenAI ? aoai.properties.endpoint : ''
output loadTestName string = deployLoadTesting ? loadTestName : ''
