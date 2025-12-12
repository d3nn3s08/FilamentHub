FROM python:3.12-slim-bookworm

WORKDIR /app

# Build-Tools für ARM installieren
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

ENV FILAMENTHUB_DB_PATH=/app/data/filamenthub.db
ENV PYTHONPATH=/app

RUN mkdir -p /app/data /app/logs && \
    dos2unix /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
