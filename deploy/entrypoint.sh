#!/usr/bin/env bash
set -e
# Clear stale Prometheus multiprocess files
rm -f "${PROMETHEUS_MULTIPROC_DIR:-/tmp/pf_metrics}"/* 2>/dev/null || true

# FastAPI (API + webhook + /metrics) on 8001
uvicorn api_server:app --host 127.0.0.1 --port 8001 &
# Streamlit UI on 8000
streamlit run app_prod.py --server.port=8000 --server.address=127.0.0.1 \
  --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false &
# nginx in the foreground multiplexes both on 8080 (the Azure port)
nginx -g 'daemon off;'
