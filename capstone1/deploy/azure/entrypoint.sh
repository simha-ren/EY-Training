#!/usr/bin/env bash
# Launch FastAPI + Streamlit + nginx (front door on 8080), with verbose nginx
# diagnostics so any failure is visible in the container log.
set -uo pipefail
export PYTHONPATH="${PYTHONPATH:-/app}"

mkdir -p /tmp/nginx-client /tmp/nginx-proxy /tmp/nginx-fastcgi \
         /tmp/nginx-uwsgi /tmp/nginx-scgi /app/data /app/logs /app/temp 2>/dev/null || true

echo "=== ENTRYPOINT: starting components ==="
echo "nginx binary: $(command -v nginx || echo 'NOT FOUND')"

# --- FastAPI (internal :8001) ---
python -m uvicorn api_server:app --host 127.0.0.1 --port 8001 --workers "${API_WORKERS:-1}" &
API_PID=$!
echo "uvicorn API started (pid $API_PID)"

# --- Streamlit UI (internal :8501) ---
python -m streamlit run api/app_prod.py \
    --server.port=8501 --server.address=127.0.0.1 --server.headless=true \
    --server.enableCORS=false --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false &
UI_PID=$!
echo "streamlit UI started (pid $UI_PID)"

# --- nginx (public :8080) ---
echo "=== nginx config test ==="
nginx -t 2>&1 || echo ">>> nginx -t FAILED <<<"
echo "=== starting nginx on :8080 ==="
nginx -g 'daemon off;' &
NGINX_PID=$!
sleep 2
if kill -0 "$NGINX_PID" 2>/dev/null; then
    echo "nginx is RUNNING (pid $NGINX_PID) on :8080"
else
    echo ">>> nginx FAILED TO STAY UP  see errors above <<<"
fi

term() { kill "$API_PID" "$UI_PID" "$NGINX_PID" 2>/dev/null || true; wait || true; }
trap term SIGTERM SIGINT

wait -n "$API_PID" "$UI_PID" "$NGINX_PID"
echo ">>> A component exited; shutting down container. <<<" >&2
term
exit 1
