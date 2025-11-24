# Vietnamese Stress Detection - Implementation Status

**Architecture**: Reddit → Kafka → Spark + PhoBERT → Cassandra → Grafana

## ✅ COMPLETED IMPLEMENTATION

### Phase 1: Data Collection ✓

- **Collected**: 1,095 Vietnamese stress posts from r/vozforums
- **Storage**: Cassandra `reddit_rt.raw_posts_by_day` (subreddit='vozforums')
- **Date range**: 2024-12-22 to 2025-11-23

### Phase 2: ABSA Topic Extraction ✓

- **Method**: LDA topic modeling on 1,095 vozforums posts
- **Output**: 10 Vietnamese mental health aspects (ABSA)
- **File**: `ml/lda/absa_mental_health_aspects.json`
- **Script**: `ml/lda/extract_topics.py`

**10 ABSA Aspects:**

1. công_việc (work stress) - 217 posts
2. giấc_ngủ_thuốc (sleep/medication) - 28 posts
3. giao_tiếp (communication) - 300 posts
4. thiếu_năng_lượng (low energy) - 251 posts
5. căng_thẳng_tài_chính (financial stress) - 304 posts
6. tình_yêu (relationships) - 239 posts
7. tự_suy_ngẫm (self-reflection) - 682 posts
8. trầm_cảm (depression) - 322 posts
9. gia_đình (family) - 187 posts
10. tìm*kiếm_giúp*đỡ (help-seeking) - 273 posts

### Phase 3: Dataset Labeling ✓

- **Method**: Ollama LLM (llama3.1:8b) automatic labeling
- **Labeled**: 1,095 posts with multi-label ABSA annotations
- **Output**: `ml/dataset/labeled/vozforums_absa_labeled.csv`
- **Script**: `ml/dataset/label_with_ollama_absa.py`
- **Statistics**:
  - 981 posts (89.6%) with at least one aspect
  - Average 2.56 aspects per post
  - Most common: tự_suy_ngẫm (62.3%), trầm_cảm (29.4%)

### Phase 4: Sentiment Validation ✓

- **Method**: Multi-process Ollama sentiment classification (llama3.2:1b)
- **Script**: `ml/dataset/validate_sentiment_parallel.py`
- **Sentiment Scale**: -1 (negative), 0 (neutral), 1 (positive)
- **Output**: `ml/dataset/labeled/vozforums_absa_sentiment.csv`
- **Speed**: 4 parallel workers, ~4 minutes for 1,095 posts
- **Status**: ✅ Complete
- **Statistics**:
  - 2,285 aspect-sentiment pairs labeled
  - Most common: tự_suy_ngẫm (649 sentiments), trầm_cảm (314 sentiments)

### Phase 5: Model Training (IN PROGRESS)

- **Task**: Multi-label ABSA sentiment classification
- **Model**: PhoBERT-base-v2 (vinai/phobert-base-v2)
- **Architecture**: 135M parameters, 10 sentiment classifiers (negative/neutral/positive)
- **Script**: `ml/models/train_absa_phobert.py`
- **Data**: `vozforums_absa_sentiment.csv` (1,095 posts with sentiments)
- **Loss**: Binary cross-entropy (normalized sentiments [0, 1])
- **Metrics**: F1-micro, F1-macro, F1-samples, Hamming loss
- **Status**: 🔄 Training started
- **Output**: `ml/models/vietnamese_absa_sentiment_phobert_v1/`

### Phase 6: Active Learning & Retraining ✓

- **Schedule**: Daily at 2 AM UTC via Airflow
- **DAG**: `airflow/dags/vietnamese_absa_retrain.py`
- **Pipeline**:
  1. Fetch real-time posts from Cassandra (last 24h)
  2. Run PhoBERT inference
  3. Calculate prediction uncertainty (entropy-based)
  4. Select top-100 uncertain predictions
  5. Validate with Ollama (automatic, no human needed)
  6. Combine with existing training data
  7. Retrain PhoBERT model
  8. Save versioned model to registry
  9. Send metrics to monitoring

### Phase 7: Model Versioning & Deployment ✓

