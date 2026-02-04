# VOZ Producer - Crawl VOZ.vn and push to Kafka
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY voz_kafka_producer.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create data directory for checkpoints
RUN mkdir -p /app/data/raw

# Environment variables
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ENV KAFKA_TOPIC=voz.posts.raw.v1
ENV TARGET_POSTS=100
ENV DELAY=1.0
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]
