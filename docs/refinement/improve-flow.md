# Stress Detection Pipeline: Improved Training & Deployment Flow

## Overview

This document describes the complete workflow for training, deploying, and retraining the Vietnamese stress detection model using **theory-based stress aspects** (replacing LDA) and **LLM ensemble labeling** (no manual annotation).

---

## 1. Stress Aspects Definition

### Why Replace LDA?

| LDA (Current) | Theory-Based (New) |
|---------------|-------------------|
| Uncontrollable clustering | Fixed, reproducible categories |
| Overlapping topics | Mutually exclusive aspects |
| Not citable | Backed by psychology research |
| Changes on each run | Stable across experiments |

### 7 Stress Aspects (Psychology-Based)

| ID | Aspect | Academic Source | Detection Keywords (Vietnamese) |
|----|--------|-----------------|--------------------------------|
| 0 | **Occupational** | Job Demand-Control Model (Karasek, 1979) | sếp, deadline, công việc, đồng nghiệp, sa thải, áp lực công việc |
| 1 | **Financial** | Financial Stress Scale (Prawitz et al., 2006) | nợ, tiền, lương, chi tiêu, nghèo, không đủ tiền |
| 2 | **Romantic** | Relationship Assessment Scale (Hendrick, 1988) | người yêu, chia tay, yêu, cô đơn, hẹn hò, tình cảm |
| 3 | **Familial** | Family Stress Model (Conger et al., 1990) | ba mẹ, gia đình, con cái, áp lực gia đình, họ hàng |
| 4 | **Health** | Perceived Stress Scale (Cohen et al., 1983) | bệnh, mất ngủ, mệt mỏi, đau, thuốc, sức khỏe |
| 5 | **Academic** | Academic Stress Inventory (Lin & Chen, 2009) | thi, điểm, trượt, học, luận văn, trường |
| 6 | **Existential** | Purpose in Life Test (Crumbaugh, 1964) | vô nghĩa, tự ti, vô dụng, mục đích, tương lai, bản thân |

### Aspect Definition File

Location: `ml/lda/stress_aspects_v2.json`

```json
{
  "version": "2.0",
  "source": "psychology_literature",
  "aspects": [
    {
      "id": 0,
      "name": "occupational",
      "name_vi": "công_việc",
      "definition": "Stress related to job, career, workplace environment",
      "academic_source": "Job Demand-Control Model (Karasek, 1979)",
      "keywords_vi": ["sếp", "deadline", "công việc", "đồng nghiệp", "sa thải"],
      "examples_positive": [
        "Sếp chửi tôi suốt ngày, stress quá",
        "Deadline dí không kịp thở"
      ],
      "examples_negative": [
        "Hôm nay đi làm vui vẻ",
        "Được tăng lương rồi"
      ]
    }
  ]
}
```

---

## 2. Initial Training Flow

### 2.1 Data Collection

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Collect Raw Posts                                  │
│                                                             │
│  Source A: Existing Cassandra data                         │
│  └── Query: SELECT * FROM raw_posts_by_day                 │
│             WHERE subreddit='vozforums'                    │
│  └── Volume: ~1095 posts                                   │
│                                                             │
│  Source B: Crawl VOZ.vn directly (if more data needed)    │
│  └── Target: voz.vn/f/tam-su.17                           │
│  └── Volume: 3000-5000 posts                              │
│                                                             │
│  Output: raw_posts.csv                                     │
│  Fields: post_id, title, body, author_id, created_date    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 LLM Ensemble Labeling (Free - Ollama Only)

**Models Used:**

| Model | Size | Purpose | Ollama Command |
|-------|------|---------|----------------|
| Llama 3.1 8B | 8B | Primary labeler | `ollama run llama3.1:8b` |
| Qwen2.5 7B | 7B | Secondary labeler | `ollama run qwen2.5:7b` |
| Gemma2 9B | 9B | Third labeler | `ollama run gemma2:9b` |

