FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Pre-download embedding model during build (configurable via build-arg)
ARG EMBEDDING_MODEL=azure
RUN if [ "$EMBEDDING_MODEL" != "azure" ] && [ "${EMBEDDING_MODEL#azure}" = "$EMBEDDING_MODEL" ]; then \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" || true; \
    fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
