# Custom Airflow Image with ML Dependencies for Retraining Pipeline
FROM apache/airflow:2.7.3

USER root

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install PyTorch first (core ML dependency)
RUN pip install --no-cache-dir torch==2.0.1

# Install Transformers and related packages
RUN pip install --no-cache-dir \
    transformers==4.35.0 \
    tokenizers==0.14.1 \
    safetensors==0.4.0 \
    accelerate==0.26.0 \
    sentencepiece==0.1.99

# Install data processing and ML packages
RUN pip install --no-cache-dir \
    cassandra-driver==3.28.0 \
    scipy==1.11.4 \
    scikit-learn==1.3.2 \
    pandas==2.1.3 \
    numpy==1.24.3 \
    tqdm==4.66.1 \
    requests==2.31.0

# Install visualization packages
RUN pip install --no-cache-dir \
    seaborn==0.12.2 \
    matplotlib==3.7.3

# Note: Ollama will be accessed via HTTP API from ollama service
