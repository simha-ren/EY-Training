FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p data logs temp /tmp/pf_metrics

# Shared Prometheus multiprocess dir so dashboard + API metrics aggregate
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/pf_metrics

# Expose ports
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health').read()"

# Run both Streamlit and FastAPI (clear stale multiprocess metric files first)
CMD ["sh", "-c", "rm -f $PROMETHEUS_MULTIPROC_DIR/* 2>/dev/null; streamlit run app_prod.py --server.port=8000 --server.address=0.0.0.0 & uvicorn api_server:app --host 0.0.0.0 --port 8001"]
