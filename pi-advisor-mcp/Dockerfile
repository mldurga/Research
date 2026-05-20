FROM python:3.11-slim

# System deps: gcc for BM25/numpy compilation, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model at build time so runtime startup is fast.
# Model is cached in the HuggingFace default cache dir inside the image.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"

# Copy source
COPY *.py ./

# Persist directories (mount as volumes in production)
RUN mkdir -p /app/chroma_data /app/graph_data /app/bm25_data

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import asyncio, json; from pi_client import get_client; \
        r = asyncio.run(get_client().test_connection()); \
        exit(0 if r.get('ok') else 1)"

ENV PYTHONUNBUFFERED=1 \
    CHROMA_DATA_DIR=/app/chroma_data \
    KG_PERSIST_PATH=/app/graph_data \
    BM25_PERSIST_PATH=/app/bm25_data

CMD ["python", "pi_mcp_server.py"]
