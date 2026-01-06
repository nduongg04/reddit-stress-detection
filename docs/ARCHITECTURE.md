# Architecture: VOZ Stress Detection Pipeline

## Overview

This document maps the 14-sprint plan to concrete files/folders, identifying what to **CREATE**, **REUSE**, and **REMOVE**.

## Data Flow

```
VOZ.vn Crawler → Cassandra (voz_raw_posts)
                      ↓
              Data Cleaning (Sprint 2)
                      ↓
              LLM Ensemble Labeling (Sprint 4)
                      ↓
              Voting & Confidence (Sprint 5)
                      ↓
              Dataset Splits (Sprint 6)
                      ↓
              PhoBERT Training (Sprint 7)
                      ↓
              Evaluation (Sprint 8)
                      ↓
              Spark Streaming Inference (Sprint 11)
                      ↓
              Cassandra (voz_classified_posts)
                      ↓
              Streamlit Dashboard
```

---

## File/Folder Inventory

### CREATE (New Files)

| Sprint | File/Folder | Purpose | Requirement |
|--------|-------------|---------|-------------|
| 1 | `cassandra/schema/04_voz_raw_posts.cql` | VOZ raw posts table (no TTL) | R3.2 |
| 1 | `scripts/voz_crawler.py` | VOZ.vn crawler with Cassandra storage | R3.1.1 |
| 2 | `scripts/data_cleaning.py` | Token filter + deduplication | R3.4 |
| 2 | `data/cleaned/` | Cleaned dataset output | R3.4 |
| 2 | `reports/cleaning_stats_v1.json` | Cleaning statistics | R6.2 |
| 3 | `config/aspects_v1.json` | 10 stress aspects schema | R2.2 |
| 3 | `config/aspects_v1.sha256` | Schema hash | R2.3 |
| 4 | `scripts/llm_labeling.py` | 3-model ensemble labeling | R4.1 |
| 4 | `config/prompt_v1.txt` | Frozen prompt | R4.2.1 |
| 4 | `config/prompt_v1.sha256` | Prompt hash | R4.2.2 |
| 4 | `logs/invalid_outputs.jsonl` | Invalid LLM outputs | R4.3 |
| 5 | `scripts/voting_aggregation.py` | Per-aspect voting | R5.1 |
| 5 | `data/voted/` | High/medium confidence splits | R5.4 |
| 5 | `reports/agreement_rates_v1.jsonl` | Agreement tracking | R6.1 |
| 6 | `scripts/dataset_splitting.py` | Stratified splits | R8.1 |
| 6 | `data/splits/` | train/val/test splits | R8.1 |
| 6 | `data/gold/gold_v1.csv` | Gold calibration set | R7.1 |
| 6 | `docs/gold_annotation_guidelines.md` | Gold annotation guide | R7.1.3 |
| 7 | `ml/training/train_phobert.py` | Multi-label PhoBERT training | R9.1 |
| 7 | `ml/models/voz_stress_phobert_v1/` | Trained model output | R9.4 |
| 8 | `scripts/evaluate_model.py` | Evaluation metrics | R10.1 |
| 8 | `reports/evaluation_v1.json` | Evaluation report | R10.1 |
| 8 | `reports/error_analysis_v1.json` | FP/FN examples | R10.2 |
| 9 | `scripts/demographic_inference.py` | Gender/occupation inference | R14.3 |
| 9 | `data/enriched/` | Posts with demographics | R14.4 |
| 10 | `scripts/generate_insights.py` | Demographic insights | R15.2 |
| 10 | `reports/insights_*.json` | Insight reports | R15.3 |
| 11 | `cassandra/schema/05_voz_classified_posts.cql` | Classified posts table | R11.1 |
| 11 | `spark/voz_streaming_inference.py` | VOZ real-time inference | R11.1, R18.1 |
| 12 | `scripts/compose_retraining_data.py` | Retraining data composer | R12.2 |
| 12 | `airflow/dags/voz_weekly_retrain.py` | Weekly retrain DAG | R12.1 |
| 13 | `scripts/drift_monitor.py` | Drift detection | R13.1 |
| 13 | `airflow/dags/voz_drift_check.py` | Drift monitoring DAG | R13.2 |
| 13 | `reports/drift_log_v1.jsonl` | Drift logs | R13.2 |
| 14 | `scripts/version_artifacts.py` | Versioning utility | R16.1 |
| 14 | `config/retention_policy.yaml` | Data retention rules | R21 |
| 14 | `docs/model_lineage_v1.md` | Model traceability | R16.2 |

### REUSE (Existing Files - Keep & Modify)

