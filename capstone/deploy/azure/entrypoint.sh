#!/usr/bin/env bash
# Launch the FastAPI API, the Streamlit UI, and nginx (front door on 8080).
# If any of the three exits, take the whole container down so Azure restarts it.
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-/app}"
mkdir -p /tmp/nginx-client /app/data /app/logs /app/temp

# --- FastAPI (internal :8001) -----------------------------------------------
python -m uvicorn api_server:app \
    --host 127.0.0.1 --port 8001 --workers "${API_WORKERS:-1}" &
API_PID=$!

# --- Streamlit UI (internal :8501) ------------------------------------------
python -m streamlit run api/app_prod.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false &
UI_PID=$!

# --- nginx (public :8080) ---------------------------------------------------
nginx -g 'daemon off;' &
NGINX_PID=$!

# If any process dies, stop the others and exit non-zero.
term() {
    kill "$API_PID" "$UI_PID" "$NGINX_PID" 2>/dev/null || true
    wait || true
}
trap term SIGTERM SIGINT

# Wait on all; -n returns when the first one exits.
wait -n "$API_PID" "$UI_PID" "$NGINX_PID"
echo "A component exited; shutting down container." >&2
term
exit 1