- **Registry**: `ml/models/registry/registry.json`
- **Inference Module**: `spark/model_inference_absa.py`
- **Features**:
  - Automatic model versioning with timestamps
  - Hot-reload without downtime
  - Graceful fallback to default model
  - Multi-label ABSA predictions with sentiments
- **Integration**: Spark streaming with Cassandra

### Phase 8: Active Learning Validation ✓

- **Validator**: `utils/ollama_validator.py`
- **Features**:
  - Entropy-based uncertainty calculation
  - Top-N uncertain sample selection
  - Ollama-powered validation
  - Correction tracking and confidence scoring
- **Usage**: Integrated in Airflow retraining pipeline

---

## 📂 FILE STRUCTURE

### ✅ ACTIVE FILES (Keep)

#### ML Pipeline

```
ml/
├── dataset/
│   ├── labeled/
│   │   ├── vozforums_absa_labeled.csv          # ✅ 1,095 ABSA-labeled posts
│   │   ├── sentiment_validation.log            # ✅ Validation progress log
│   │   └── labeling.log                        # ✅ Labeling progress log
│   ├── active_learning/                        # ✅ Active learning validated data
│   ├── label_with_ollama_absa.py               # ✅ ABSA labeling script
│   └── validate_sentiment_fast.py              # ✅ Fast sentiment validation
│   └── validate_sentiment_ultra_fast.py        # ✅ Ultra-Fast sentiment validation
├── lda/
│   ├── absa_mental_health_aspects.json         # ✅ 10 Vietnamese ABSA aspects
│   ├── extract_topics.py                       # ✅ LDA topic extraction
│   └── interpret_absa_aspects.py               # ✅ Aspect interpretation
└── models/
    ├── train_absa_phobert.py                   # ✅ Multi-label PhoBERT training
    ├── vietnamese_stress_phobert/              # ✅ Binary PhoBERT (keep for fallback)
    ├── vietnamese_augmentation.py              # ✅ Vietnamese text augmentation
    ├── test_vietnamese_model.py                # ✅ Model testing
    └── registry/v1/metadata.json               # ✅ Model registry
```

#### Streaming & Inference

```
spark/
├── kafka_to_cassandra.py                       # Spark streaming (basic)
├── model_inference.py                          # Binary stress inference (old)
└── model_inference_absa.py                     # ABSA inference with versioning
```

#### Orchestration

```
airflow/dags/
└── vietnamese_absa_retrain.py                  # Daily retraining DAG
```

#### Utilities

```
utils/
└── ollama_validator.py                         # Active learning validator
```

#### Scripts

```
scripts/
├── export_vietnamese_from_cassandra.py         # Export posts from Cassandra
└── prepare_vozforums_dataset.py                # Dataset preparation
```

---

### 🗑️ DEPRECATED FILES (Can Remove)
$$
#### Old English/Binary Models

```
ml/models/
├── reddit_stress_v4/                           # Old English DistilBERT
├── checkpoints/                                # Old training checkpoints
├── train.py                                    # Old binary training
├── augmentation.py                             # Old English augmentation
├── data_loader.py                              # Old data loader
├── evaluate.py                                 # Old evaluation
└── focal_loss.py                               # Unused loss function
```

#### Old Datasets

```
ml/dataset/
├── raw/
│   ├── reddit_crawl_20251019_003127.csv       # Old English data
│   └── vietnamese_posts.csv                    # Superseded by Cassandra
├── labeled/
│   ├── reddit_crawl_ollama_labeled.csv        # Old English labels
│   ├── vietnamese_ollama_labeled.csv          # Old binary labels
│   └── vietnamese_labeling_checkpoint.json    # Old checkpoint
├── splits/                                     # Old train/val/test splits
│   ├── train_v2.csv
│   ├── val_v2.csv
│   ├── test_v2.csv
│   ├── train_vietnamese.csv
│   ├── val_vietnamese.csv
│   └── test_vietnamese.csv
├── create_splits_from_ollama.py               # Old split creation
├── create_vietnamese_splits.py                # Old Vietnamese splits
├── label_vietnamese_with_ollama.py            # Old binary labeling
└── review_low_confidence.py                   # Manual review (replaced by auto)
```