**Labeling Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: LLM Ensemble Labeling                              │
│                                                             │
│  For each post:                                             │
│                                                             │
│  Post ──┬──→ Llama 3.1:8b ──→ Labels A                     │
│         │                                                   │
│         ├──→ Qwen2.5:7b   ──→ Labels B                     │
│         │                                                   │
│         └──→ Gemma2:9b    ──→ Labels C                     │
│                                                             │
│  Voting Logic:                                              │
│  ├── 3/3 agree  → HIGH confidence (1.0)                   │
│  ├── 2/3 agree  → MEDIUM confidence (0.67) → Use majority │
│  └── All differ → LOW confidence (0.33) → Discard         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Labeling Prompt Template:**

```
You are a mental health expert analyzing Vietnamese social media posts.

POST: "{text}"

Identify ALL stress aspects present (multi-label classification):

0. OCCUPATIONAL - Job, boss, deadline, colleagues, career
1. FINANCIAL - Money, debt, salary, expenses
2. ROMANTIC - Love, breakup, dating, loneliness
3. FAMILIAL - Parents, family, children, relatives
4. HEALTH - Illness, sleep, fatigue, pain
5. ACADEMIC - School, exams, grades, thesis
6. EXISTENTIAL - Self-doubt, meaninglessness, identity

RULES:
- Select ALL applicable aspects
- Only select if clearly mentioned or strongly implied
- Return empty list [] if no stress detected

OUTPUT (JSON only):
{"aspects": [0, 2], "reasoning": "mentions boss (0) and breakup (2)"}
```

### 2.3 Quality Filtering

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Filter by Confidence                               │
│                                                             │
│  Input: 5000 posts with ensemble labels                    │
│                                                             │
│  ├── HIGH confidence (3/3 agree)                          │
│  │   └── ~60% of posts → KEEP for training                │
│  │                                                         │
│  ├── MEDIUM confidence (2/3 agree)                        │
│  │   └── ~30% of posts → KEEP (use majority vote)         │
│  │                                                         │
│  └── LOW confidence (all disagree)                        │
│      └── ~10% of posts → DISCARD                          │
│                                                             │
│  Output: ~4500 high-quality labeled posts                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 Dataset Split

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Create Train/Val/Test Split                        │
│                                                             │
│  Total: 4500 labeled posts                                 │
│                                                             │
│  ├── Train: 3600 posts (80%)                              │
│  ├── Validation: 450 posts (10%)                          │
│  └── Test: 450 posts (10%) ← NEVER retrain on this        │
│                                                             │
│  Stratification: Maintain aspect distribution in each split│
│                                                             │
│  Output files:                                              │
│  ├── ml/dataset/train.csv                                  │
│  ├── ml/dataset/val.csv                                    │
│  └── ml/dataset/test.csv                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.5 Model Training

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Train PhoBERT Model                                │
│                                                             │
│  Base Model: vinai/phobert-base-v2                         │
│  Task: Multi-label classification (7 aspects)              │
│                                                             │
│  Architecture:                                              │
│  ┌─────────────────────────────────────────┐               │
│  │  PhoBERT Encoder                        │               │
│  │  └── [CLS] token (768-dim)             │               │
│  │       ↓                                 │               │
│  │  Dropout (0.3)                          │               │
│  │       ↓                                 │               │
│  │  Dense (768 → 256)                      │               │
│  │       ↓                                 │               │
│  │  ReLU                                   │               │
│  │       ↓                                 │               │
│  │  Dense (256 → 7)                        │               │
│  │       ↓                                 │               │
│  │  Sigmoid (per aspect)                   │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
│  Training Config:                                           │
│  ├── Optimizer: AdamW (lr=2e-5)                           │
│  ├── Batch size: 16                                        │
│  ├── Max sequence: 256 tokens                              │
│  ├── Epochs: 10 (early stopping patience=3)               │
│  └── Loss: Binary Cross-Entropy                            │
│                                                             │
│  Output: ml/models/stress_absa_phobert_v1/                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.6 Evaluation

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Evaluate on Test Set                               │
│                                                             │
│  Metrics:                                                   │
│  ├── Micro-F1: Overall performance                        │
│  ├── Macro-F1: Average across aspects (handles imbalance) │
│  ├── Per-aspect F1: Identify weak aspects                 │
│  └── Exact Match: % of posts with all labels correct      │
│                                                             │
│  Target Performance:                                        │
│  ├── Micro-F1 ≥ 0.75                                      │
│  ├── Macro-F1 ≥ 0.70                                      │
│  └── Exact Match ≥ 0.50                                   │
│                                                             │
│  If targets not met → Collect more data → Retrain         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Deployment Flow