| File/Folder | Current Use | New Use | Modification |
|-------------|-------------|---------|--------------|
| `cassandra/schema/01_keyspace.cql` | reddit_rt keyspace | Same keyspace for VOZ | None |
| `requirements.txt` | Dependencies | Add sentence-transformers | Add dependencies |
| `docker-compose.yml` | Kafka, Cassandra, Spark | Same infrastructure | None |
| `scripts/init-cassandra-schema.sh` | Init Reddit schema | Init VOZ schema | Add VOZ tables |
| `grafana/` | Reddit dashboards | VOZ dashboards | Update queries |
| `streamlit_app/` | ABSA dashboard | VOZ stress dashboard | Update for 10 aspects |

### REMOVE (Deprecated - Comment/Archive)

| File/Folder | Reason | Action |
|-------------|--------|--------|
| `producers/reddit_producer/` | Reddit excluded (R3.1.2) | Comment out in docker-compose |
| `cassandra/schema/02_raw_posts_by_day.cql` | Reddit-specific schema | Keep but don't use |
| `cassandra/schema/03_classified_posts_by_hour.cql` | Reddit-specific schema | Keep but don't use |
| `spark/kafka_to_cassandra*.py` | Reddit flow | Comment, create VOZ version |
| `collect_vozforums_stress.sh` | Old Reddit-based collection | Remove |
| `run_vietnamese_producer.sh` | Reddit producer | Remove |
| `scripts/export_vietnamese_from_cassandra.py` | Reddit export | Replace with VOZ version |
| `scripts/prepare_vozforums_dataset.py` | Old dataset prep | Replace with new pipeline |
| `ml/dataset/label_*.py` | Old labeling scripts | Replace with llm_labeling.py |
| `ml/lda/` | Old LDA approach | Remove (replaced by 10-aspect schema) |
| `ml/models/vietnamese_stress_phobert/` | Old binary model | Archive |
| `ml/models/vietnamese_absa_sentiment_phobert_v1/` | Old ABSA model | Archive |
| `airflow/dags/vietnamese_absa_retrain.py` | Old retrain DAG | Replace with VOZ DAG |
| `data/raw/voz_posts_v1.jsonl` | JSONL backup | Remove (Cassandra only) |

---

## Directory Structure (Final)

```
project/
├── cassandra/
│   └── schema/
│       ├── 01_keyspace.cql              # REUSE
│       ├── 02_raw_posts_by_day.cql      # DEPRECATED (Reddit)
│       ├── 03_classified_posts_by_hour.cql # DEPRECATED (Reddit)
│       ├── 04_voz_raw_posts.cql         # CREATE
│       └── 05_voz_classified_posts.cql  # CREATE (Sprint 11)
│
├── config/
│   ├── aspects_v1.json                  # CREATE (Sprint 3)
│   ├── aspects_v1.sha256                # CREATE
│   ├── prompt_v1.txt                    # CREATE (Sprint 4)
│   ├── prompt_v1.sha256                 # CREATE
│   └── retention_policy.yaml            # CREATE (Sprint 14)
│
├── data/
│   ├── cleaned/                         # CREATE (Sprint 2)
│   │   └── voz_cleaned_v1.jsonl
│   ├── voted/                           # CREATE (Sprint 5)
│   │   ├── high_confidence.jsonl
│   │   └── medium_confidence.jsonl
│   ├── splits/                          # CREATE (Sprint 6)
│   │   ├── train_v1.jsonl
│   │   ├── val_v1.jsonl
│   │   └── test_v1.jsonl
│   ├── gold/                            # CREATE (Sprint 6)
│   │   └── gold_v1.csv
│   └── enriched/                        # CREATE (Sprint 9)
│       └── posts_with_demographics.jsonl
│
├── scripts/
│   ├── voz_crawler.py                   # CREATE (Sprint 1) ✓
│   ├── data_cleaning.py                 # CREATE (Sprint 2)
│   ├── llm_labeling.py                  # CREATE (Sprint 4)
│   ├── voting_aggregation.py            # CREATE (Sprint 5)
│   ├── dataset_splitting.py             # CREATE (Sprint 6)
│   ├── evaluate_model.py                # CREATE (Sprint 8)
│   ├── demographic_inference.py         # CREATE (Sprint 9)
│   ├── generate_insights.py             # CREATE (Sprint 10)
│   ├── compose_retraining_data.py       # CREATE (Sprint 12)
│   ├── drift_monitor.py                 # CREATE (Sprint 13)
│   └── version_artifacts.py             # CREATE (Sprint 14)
│
├── ml/
│   ├── training/
│   │   └── train_phobert.py             # CREATE (Sprint 7)
│   └── models/
│       └── voz_stress_phobert_v1/       # CREATE (Sprint 7)
│           ├── model.pt
│           └── metadata.json
│
├── spark/
│   ├── voz_streaming_inference.py       # CREATE (Sprint 11)
│   └── model_inference.py               # REUSE (update for 10 aspects)
│
├── airflow/
│   └── dags/
│       ├── voz_weekly_retrain.py        # CREATE (Sprint 12)
│       └── voz_drift_check.py           # CREATE (Sprint 13)
│
├── reports/
│   ├── cleaning_stats_v1.json           # CREATE (Sprint 2)
│   ├── agreement_rates_v1.jsonl         # CREATE (Sprint 5)
│   ├── evaluation_v1.json               # CREATE (Sprint 8)
│   ├── error_analysis_v1.json           # CREATE (Sprint 8)
│   ├── insights_gender_v1.json          # CREATE (Sprint 10)
│   ├── insights_occupation_v1.json      # CREATE (Sprint 10)
│   └── drift_log_v1.jsonl               # CREATE (Sprint 13)
│
├── logs/
│   └── invalid_outputs.jsonl            # CREATE (Sprint 4)
│
├── docs/
│   ├── ARCHITECTURE.md                  # CREATE (this file)
│   ├── gold_annotation_guidelines.md    # CREATE (Sprint 6)
│   └── model_lineage_v1.md              # CREATE (Sprint 14)
│
└── openspec/
    └── specs/
        └── voz-stress-pipeline/         # CREATE (spec for this pipeline)
            └── spec.md
```

