# Project Overview

## Purpose
Real-time ML pipeline for detecting stress in Reddit posts using Vietnamese PhoBERT. The system crawls Reddit posts, processes them through Apache Kafka and Spark, classifies mental health aspects using a multi-label ABSA (Aspect-Based Sentiment Analysis) PhoBERT model, and stores results in Cassandra for visualization.

## Tech Stack
- **Language**: Python 3.8+
- **ML/DL**: PyTorch, Hugging Face Transformers, PhoBERT-base-v2
- **Data Processing**: pandas, numpy, scikit-learn
- **Streaming**: Apache Kafka, Apache Spark (PySpark)
- **Database**: Apache Cassandra
- **Orchestration**: Apache Airflow
- **Visualization**: Grafana, Streamlit
- **Containerization**: Docker, Docker Compose
- **Reddit API**: PRAW (Python Reddit API Wrapper)
- **Labeling**: Ollama (llama3.1:8b)

## Architecture
```
Reddit → Kafka → Spark + Vietnamese PhoBERT → Cassandra → Streamlit/Grafana
```

## Key Features
- Vietnamese-only stress detection
- Multi-label classification (10 mental health characteristics)
- Real-time streaming pipeline
- LDA-derived mental health topics
- Automated data collection from r/vozforums
