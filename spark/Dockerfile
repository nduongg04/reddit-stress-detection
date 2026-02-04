# Spark + PhoBERT ONNX inference image
FROM eclipse-temurin:11-jdk

# Install Python and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

# Install Spark
ENV SPARK_VERSION=3.5.0
ENV HADOOP_VERSION=3
ENV SPARK_HOME=/opt/spark

RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz" \
    | tar -xz -C /opt/ \
    && mv /opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} ${SPARK_HOME}

ENV PATH="${SPARK_HOME}/bin:${SPARK_HOME}/sbin:${PATH}"
ENV PYTHONPATH="${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip"

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    pyspark==3.5.0 \
    onnxruntime>=1.17.0 \
    transformers>=4.36.0 \
    cassandra-driver>=3.28.0 \
    numpy \
    requests

# Create directories
RUN mkdir -p /opt/models /opt/spark-apps

# Copy application code
COPY kafka_to_cassandra_with_ml.py /opt/spark-apps/
COPY model_inference.py /opt/spark-apps/

# Copy entrypoint
COPY entrypoint.sh /opt/spark-apps/
RUN chmod +x /opt/spark-apps/entrypoint.sh

WORKDIR /opt/spark-apps

ENTRYPOINT ["/opt/spark-apps/entrypoint.sh"]
