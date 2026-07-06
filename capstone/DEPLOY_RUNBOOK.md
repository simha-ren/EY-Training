# Deploy Runbook — ProposalForge Pro

This repo is wired to build a container, run tests, push to Azure Container Registry
(ACR), and deploy to **Azure Web App for Containers** via GitHub Actions. Two ways to
ship:

- **A. GitHub Actions (CI/CD)** — push to `main`, the pipeline does the rest.
- **B. One-shot script** — `infra/deploy/azure/deploy.sh` from your machine.

> Heads-up: nobody but you can run *your* pipeline or push to *your* Azure — the
> workflow runs in **your** GitHub repo using **your** secrets. The steps below make
> that turnkey.

---

## 0. Prerequisites
- Azure subscription + `az` CLI logged in (`az login`).
- A GitHub repo containing this code.
- An LLM key for live answers (recommended: a free **Groq** key). Without one the app
  still runs in offline-extractive mode.

## 1. Create Azure resources you need names for
You can let `deploy.sh` create everything, or pre-create an ACR + resource group.
You will need three values for GitHub secrets: a service-principal JSON, the ACR name,
and the Web App name.

```bash
# Resource group
az group create -n proposalforge-rg -l eastus

# Service principal scoped to the resource group (this whole JSON becomes a secret)
az ad sp create-for-rbac \
  --name proposalforge-ci \
  --role contributor \
  --scopes /subscriptions/<SUB_ID>/resourceGroups/proposalforge-rg \
  --sdk-auth
```

## 2. Add GitHub secrets (Settings → Secrets and variables → Actions)
| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | the **entire** JSON from `az ad sp create-for-rbac --sdk-auth` |
| `ACR_NAME` | your registry name only, e.g. `proposalforgeacr` (no `.azurecr.io`) |
| `AZURE_WEBAPP_NAME` | your Web App name, e.g. `proposalforge-web` |

Also create a GitHub **Environment** named `production` (Settings → Environments) —
the deploy job targets it.

## 3. Provision the platform (first time only)
Run from the **repo root** (paths are `infra/`-relative):
```bash
RG=proposalforge-rg ALERT_EMAIL=you@example.com ./infra/deploy/azure/deploy.sh
```
This builds the image into ACR **first**, then provisions the Web App with the registry
credentials wired in so it can pull the private image.

## 4. ⚠️ Enable WebSockets (required for Streamlit)
Azure Web Apps disable WebSockets by default. Streamlit needs them, or the UI loads
blank / keeps reconnecting. Run once after the Web App exists:
```bash
az webapp config set -g proposalforge-rg -n <AZURE_WEBAPP_NAME> --web-sockets-enabled true
```

## 5. Configure app settings (LLM key + port)
```bash
az webapp config appsettings set -g proposalforge-rg -n <AZURE_WEBAPP_NAME> --settings \
  WEBSITES_PORT=8080 \
  GROQ_API_KEY=<your_groq_key> \
  GROQ_MODEL=llama-3.3-70b-versatile
# (or CLAUDE_API_KEY=<...> to use Claude instead)
```

## 6. Ship via CI/CD
Push to `main`. `.github/workflows/azure.yml` will:
1. **test** — `pytest tests` (gate),
2. **build-deploy** — `az acr build -f infra/Dockerfile.azure .` then
   `azure/webapps-deploy` with the image tagged `${{ github.sha }}`,
3. **load-test** — Locust against the live host.

Watch it under the repo's **Actions** tab.

## 7. Verify
```bash
curl https://<AZURE_WEBAPP_NAME>.azurewebsites.net/health      # -> ok
open  https://<AZURE_WEBAPP_NAME>.azurewebsites.net/           # Streamlit UI
```

---

## Notes & gotchas
- **LLM connector = Azure OpenAI, provisioned automatically.** The Bicep creates an
  Azure OpenAI resource and a model deployment (`gpt-4o-mini` by default) and injects
  `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_DEPLOYMENT` into the
  Web App, so `get_llm_client()` uses it first. Two caveats: (1) your subscription must
  have Azure OpenAI access enabled; (2) model + version availability is **region-
  specific** — if the deployment fails, change `azureOpenAiModel` / `azureOpenAiModelVersion`
  (or set `DEPLOY_AOAI=false ./infra/deploy/azure/deploy.sh` to skip it and fall back to
  Groq/Claude via app settings).
- **Pinecone** is optional. Provide the key at deploy time so it's stored as an app
  setting: `PINECONE_API_KEY=<key> ./infra/deploy/azure/deploy.sh`. With no key the app
  uses faiss/tf-idf automatically (`VECTOR_BACKEND=auto`). Create the index (dimension
  matching your embedding model) in the Pinecone console first.
- **Autoscale** is on by default (1→5 instances on CPU). Adjust min/max/threshold in
  `infra/deploy/azure/main.bicep` (`autoscale` resource).
- **Load + latency gates.** The post-deploy `load-test` job enforces `/health` p95 <
  50 ms, `/api/v1/retrieve` p95 < 50 ms, and end-to-end p95 < 5 s, and fails the pipeline
  if breached. `<5 ms` is not achievable for LLM calls — the 50 ms budgets are for the
  health and retrieval-only paths. For cloud-scale runs, use the provisioned Azure Load
  Testing resource with `tests/load/loadtest.yaml` (uncomment the `azure-load-test` job).
- **End-to-end evaluation gates deploy.** `eval/eval_realdoc.py` ingests a real document
  and checks grounded answers; `eval.evaluate` scores the golden set. Both run before
  build/deploy.
- **Observability is Azure Monitor in production, automatically.** The Bicep template
  provisions an Application Insights resource and injects
  `APPLICATIONINSIGHTS_CONNECTION_STRING` into the Web App, so pipeline traces and
  request telemetry flow to Azure Monitor with no extra setup. After deploy, view them
  in the portal: **Application Insights → Transaction search / Application map**. You do
  not need the LangSmith keys in production; they're an opt-in dev tool. Prometheus +
  Grafana (`infra/docker-compose.yml`) are for local metrics only — if you want Grafana
  dashboards in Azure too, add Azure Managed Prometheus/Grafana and scrape the
  container's `/metrics` (optional; not required for the app to be observable).
- **Test job needs a key or a skip.** `tests/test_live_groq.py` calls a live endpoint.
  If it runs without a key it can fail and block the deploy. Either add a `GROQ_API_KEY`
  **repo secret** and expose it to the test job, or mark those tests to skip when no key
  is present (e.g. `pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), ...)`). Pure unit
  tests need no key.
- **First boot is slow.** The image is large (faiss, sklearn, azure SDKs, opentelemetry).
  The health check has a 40s start period; give the first cold start a couple of minutes.
- **Local smoke test before pushing** (fastest way to catch a bad build):
  ```bash
  docker build -f infra/Dockerfile.azure -t proposalforge:local .
  docker run -p 8080:8080 -e GROQ_API_KEY=<key> proposalforge:local
  curl localhost:8080/health
  ```
- **Reconstructed files.** `src/agents/groq_llm.py`, `src/orchestrator/router.py`, and
  `worker.py` were rebuilt from a partially corrupt backup (see `docs/decisions.md`).
  They compile, import, and pass an end-to-end run here — but confirm behavior against
  your original repo if you have it.
