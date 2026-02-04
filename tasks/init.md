# Vietnamese Stress Detection System

Real-time ML pipeline detecting stress in Voz Vietnamese posts.

## Architecture

```
VOZ.vn → Kafka → Spark + PhoBERT → Cassandra → Streamlit
```

## Project Phases

### Phase 1: Data Collection

- [ ] Set up Kafka cluster
- [ ] Build VOZ crawler/producer
- [ ] Stream posts to Kafka topic
- [ ] Store raw data in Cassandra

### Phase 2: Data Preparation

- [ ] Clean text (remove HTML, normalize Vietnamese)
- [ ] Define 10 stress aspect labels
- [ ] Label dataset with LLM (Qwen)
- [ ] **Validate labels with Claude** (cross-check Qwen labels, resolve conflicts)
- [ ] Balance data: augmentation (40%) + synthetic (60%)
- [ ] Split: train/val/test (80/10/10)

### Phase 3: Model Training

- [ ] Fine-tune PhoBERT-base on labeled data
- [ ] Multi-label classification (10 aspects)
- [ ] Evaluate: F1, precision, recall per aspect
- [ ] **Validate test set with Claude** (sample predictions, error analysis)
- [ ] Export model for Spark inference

### Phase 4: Streaming Pipeline

- [ ] Spark Structured Streaming from Kafka
- [ ] Load PhoBERT model for inference
- [ ] Write predictions to Cassandra
- [ ] Handle backpressure and failures

### Phase 5: Dashboard

- [ ] Streamlit app connecting to Cassandra
- [ ] Real-time stress trend charts
- [ ] Aspect distribution visualization
- [ ] Post search and filtering

## ML Approach

**Model**: PhoBERT-base (`vinai/phobert-base`) - Vietnamese BERT pre-trained on 20GB Vietnamese text

**10 Stress Aspects**:

- Work stress, Financial anxiety, Relationship issues, Academic pressure, Exhaustion
- Depression, Loneliness, Health concerns, Family conflict, Future uncertainty

**Data Balancing Strategy** (10k VOZ posts, >80% coverage per aspect):

1. **Augmentation** (40%): Synonym replacement, word swapping
2. **Synthetic Generation** (60%): Qwen-generated posts for gaps

## Quick Start

```bash
docker-compose up -d
```

## Dashboards

- Streamlit: http://localhost:8501
- Kafka UI: http://localhost:8080
