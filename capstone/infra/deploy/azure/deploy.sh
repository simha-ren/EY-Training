#!/usr/bin/env bash
# Provision the full Azure platform + deploy ProposalForge Pro.
# Prereqs: az CLI logged in (az login). Usage: RG=my-rg ALERT_EMAIL=you@co ./deploy.sh
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

echo "==> Provision platform (Monitor + ACR + Service Bus + App Service + worker)"
az deployment group create -g "$RG" -f deploy/azure/main.bicep \
  -p appName="$APP" imageTag="$IMAGE_TAG" adminPassword="$ADMIN_PW" \
     alertEmail="$ALERT_EMAIL" notifyWebhookUrl="$NOTIFY_WEBHOOK_URL" -o none

echo "==> Build & push image to ACR (Dockerfile.azure)"
az acr build --registry "$ACR" --image "${APP}:${IMAGE_TAG}" -f Dockerfile.azure .

echo "==> Restart web app + worker to pull the new image"
az webapp restart -g "$RG" -n "${APP}-app" -o none
az webapp restart -g "$RG" -n "${APP}-worker" -o none

URL=$(az webapp show -g "$RG" -n "${APP}-app" --query defaultHostName -o tsv)
echo "==> Live at: https://${URL}"
echo "==> Admin password: ${ADMIN_PW}  (store it securely)"
echo "==> Observability: Application Insights '${APP}-insights' in portal"
echo "==> Queue: Service Bus '${APP}sb' / pipeline-jobs (worker processing)"