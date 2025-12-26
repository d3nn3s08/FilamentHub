FROM python:3.12-slim-bookworm

WORKDIR /app

# Build-Tools für ARM installieren + curl für healthcheck
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    python3-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files explicitly
COPY app/ /app/app/
COPY utils/ /app/utils/
COPY services/ /app/services/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY entrypoint.sh /app/
COPY run.py /app/
COPY config.yaml /app/
COPY frontend/ /app/frontend/
COPY .env /app/.env

EXPOSE 8085

ENV FILAMENTHUB_DB_PATH=/app/data/filamenthub.db
ENV PYTHONPATH=/app

RUN mkdir -p /app/data /app/logs /app/app/logging && \
    sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh && \
    python -m compileall /app/app -q || true

ENTRYPOINT ["./entrypoint.sh"]