### 3.1 Real-Time Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  PRODUCTION PIPELINE                                        │
│                                                             │
│  VOZ.vn ──→ Kafka ──→ Spark ──→ PhoBERT ──→ Cassandra     │
│             │         │         │           │              │
│             │         │         │           │              │
│         raw posts  batching   inference   predictions      │
│                                                             │
│  Output stored in Cassandra:                               │
│  ├── post_id                                               │
│  ├── text                                                  │
│  ├── aspect_predictions: [0.8, 0.1, 0.6, 0.2, ...]       │
│  ├── stress_label: true/false                             │
│  ├── confidence_score: 0.85                               │
│  ├── model_version: "v1"                                  │
│  └── processed_at: timestamp                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Confidence Scoring

```
┌─────────────────────────────────────────────────────────────┐
│  CONFIDENCE CALCULATION                                     │
│                                                             │
│  For predictions like [0.35, 0.25, 0.40]:                  │
│                                                             │
│  max_prob = 0.40                                           │
│  margin = 0.40 - 0.35 = 0.05                               │
│  entropy = -Σ(p * log(p))                                  │
│                                                             │
│  confidence = 0.4 * max_prob                               │
│             + 0.3 * margin                                 │
│             + 0.3 * (1 - normalized_entropy)               │
│                                                             │
│  Threshold:                                                 │
│  ├── confidence ≥ 0.7 → Trust prediction                  │
│  └── confidence < 0.7 → Flag for retraining pool          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Continuous Retraining Flow

### 4.1 Weekly Retraining Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  AIRFLOW DAG: weekly_retrain                                │
│  Schedule: Every Sunday 2:00 AM                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Task 1: Export New Posts                             │   │
│  │                                                      │   │
│  │ Query Cassandra for posts from last 7 days          │   │
│  │ Filter: Only LOW confidence predictions             │   │
│  │ Output: new_posts_for_labeling.csv                  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Task 2: LLM Ensemble Labeling                       │   │
│  │                                                      │   │
│  │ Run 3 Ollama models on new posts                    │   │
│  │ Apply majority voting                               │   │
│  │ Filter by confidence                                │   │
│  │ Output: new_labeled_posts.csv                       │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Task 3: Merge with Training Pool                    │   │
│  │                                                      │   │
│  │ Add new labeled posts to training set               │   │
│  │ Remove duplicates                                   │   │
│  │ Maintain max pool size (e.g., 10000 posts)         │   │
│  │ Output: updated_train.csv                           │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Task 4: Retrain Model                               │   │
│  │                                                      │   │
│  │ Train PhoBERT on updated dataset                    │   │
│  │ Output: stress_absa_phobert_v{N+1}                  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Task 5: Evaluate & Compare                          │   │
│  │                                                      │   │
│  │ Test new model on held-out test set                 │   │
│  │ Compare with current production model               │   │
│  │                                                      │   │
│  │ IF new_f1 > current_f1:                            │   │
│  │   → Deploy new model                               │   │
│  │   → Update registry                                │   │
│  │ ELSE:                                               │   │
│  │   → Keep current model                             │   │
│  │   → Log metrics for analysis                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Model Registry

```
┌─────────────────────────────────────────────────────────────┐
│  MODEL REGISTRY                                             │
│  Location: /opt/ml/models/registry/registry.json           │
│                                                             │
│  {                                                          │
│    "models": [                                              │
│      {                                                      │
│        "version": "v1",                                    │
│        "created_at": "2024-01-15",                         │
│        "model_dir": "/opt/ml/models/stress_absa_v1",      │
│        "metrics": {"micro_f1": 0.76, "macro_f1": 0.71},   │
│        "active": false                                     │
│      },                                                     │
│      {                                                      │
│        "version": "v2",                                    │
│        "created_at": "2024-01-22",                         │
│        "model_dir": "/opt/ml/models/stress_absa_v2",      │
│        "metrics": {"micro_f1": 0.79, "macro_f1": 0.74},   │
│        "active": true   ← Current production model        │
│      }                                                      │
│    ]                                                        │
│  }                                                          │
│                                                             │
│  Spark loads active model automatically                    │
│  Hot-reload when registry changes                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. File Structure

