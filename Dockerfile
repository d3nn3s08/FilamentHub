FROM python:3.12-slim-bookworm

WORKDIR /app

# Build-Tools f�r ARM installieren
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

EXPOSE 8085

ENV FILAMENTHUB_DB_PATH=/app/data/filamenthub.db
ENV PYTHONPATH=/app

RUN mkdir -p /app/data /app/logs && \
    sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