---

## Cassandra Tables

### Table: `voz_raw_posts` (Sprint 1) ✓

```sql
CREATE TABLE voz_raw_posts (
    post_id text,          -- Partition key (natural deduplication)
    text text,
    timestamp timestamp,   -- Original post time
    crawled_at timestamp,
    source text,           -- 'voz.vn'
    url text,
    PRIMARY KEY (post_id)
) WITH compaction = {'class': 'SizeTieredCompactionStrategy'}
  AND compression = {'class': 'LZ4Compressor'};
-- No TTL - training data is permanent
-- Index on source for filtering by forum
```

### Table: `voz_classified_posts` (Sprint 11)

```sql
CREATE TABLE voz_classified_posts (
    hour_bucket text,      -- '2024-01-15-10'
    post_id text,
    text text,
    aspects list<int>,     -- [0, 3, 5] = Occupational, Familial, Romantic
    aspect_probs map<int, float>,
    confidence float,
    model_version text,
    classified_at timestamp,
    PRIMARY KEY (hour_bucket, classified_at, post_id)
) WITH CLUSTERING ORDER BY (classified_at DESC, post_id ASC)
  AND default_time_to_live = 31536000;  -- 1 year (R21)
```

---

## LLM Models (Ollama)

| Model | Ollama Name | Size | Use |
|-------|-------------|------|-----|
| LLaMA 3.1 8B | `llama3.1:8b` | 4.9 GB | Ensemble member 1 |
| GPT-OSS 20B | `gpt-oss:20b` | 13 GB | Ensemble member 2 |
| Gemma 2 9B | `gemma2:9b` | ~5 GB | Ensemble member 3 |

**Execution:** Sequential (R17.2), one model at a time, batch=8

---

## Sprint Dependencies

```
Sprint 1 (Crawler) ────→ Sprint 2 (Cleaning) ────→ Sprint 4 (Labeling)
                                                        ↓
Sprint 3 (Aspects) ─────────────────────────────→ Sprint 4
                                                        ↓
                                                  Sprint 5 (Voting)
                                                        ↓
                                                  Sprint 6 (Splits)
                                                        ↓
                                                  Sprint 7 (Training)
                                                        ↓
                                                  Sprint 8 (Eval)
                                                   ↓         ↓
                                            Sprint 9    Sprint 11
                                          (Demographics) (Deployment)
                                                ↓              ↓
                                           Sprint 10    Sprint 12
                                           (Insights)   (Retrain)
                                                              ↓
                                                        Sprint 13
                                                         (Drift)
                                                              ↓
                                                        Sprint 14
                                                       (Governance)
```

**Critical Path:** 1 → 2 → 4 → 5 → 6 → 7 → 8 → 11

---

## Progress

### ✓ Sprint 1 COMPLETED
- `scripts/voz_crawler.py` - VOZ.vn crawler with Cassandra storage
- `cassandra/schema/04_voz_raw_posts.cql` - Schema with post_id as partition key
- 12,000+ posts collected from tam-su forum

## Next Steps

1. **Sprint 2 (NOW):** Data Cleaning & Deduplication
   - Token length filter (20-300 tokens)
   - Semantic deduplication (cosine similarity ≥0.90)
2. **Sprint 3 (Parallel):** Create aspect schema JSON
3. Proceed to Sprint 4 (LLM Labeling)
