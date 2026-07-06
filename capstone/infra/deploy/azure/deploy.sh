#!/usr/bin/env bash
# Provision the full Azure platform + deploy ProposalForge Pro.
# Prereqs: az CLI logged in (az login).
# Run from the REPO ROOT (paths are infra/-relative):
#   RG=my-rg ALERT_EMAIL=you@co ./infra/deploy/azure/deploy.sh
set -euo pipefail

RG=${RG:-proposalforge-rg}
LOCATION=${LOCATION:-eastus}
APP=${APP:-proposalforge}
ACR=${ACR:-${APP}acr}
IMAGE_TAG=${IMAGE_TAG:-latest}
ADMIN_PW=${ADMIN_PW:-$(openssl rand -base64 18)}
ALERT_EMAIL=${ALERT_EMAIL:-}
NOTIFY_WEBHOOK_URL=${NOTIFY_WEBHOOK_URL:-}

echo "==> Resource group"
az group create -n "$RG" -l "$LOCATION" -o none

CONTAINER_IMAGE="${ACR}.azurecr.io/${APP}:${IMAGE_TAG}"

echo "==> Build & push image to ACR FIRST (Dockerfile.azure) so the Web App can pull it"
# Create the registry up front (idempotent), then build the image into it.
az acr create -g "$RG" -n "$ACR" --sku Basic --admin-enabled true -o none 2>/dev/null || true
az acr build --registry "$ACR" --image "${APP}:${IMAGE_TAG}" -f infra/Dockerfile.azure .

echo "==> Provision platform (App Insights + App Service + Web App for Containers)"
az deployment group create -g "$RG" -f infra/deploy/azure/main.bicep \
  -p appName="$APP" containerImage="$CONTAINER_IMAGE" adminPassword="$ADMIN_PW" \
     notifyWebhookUrl="$NOTIFY_WEBHOOK_URL" \
     pineconeApiKey="${PINECONE_API_KEY:-}" \
     deployAzureOpenAI="${DEPLOY_AOAI:-true}" \
     deployLoadTesting="${DEPLOY_LOADTEST:-true}" -o none

echo "==> Restart web app + worker to pull the new image"
az webapp restart -g "$RG" -n "${APP}-app" -o none
# Worker is optional (only if the bicep provisions a ${APP}-worker site); ignore if absent.
az webapp restart -g "$RG" -n "${APP}-worker" -o none 2>/dev/null || true

URL=$(az webapp show -g "$RG" -n "${APP}-app" --query defaultHostName -o tsv)
echo "==> Live at: https://${URL}"
echo "==> Admin password: ${ADMIN_PW}  (store it securely)"
echo "==> Observability: Application Insights '${APP}-insights' in portal"
echo "==> Queue: Service Bus '${APP}sb' / pipeline-jobs (worker processing)"