# Real-time Vietnamese Stress Detection from Social Media

## Demo Video

<video src="https://github.com/nduongg04/reddit-stress-detection/raw/main/demo/Screen%20Recording%202026-02-05%20at%2000.22.48.mov" controls width="100%"></video>

## Abstract

A real-time machine learning pipeline detecting stress indicators in Vietnamese social media posts from VOZ.vn forum. The system classifies posts into 10 stress aspects using PhoBERT fine-tuned on 10k labeled Vietnamese posts, achieving **F1 macro > 0.70** with automated retraining via Airflow.

## System Architecture

```
┌─────────┐    ┌─────────┐    ┌───────────────┐    ┌───────────┐    ┌───────────┐
│ VOZ.vn  │───►│  Kafka  │───►│ Spark + ONNX  │───►│ Cassandra │───►│ Streamlit │
│ Crawler │    │  Queue  │    │   PhoBERT     │    │    DB     │    │ Dashboard │
└─────────┘    └─────────┘    └───────────────┘    └───────────┘    └───────────┘
                                     ▲
                                     │
                              ┌──────┴──────┐
                              │   Airflow   │
                              │  Retraining │
                              └─────────────┘
```

## Methodology

### Data Collection

- Source: VOZ.vn "Tâm Sự" (Confession) forum
- Volume: 10,000+ Vietnamese posts
- Filter: Stress-related keywords in Vietnamese

### Labeling Pipeline

| Step | Tool         | Purpose                             |
| ---- | ------------ | ----------------------------------- |
| 1    | Qwen 2.5:7B  | Initial multi-label classification  |
| 2    | Claude API   | 20% sample validation (Kappa > 0.7) |
| 3    | Human Review | Conflict resolution                 |

### 10 Stress Aspects

| ID  | Aspect              | Vietnamese         |
| --- | ------------------- | ------------------ |
| 0   | Work Stress         | Áp lực công việc   |
| 1   | Financial Anxiety   | Lo âu tài chính    |
| 2   | Relationship Issues | Vấn đề tình cảm    |
| 3   | Academic Pressure   | Áp lực học tập     |
| 4   | Exhaustion          | Kiệt sức           |
| 5   | Depression          | Trầm cảm           |
| 6   | Loneliness          | Cô đơn             |
| 7   | Health Concerns     | Lo lắng sức khỏe   |
| 8   | Family Conflict     | Mâu thuẫn gia đình |
| 9   | Future Uncertainty  | Bất an tương lai   |

### Model

- **Base**: `vinai/phobert-base` (Vietnamese BERT, 20GB pretraining)
- **Architecture**: PhoBERT + Dropout(0.3) + Linear(768→10) + Sigmoid
- **Training**: BCEWithLogitsLoss, AdamW, 10 epochs, early stopping
- **Export**: ONNX for Spark inference

### Data Balancing

- Augmentation (40%): Synonym replacement, word swapping
- Synthetic (60%): Qwen-generated posts for minority classes
- Target: >80% coverage per aspect

## Results

| Metric    | Score       |
| --------- | ----------- |
| F1 Macro  | 0.72        |
| F1 Micro  | 0.78        |
| Precision | 0.75        |
| Recall    | 0.74        |
| Inference | <100ms/post |

## Tech Stack

| Component     | Technology             |
| ------------- | ---------------------- |
| Crawler       | Python, BeautifulSoup  |
| Queue         | Apache Kafka           |
| Processing    | Apache Spark Streaming |
| ML Model      | PhoBERT → ONNX Runtime |
| Database      | Apache Cassandra       |
| Dashboard     | Streamlit, Plotly      |
| Orchestration | Apache Airflow         |
| Container     | Docker Compose         |

## Quick Start

```bash
# Start all services
docker-compose up -d

# Initialize database schema
./scripts/init-cassandra-schema.sh

# Run crawler (collect 10k posts)
python producers/voz_producer/main.py --target 10000

# Start ML streaming pipeline
./scripts/start_streaming.sh
```

## Dashboards

| Service   | URL                   |
| --------- | --------------------- |
| Streamlit | http://localhost:8501 |
| Kafka UI  | http://localhost:8080 |
| Airflow   | http://localhost:8082 |
| Spark UI  | http://localhost:4040 |

## Continuous Learning

Airflow DAG runs daily at 2 AM:

1. Query low-confidence predictions (< 0.5)
2. Relabel with Qwen3:14B
3. Incremental retraining
4. Hot-swap ONNX model

## Project Structure

```
├── producers/          # VOZ crawler + Kafka producer
├── spark/              # Streaming ML inference
├── ml/                 # PhoBERT training & export
├── streamlit_app/      # Real-time dashboard
├── airflow/            # Retraining DAG
├── cassandra/          # Database schemas
├── data/               # Raw → Cleaned → Labeled → Splits
└── docker-compose.yml  # Full stack deployment
```

## References

- PhoBERT: Nguyen & Nguyen (2020). "PhoBERT: Pre-trained language models for Vietnamese"
- VOZ.vn: Vietnamese online community forum
