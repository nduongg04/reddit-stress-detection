FROM apache/airflow:2.7.3

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install base packages
RUN pip install --no-cache-dir \
    cassandra-driver==3.29.2 \
    requests==2.31.0

# Install PyTorch CPU version
RUN pip install --no-cache-dir torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# Install ML packages
RUN pip install --no-cache-dir \
    transformers==4.36.0 \
    datasets==2.16.0 \
    scikit-learn==1.3.2 \
    onnx==1.15.0 \
    onnxruntime==1.16.3