```
ml/
├── lda/
│   └── stress_aspects_v2.json          # New aspect definitions
│
├── dataset/
│   ├── raw_posts.csv                   # Raw collected posts
│   ├── labeled/
│   │   ├── ensemble_labeled.csv        # LLM ensemble output
│   │   ├── train.csv                   # Training split
│   │   ├── val.csv                     # Validation split
│   │   └── test.csv                    # Test split (frozen)
│   └── retraining_pool/
│       └── low_confidence_posts.csv    # Posts for relabeling
│
├── models/
│   ├── stress_absa_phobert_v1/         # Model version 1
│   ├── stress_absa_phobert_v2/         # Model version 2
│   └── registry/
│       └── registry.json               # Model registry
│
└── scripts/
    ├── label_with_ensemble.py          # LLM ensemble labeling
    ├── train_stress_model.py           # Training script
    ├── evaluate_model.py               # Evaluation script
    └── export_for_retraining.py        # Export low-confidence posts
```

---

## 6. Commands

### Initial Training

```bash
# 1. Export posts from Cassandra
python scripts/export_posts_from_cassandra.py

# 2. Label with LLM ensemble
python ml/scripts/label_with_ensemble.py \
    --input raw_posts.csv \
    --output labeled_posts.csv \
    --models llama3.1:8b,qwen2.5:7b,gemma2:9b

# 3. Split dataset
python ml/scripts/split_dataset.py \
    --input labeled_posts.csv \
    --train-ratio 0.8 \
    --val-ratio 0.1

# 4. Train model
python ml/models/train_stress_model.py \
    --train ml/dataset/train.csv \
    --val ml/dataset/val.csv \
    --output ml/models/stress_absa_phobert_v1

# 5. Evaluate
python ml/models/evaluate_model.py \
    --model ml/models/stress_absa_phobert_v1 \
    --test ml/dataset/test.csv
```

### Start Pipeline

```bash
# Start all services
./run.sh
```

### Trigger Retraining

```bash
# Manual trigger
airflow dags trigger weekly_retrain

# Or run directly
python ml/scripts/retrain_pipeline.py
```

---

## 7. Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Micro-F1 | ≥ 0.75 | TBD |
| Macro-F1 | ≥ 0.70 | TBD |
| Exact Match | ≥ 0.50 | TBD |
| Labeling Agreement (3 LLMs) | ≥ 60% | TBD |
| Weekly New Posts Labeled | 500+ | TBD |

---

## 8. References

1. Karasek, R. A. (1979). Job demands, job decision latitude, and mental strain. *Administrative Science Quarterly*, 24(2), 285-308.
2. Prawitz, A. D., et al. (2006). InCharge Financial Distress/Financial Well-Being Scale. *Journal of Financial Counseling and Planning*, 17(1).
3. Hendrick, S. S. (1988). A generic measure of relationship satisfaction. *Journal of Marriage and the Family*, 93-98.
4. Conger, R. D., et al. (1990). Linking economic hardship to marital quality and instability. *Journal of Marriage and the Family*, 643-656.
5. Cohen, S., et al. (1983). A global measure of perceived stress. *Journal of Health and Social Behavior*, 385-396.
6. Lin, S. H., & Chen, Y. C. (2009). Academic stress scale. *Psychological Reports*, 104(2), 631-636.
7. Crumbaugh, J. C. (1964). An experimental study in existentialism. *Journal of Clinical Psychology*, 20(2), 200-207.
