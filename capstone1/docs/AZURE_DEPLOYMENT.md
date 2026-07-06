# Azure Deployment & Operational Runbook — ProposalForge Pro

Ship the app as a container to Azure, with CI/CD and load testing. The app itself
stays vendor-neutral (open-source RAG stack); Azure is only the hosting target.

## 1. Container image
- `Dockerfile.azure` — production, multi-stage, **non-root**, single exposed port
  **8080**. Inside the container, **nginx** multiplexes the Streamlit UI (`/`) and
  the FastAPI API (`/api`, `/metrics`, `/health`) — App Service only routes one port.
- Local validation:
  ```
  docker build -f Dockerfile.azure -t proposalforge:local .
  docker run -p 8080:8080 -e REQUIRE_AUTH=false proposalforge:local
  # open http://localhost:8080  ·  curl http://localhost:8080/health
  ```

## 2. Deploy to Azure — App Service (recommended)
```
az login
RG=proposalforge-rg APP=proposalforge ./deploy/azure/deploy.sh
```
This provisions (via `deploy/azure/main.bicep`): ACR + Linux App Service Plan
(P1v3) + Web App for Containers, builds/pushes the image with `az acr build`, and
starts the site. Output prints the URL and the generated admin password.

Key App Service settings (set by Bicep): `WEBSITES_PORT=8080`, `httpsOnly`,
`healthCheckPath=/health`, `alwaysOn`, plus app env (auth, RAG backend).

### AKS alternative
```
kubectl apply -f deploy/azure/k8s/     # deployment (2 replicas) + service + ingress
```
Edit the image reference and `config.yaml`/secret first. Add Qdrant/Ollama as
in-cluster services (or managed equivalents).

## 3. CI/CD (GitHub Actions -> Azure)
`.github/workflows/azure.yml` runs on every push:
1. **test** — unit + integration (`pytest`) + coverage. Must pass to proceed.
2. **build-deploy** (main only) — `az acr build` the image, `azure/webapps-deploy`.
3. **load-test** — post-deploy Locust smoke against the live URL; fails on errors.

Required repo secrets: `AZURE_CREDENTIALS` (service principal JSON), `ACR_NAME`,
`AZURE_WEBAPP_NAME`. Create the SP with:
```
az ad sp create-for-rbac --name proposalforge-ci --role contributor \
  --scopes /subscriptions/<SUB>/resourceGroups/proposalforge-rg --sdk-auth
```

## 4. Testing (all pass in the pipeline)
- **Unit + integration:** `pytest tests -q` (60 tests). Integration hits the real
  FastAPI app via TestClient: health, metrics, `/pipeline/run`, webhook + job store.
- **Load:** `tests/load/locustfile.py` (Locust) and `tests/load/k6.js` (k6) with
  thresholds (error rate < 1%, p95 latency). Run locally:
  ```
  locust -f tests/load/locustfile.py --host http://localhost:8001 --headless -u 20 -r 5 -t 60s
  # or
  k6 run tests/load/k6.js --env HOST=http://localhost:8001
  ```
  Baseline (offline, single box): ~20 req/s, 0% errors observed in smoke.

## 5. Operations
### Monitoring
- Health: `GET /health`. App Service health-check pings this.
- Metrics: `GET /metrics` (Prometheus). Scrape from Azure Monitor managed
  Prometheus or a Prometheus sidecar; import the Grafana board in `monitoring/`.
- Logs: `az webapp log tail -g <RG> -n <APP>-app`; structured run logs in `/app/logs`.

### Scaling
- App Service: `az appservice plan update --number-of-workers N` or enable
  autoscale rules on CPU/memory. Use P-series for the embedding model's RAM.
- AKS: `kubectl scale deployment/proposalforge --replicas=N` or an HPA.
- Persisted state (auth/chat/audit/jobs) is SQLite by default — for multi-replica,
  set `DATABASE_URL` to Azure Database for PostgreSQL (pgvector) so replicas share.

### Rollback
- App Service keeps image tags per commit SHA: redeploy a previous tag
  `az webapp config container set ... --docker-custom-image-name <ACR>/proposalforge:<OLD_SHA>`,
  or use a deployment slot swap.
- AKS: `kubectl rollout undo deployment/proposalforge`.

### Incident response
1. Check `/health` and `az webapp log tail`.
2. Check Prometheus alerts (latency, error rate, guardrail spikes) in
   `monitoring/alert_rules.yml`.
3. If a bad release: roll back (above). If capacity: scale out.
4. Data issue: restore SQLite volume / `pg_restore`.

### Secrets & security
- Secrets via App Service settings / Key Vault references — never in the image.
- App runs as non-root; only 8080 exposed; `httpsOnly` on; change the admin and
  Grafana passwords on first boot.

## 6. Acceptance checklist
- [ ] `docker build -f Dockerfile.azure` succeeds; container serves `/health` on 8080.
- [ ] `deploy.sh` provisions Azure and the site is reachable over HTTPS.
- [ ] Push to `main` triggers test -> build -> deploy -> load-test, all green.
- [ ] Unit + integration (60) pass; load smoke under thresholds.
- [ ] This runbook + `DESIGN.md` reviewed by the team.

## 7. Azure-native ops (notifications, observability, CI/CD)

### Observability — Azure Application Insights
- Set `APPLICATIONINSIGHTS_CONNECTION_STRING` (the Bicep provisions an App Insights
  resource and injects it automatically). The tracer then sends every pipeline run
  and each agent as an OpenTelemetry span to Azure Monitor, with attributes
  (`pf.quality_score`, `pf.tokens`, `pf.gate`, `pf.guardrail_hits`, `pf.latency_s`).
- View in Azure Portal → your App Insights → **Transaction search / Application map**.
- The in-app sidebar **🔭 Observability** link points to Application Insights when
  this is set (selection order: Azure → LangSmith → Langfuse → none).
- Install on the image: uncomment `azure-monitor-opentelemetry` in requirements.txt.

### Notifications — Logic App / Teams or Azure Communication Services
- **Webhook (simplest):** set `NOTIFY_WEBHOOK_URL` to an Azure Logic App HTTP
  trigger or a Teams/Slack incoming webhook. On pipeline completion / failure the
  app POSTs a JSON card (title, score, gate, run_id, trace_url).
- **Email:** set `ACS_CONNECTION_STRING`, `ACS_SENDER`, `NOTIFY_EMAIL_TO` to send
  via Azure Communication Services Email (uncomment `azure-communication-email`).
- Alerting on metrics: add an Azure Monitor **alert rule** on App Insights (e.g.
  failed pipelines or p95 latency) → **Action Group** → email/SMS/Logic App.

### CI/CD — Azure DevOps Pipelines
- `azure-pipelines.yml` runs on every commit: **Test** (unit + integration +
  coverage) → **BuildDeploy** (`az acr build` → `AzureWebAppContainer@1`, main
  only) → **LoadTest** (Locust smoke, fails on errors).
- Set pipeline variables: `AZURE_SUBSCRIPTION` (service connection), `ACR_NAME`,
  `AZURE_WEBAPP_NAME`, `RESOURCE_GROUP`.
- (A GitHub Actions equivalent, `.github/workflows/azure.yml`, is also included.)
