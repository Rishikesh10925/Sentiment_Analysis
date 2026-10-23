# Build context = repository root.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime deps only: no PySpark, no torch/transformers. The API serves the
# CPU TF-IDF + logistic-regression model, so the image stays ~450 MB.
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Application code + the small tracked model/research artifacts the API reads.
COPY backend ./backend
COPY ml ./ml
COPY research ./research
COPY preprocessing ./preprocessing
COPY ingestion ./ingestion
COPY scripts ./scripts
COPY models ./models
COPY results ./results

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p data/raw data/processed \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render sets PORT; locally the default 8000 applies.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=3)"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
