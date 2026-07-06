#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ProposalForge Pro — one-command Azure deploy (Web App for Containers).
#
# Prereqs (once):
#   - Azure CLI installed:  https://aka.ms/azure-cli
#   - Logged in:            az login
#   - A subscription set:   az account set --subscription "<name-or-id>"
#
# Usage:
#   ./deploy/azure/deploy.sh
#   RG=my-rg APP=my-app LOCATION=centralindia ./deploy/azure/deploy.sh
#
# It provisions (idempotently) an ACR + Linux App Service Plan + Web App,
# builds the image straight from Dockerfile.azure with `az acr build` (no local
# Docker needed), points the Web App at it, and prints the live URL.
# ---------------------------------------------------------------------------
set -euo pipefail

# ---- Config (override via env) --------------------------------------------
RG="${RG:-proposalforge-rg}"
LOCATION="${LOCATION:-centralindia}"
APP="${APP:-proposalforge-$RANDOM}"          # must be globally unique
PLAN="${PLAN:-proposalforge-plan}"
# ACR name: alphanumeric only, globally unique, 5-50 chars.
ACR="${ACR:-pfacr$RANDOM}"
IMAGE="${IMAGE:-proposalforge}"
SKU="${SKU:-B1}"                             # B1 is cheap; use P1v3 for the embedding model
PORT="8080"
# Generate an admin password for first boot unless one is supplied.
ADMIN_PW="${DEFAULT_ADMIN_PASSWORD:-$(openssl rand -base64 15 2>/dev/null || echo change-me-$RANDOM)}"

# ---- Sanity checks ---------------------------------------------------------
command -v az >/dev/null || { echo "ERROR: Azure CLI (az) not found. Install: https://aka.ms/azure-cli"; exit 1; }
az account show >/dev/null 2>&1 || { echo "ERROR: not logged in. Run: az login"; exit 1; }

# Run from the repo root (this script lives in deploy/azure/).
cd "$(dirname "$0")/../.."
test -f Dockerfile.azure || { echo "ERROR: Dockerfile.azure not found in repo root."; exit 1; }

echo ">> Subscription: $(az account show --query name -o tsv)"
echo ">> RG=$RG  LOCATION=$LOCATION  APP=$APP  ACR=$ACR  SKU=$SKU"

# ---- 1. Resource group -----------------------------------------------------
echo ">> [1/6] Resource group..."
az group create -n "$RG" -l "$LOCATION" -o none

# ---- 2. Container registry -------------------------------------------------
echo ">> [2/6] Container registry ($ACR)..."
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true -o none

# ---- 3. Build image in the cloud (no local Docker needed) ------------------
echo ">> [3/6] Building image from Dockerfile.azure (this takes a few minutes)..."
az acr build \
  --registry "$ACR" \
  --image "${IMAGE}:latest" \
  --file Dockerfile.azure . -o none

# ---- 4. App Service plan (Linux) ------------------------------------------
echo ">> [4/6] App Service plan ($SKU)..."
az appservice plan create -n "$PLAN" -g "$RG" --is-linux --sku "$SKU" -o none

# ---- 5. Web App for Containers --------------------------------------------
echo ">> [5/6] Web App ($APP)..."
ACR_SERVER="$(az acr show -n "$ACR" --query loginServer -o tsv)"
ACR_USER="$(az acr credential show -n "$ACR" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)"

az webapp create -g "$RG" -p "$PLAN" -n "$APP" \
  --deployment-container-image-name "${ACR_SERVER}/${IMAGE}:latest" -o none

az webapp config container set -g "$RG" -n "$APP" \
  --docker-custom-image-name "${ACR_SERVER}/${IMAGE}:latest" \
  --docker-registry-server-url "https://${ACR_SERVER}" \
  --docker-registry-server-user "$ACR_USER" \
  --docker-registry-server-password "$ACR_PASS" -o none

# ---- 6. App settings (port, health, env) -----------------------------------
echo ">> [6/6] Configuring app settings..."
az webapp config appsettings set -g "$RG" -n "$APP" --settings \
  WEBSITES_PORT="$PORT" \
  REQUIRE_AUTH="true" \
  DEFAULT_ADMIN_PASSWORD="$ADMIN_PW" \
  VECTOR_BACKEND="tfidf" \
  LANGCHAIN_TRACING_V2="false" -o none

az webapp config set -g "$RG" -n "$APP" \
  --always-on true \
  --generic-configurations '{"healthCheckPath": "/health"}' -o none 2>/dev/null || \
  az webapp update -g "$RG" -n "$APP" --https-only true -o none

az webapp update -g "$RG" -n "$APP" --https-only true -o none

URL="https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
echo ""
echo "============================================================"
echo " Deployed."
echo " URL:            $URL"
echo " Health:         $URL/health"
echo " API docs:       $URL/docs"
echo " Admin password: $ADMIN_PW"
echo "------------------------------------------------------------"
echo " First request may take ~1 min while the container starts."
echo " Tail logs:  az webapp log tail -g $RG -n $APP"
echo " Delete all: az group delete -n $RG --yes --no-wait"
echo "============================================================"