#### Old LDA Files

```
ml/lda/
├── mental_health_topics.json                   # Old binary topics
├── mental_health_aspects.json                  # Old aspects (not ABSA)
└── extract_from_kafka.py                       # Unused Kafka extraction
```

#### Old Airflow DAGs

```
airflow/dags/
├── dag_template.py                             # Template only
├── health_check_dag.py                         # Testing only
└── sample_dag.py                               # Testing only
```

---

## 🔄 CURRENT WORKFLOW

### Training Pipeline

```
Cassandra (1095 posts)
    ↓
LDA Topic Extraction → 10 ABSA aspects
    ↓
Ollama Labeling → Multi-label annotations
    ↓
Ollama Sentiment → -1/0/1 per aspect
    ↓
PhoBERT Training → Multi-label classifier
    ↓
Model Registry → Versioned models
```

### Production Pipeline

```
Reddit API
    ↓
Kafka (reddit.posts.raw.v1)
    ↓
Spark Streaming + PhoBERT ABSA
    ↓
Cassandra (classified_posts_by_hour)
    ↓
Grafana Dashboards
```

### Retraining Pipeline (Daily)

```
Cassandra (last 24h posts)
    ↓
PhoBERT Inference → Predictions
    ↓
Uncertainty Calculation → Top-100 uncertain
    ↓
Ollama Validation → Corrected labels
    ↓
Combine with existing data
    ↓
Retrain PhoBERT → New version
    ↓
Update Registry → Deploy automatically
```

---

## 📊 CURRENT STATUS

| Phase                | Status      | Progress               |
| -------------------- | ----------- | ---------------------- |
| Data Collection      | ✅ Complete | 1,095 posts            |
| ABSA Extraction      | ✅ Complete | 10 aspects             |
| ABSA Labeling        | ✅ Complete | 1,095 labeled          |
| Sentiment Validation | 🔄 Running  | ~6 mins remaining      |
| Model Training       | ⏳ Ready    | Pending sentiment data |
| Airflow Pipeline     | ✅ Complete | Ready for deployment   |
| Model Versioning     | ✅ Complete | With hot-reload        |
| Active Learning      | ✅ Complete | Ollama validator       |

---

## 🎯 NEXT STEPS

1. **Wait for sentiment validation** (~6 mins)
2. **Train PhoBERT ABSA model** with sentiment data
3. **Test model accuracy** on Vietnamese posts
4. **Deploy to Spark streaming** (update `spark/kafka_to_cassandra.py`)
5. **Activate Airflow DAG** for daily retraining
6. **Monitor in Grafana** for real-time metrics

---

## 🧹 CLEANUP COMMANDS

```bash
# Remove old English models
rm -rf ml/models/reddit_stress_v4
rm -rf ml/models/checkpoints

# Remove old datasets
rm -rf ml/dataset/raw
rm -rf ml/dataset/splits
rm ml/dataset/labeled/reddit_crawl_ollama_labeled.csv
rm ml/dataset/labeled/vietnamese_ollama_labeled.csv
rm ml/dataset/labeled/vietnamese_labeling_checkpoint.json

# Remove old scripts
rm ml/dataset/create_splits_from_ollama.py
rm ml/dataset/create_vietnamese_splits.py
rm ml/dataset/label_vietnamese_with_ollama.py
rm ml/dataset/review_low_confidence.py

# Remove old training files
rm ml/models/train.py
rm ml/models/augmentation.py
rm ml/models/data_loader.py
rm ml/models/evaluate.py
rm ml/models/focal_loss.py

# Remove old LDA files
rm ml/lda/mental_health_topics.json
rm ml/lda/mental_health_aspects.json
rm ml/lda/extract_from_kafka.py

# Remove test DAGs
rm airflow/dags/dag_template.py
rm airflow/dags/health_check_dag.py
rm airflow/dags/sample_dag.py
```

**Estimated space saved**: ~50-100 MB

---

**Last Updated**: 2025-11-24
**Model Version**: Vietnamese ABSA PhoBERT v1
**Total Implementation Time**: ~8 hours
