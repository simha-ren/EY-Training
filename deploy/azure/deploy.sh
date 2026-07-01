#!/usr/bin/env bash
# One-shot Azure App Service deploy for ProposalForge Pro.
# Prereqs: az CLI logged in (az login). Usage: ./deploy.sh
set -euo pipefail

RG=${RG:-proposalforge-rg}
LOCATION=${LOCATION:-eastus}
APP=${APP:-proposalforge}
ACR=${ACR:-${APP}acr}
IMAGE_TAG=${IMAGE_TAG:-latest}
ADMIN_PW=${ADMIN_PW:-$(openssl rand -base64 18)}

echo "==> Resource group"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> Provision ACR + App Service via Bicep"
az deployment group create -g "$RG" -f deploy/azure/main.bicep \
  -p appName="$APP" containerImage="${ACR}.azurecr.io/${APP}:${IMAGE_TAG}" \
     adminPassword="$ADMIN_PW" -o none

echo "==> Build & push image to ACR (Dockerfile.azure)"
az acr build --registry "$ACR" --image "${APP}:${IMAGE_TAG}" -f Dockerfile.azure .

echo "==> Restart web app to pull new image"
az webapp restart -g "$RG" -n "${APP}-app" -o none

URL=$(az webapp show -g "$RG" -n "${APP}-app" --query defaultHostName -o tsv)
echo "==> Live at: https://${URL}"
echo "==> Admin password: ${ADMIN_PW}  (store it securely)"
