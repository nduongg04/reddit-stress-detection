# Sprint Plan: Stress Detection Pipeline (Consolidated)

## Sprint 1: Data Collection Infrastructure ✓ COMPLETED

### Goal
Set up VOZ.vn crawler and collect 12,000 raw posts.

### Tasks

| ID | Task | Requirement | Status |
|----|------|-------------|--------|
| 1.1 | Build VOZ.vn crawler for `voz.vn/f/tam-su.17` | R3.1.1 | ✓ |
| 1.2 | Implement pagination (newest first) | R3.1.4 | ✓ |
| 1.3 | Extract: post_id, text, timestamp, source | R3.2.1 | ✓ |
| 1.4 | Store raw posts to Cassandra (voz_raw_posts table) | R3.2 | ✓ |
| 1.5 | Add progress logging and resume capability | R16.1 | ✓ |
| 1.6 | Keyword-based stress filtering (relaxed) | - | ✓ |

### Acceptance Criteria

- [x] Crawler runs without errors for 2+ hours
- [x] ≥12,000 posts collected from VOZ tam-su forum
- [x] Each post has: `post_id`, `text`, `timestamp`, `source`, `url`
- [x] Duplicate URLs are skipped during crawl (natural dedup via post_id PK)
- [x] Crawler can resume from last checkpoint

### Deliverables

- `scripts/voz_crawler.py` ✓
- `cassandra/schema/04_voz_raw_posts.cql` ✓
- Posts stored in Cassandra `voz_raw_posts` table

---

## Sprint 2: Data Cleaning + Aspect Schema

**Combines:** Data Cleaning & Deduplication + Stress Aspect Schema (can run in parallel)

### Input
- **Raw data source:** Cassandra table `reddit_rt.voz_raw_posts`
- **Query:** `SELECT post_id, text, timestamp, source, url FROM voz_raw_posts`
- **Expected records:** ~12,000 posts from Sprint 1

### Goal
Clean/deduplicate posts AND create versioned aspect definitions.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| **Data Cleaning** | | |
| 2.1 | Implement token length filter (20-300 tokens using underthesea tokenizer) | R3.2.2 |
| 2.2 | Load MiniLM embedding model (`paraphrase-multilingual-MiniLM-L12-v2`) | R3.4.1 |
| 2.3 | Compute pairwise cosine similarity using faiss for efficiency | R3.4.1 |
| 2.4 | Remove duplicates (cosine similarity ≥0.90, keep post with earliest timestamp) | R3.4.1 |
| 2.5 | Generate cleaning statistics JSON report | R6.2 |
| **Aspect Schema** | | |
| 2.6 | Define 10 stress aspects: Occupational, Financial, Romantic, Familial, Health, Academic, Existential, Social, Life_Events, Self_Image | R2.2 |
| 2.7 | Add 3+ inclusion rules and 2+ exclusion rules per aspect | R2.2.2 |
| 2.8 | Add 10+ Vietnamese keywords per aspect | R2.2.2 |
| 2.9 | Add 3 positive examples and 3 negative examples per aspect | R2.2.2 |
| 2.10 | Version file as `aspects_v1.json`, compute SHA-256 hash | R2.3 |

### Acceptance Criteria

**Data Cleaning:**
- [ ] Posts with <20 or >300 tokens (underthesea tokenizer) are removed
- [ ] Embedding model: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim vectors)
- [ ] Duplicates detected at cosine similarity ≥0.90
- [ ] Earliest timestamp post retained for duplicates
- [ ] Final dataset: 8,000-10,000 posts (expect ~20% removal)
- [ ] Statistics JSON includes: `original_count`, `removed_by_length`, `removed_by_duplicate`, `final_count`, `removal_rate`

**Aspect Schema:**
- [ ] JSON schema with exactly 10 aspects (IDs 0-9)
- [ ] 10 aspects: `occupational`, `financial`, `romantic`, `familial`, `health`, `academic`, `existential`, `social`, `life_events`, `self_image`
- [ ] Each aspect has: `id` (int), `name_en` (str), `name_vi` (str), `definition` (str, 1-2 sentences), `academic_sources` (list of citations), `inclusion_rules` (list, ≥3), `exclusion_rules` (list, ≥2), `keywords_vi` (list, ≥10), `positive_examples` (list, exactly 3), `negative_examples` (list, exactly 3)
- [ ] Schema version in filename: `aspects_v1.json`
- [ ] SHA-256 hash stored in `aspects_v1.sha256`

### Deliverables

- `scripts/data_cleaning.py`
- `data/cleaned/voz_posts_cleaned_v1.jsonl`
- `reports/cleaning_stats_v1.json`
- `config/aspects_v1.json`
- `config/aspects_v1.sha256`

---

## Sprint 3: LLM Labeling Pipeline

**Requires:** Sprint 2 (cleaned data + aspect schema)

### Input
- **Cleaned posts:** `data/cleaned/voz_posts_cleaned_v1.jsonl`
- **Aspect schema:** `config/aspects_v1.json` (10 aspects with definitions, keywords, examples)
- **Aspect hash:** `config/aspects_v1.sha256` (for version verification)
- **Expected records:** ~8,000-10,000 posts from Sprint 2

### Goal
Label all posts using 3-model ensemble via Ollama for multi-label stress aspect classification.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| 3.1 | Install and run Ollama with `llama3.1:8b` (4.9GB VRAM) | R4.1 |
| 3.2 | Install and run Ollama with `mixtral:8x7b` (26GB VRAM, replaces GPT-OSS) | R4.1 |
| 3.3 | Install and run Ollama with `gemma2:9b` (5.4GB VRAM) | R4.1 |
| 3.4 | Create frozen prompt template with aspect definitions, output JSON schema `{"aspects": [0,2,5], "reasoning": "..."}` | R4.2 |
| 3.5 | Build sequential labeling: load 1 model → label all posts → unload → next model (batch_size=8) | R17.2 |
| 3.6 | Implement retry: max 2 retries per post, 60s timeout per request | R19.1 |
| 3.7 | Implement fallback: 1 model fail → use other 2 votes, 2+ models fail → discard post | R19.2 |
| 3.8 | Log invalid outputs (non-JSON, missing fields) to `logs/invalid_outputs.jsonl` | R4.3 |

### Acceptance Criteria

- [ ] All 3 models respond via `ollama run <model>` and HTTP API `localhost:11434`
- [ ] Prompt stored in `config/prompt_v1.txt`, SHA-256 hash in `config/prompt_v1.sha256`
- [ ] Models run sequentially (only 1 model loaded in GPU at a time to fit in 24GB VRAM)
- [ ] Each post receives labels from all 3 models (or 2 if 1 fails)
- [ ] Output JSON per post: `{"post_id": str, "text": str, "model_outputs": {"llama3.1": [...], "mixtral": [...], "gemma2": [...]}}`
- [ ] Invalid outputs logged with: `post_id`, `model`, `raw_output`, `error_type`, `timestamp`
- [ ] Retry on timeout/error (max 2 attempts), 60s timeout per request
- [ ] Posts with 2+ model failures logged and excluded from output
- [ ] Expected throughput: ~500 posts/hour → ~20 hours for 10k posts

### Deliverables

- `scripts/llm_labeling.py`
- `config/prompt_v1.txt`
- `config/prompt_v1.sha256`
- `data/labeled/llm_outputs_v1.jsonl`
- `logs/invalid_outputs.jsonl`

---

## Sprint 4: Voting & Confidence Assignment

**Requires:** Sprint 3 (LLM labels)

### Input
- **LLM outputs:** `data/labeled/llm_outputs_v1.jsonl`
- **Format:** Each line contains `{"post_id", "text", "model_outputs": {"llama3.1": [aspects], "mixtral": [aspects], "gemma2": [aspects]}}`
- **Expected records:** ~8,000-10,000 labeled posts from Sprint 3

### Goal
Aggregate 3-model votes per aspect and assign confidence scores to each post.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| 4.1 | For each aspect (0-9), count votes from 3 models independently | R5.1 |
| 4.2 | Compute aspect confidence: 3/3 agree → 1.0, 2/3 agree → 0.67, 1/3 or 0/3 → 0.0 | R5.2 |
| 4.3 | Compute post confidence = mean of 10 aspect confidences | R5.3 |
| 4.4 | Split posts: confidence ≥0.8 → train, 0.6-0.79 → retrain pool, <0.6 → discard | R5.4 |
| 4.5 | Compute agreement rate per aspect: `count(votes≥2) / count(aspect_predicted_positive)` | R6.1 |

### Acceptance Criteria

- [ ] Voting computed independently for each of 10 aspects (not whole-post voting)
- [ ] Aspect label = 1 if ≥2 models agree, else 0
- [ ] Post confidence = `sum(aspect_confidences) / 10` (range 0.0-1.0)
- [ ] Output split: `high_confidence.jsonl` (≥0.8), `medium_confidence.jsonl` (0.6-0.79), discarded (<0.6)
- [ ] Agreement rate per aspect logged: `{"aspect_id": 0, "aspect_name": "occupational", "agreement_rate": 0.85, "total_positive": 1200, "agreed_count": 1020}`
- [ ] Expected distribution: ~60% high, ~25% medium, ~15% discarded
- [ ] Medium confidence pool capped at 10,000 posts (FIFO eviction if exceeded)

### Deliverables

- `scripts/voting_aggregation.py`
- `data/voted/high_confidence.jsonl` (confidence ≥0.8)
- `data/voted/medium_confidence.jsonl` (confidence 0.6-0.79)
- `reports/agreement_rates_v1.jsonl`

---

## Sprint 5: Dataset Splitting & Gold Set

**Requires:** Sprint 4 (voted/confidence-scored data)

### Input
- **High confidence posts:** `data/voted/high_confidence.jsonl` (confidence ≥0.8)
- **Medium confidence posts:** `data/voted/medium_confidence.jsonl` (confidence 0.6-0.79)
- **Format:** Each line contains `{"post_id", "text", "aspects": [0,2,5], "aspect_confidences": [...], "confidence": 0.85}`
- **Expected records:** ~6,000 high + ~2,500 medium = ~8,500 total usable posts

### Goal
Create stratified train/val/test splits and human-verified gold calibration set.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| 5.1 | Use scikit-learn `iterative_stratification` for multi-label split: 80% train, 10% val, 10% test | R8.1, R8.2 |
| 5.2 | Verify aspect frequency deviation <5% across splits | R8.2 |
| 5.3 | Sample 300 gold posts: 30 per aspect, stratified (15 high-conf + 15 medium-conf each) | R7.1.1 |
| 5.4 | If aspect has <15 high-conf posts, take all available + fill from medium-conf | R7.1.2 |
| 5.5 | Create annotation guidelines with examples for each aspect | R7.1.3 |
| 5.6 | Mark test set read-only (chmod 444), add `.immutable` marker file | R8.3 |

### Acceptance Criteria

- [ ] Split ratio: Train 80% (±1%), Val 10% (±1%), Test 10% (±1%)
- [ ] Aspect frequency in each split within 5% of original distribution
- [ ] Gold set: exactly 300 posts, 30 per aspect (or documented exception)
- [ ] Gold set composition: 50% from high-confidence (≥0.8), 50% from medium-confidence (0.6-0.79)
- [ ] Edge cases logged to `reports/gold_sampling_exceptions.json`
- [ ] Test set files are read-only with `.immutable` marker
- [ ] Gold set posts excluded from train/val/test (verified by post_id check)
- [ ] Output format: JSONL with fields `post_id`, `text`, `aspects` (list of ints), `confidence`, `split`

### Deliverables

- `scripts/dataset_splitting.py`
- `data/splits/train_v1.jsonl` (~6,400 posts)
- `data/splits/val_v1.jsonl` (~800 posts)
- `data/splits/test_v1.jsonl` (~800 posts, read-only)
- `data/gold/gold_v1.csv` (300 posts for human verification)
- `docs/gold_annotation_guidelines.md`
- `reports/gold_sampling_exceptions.json`

---

## Sprint 6: PhoBERT Training

**Requires:** Sprint 5 (train/val/test splits)

### Input
- **Training set:** `data/splits/train_v1.jsonl` (~6,400 posts)
- **Validation set:** `data/splits/val_v1.jsonl` (~800 posts)
- **Aspect schema:** `config/aspects_v1.json` (for class weights and aspect mapping)
- **Format:** Each line contains `{"post_id", "text", "aspects": [0,2,5], "confidence": 0.85, "split": "train"}`
- **Pre-trained model:** `vinai/phobert-base-v2` from HuggingFace

### Goal
Train multi-label PhoBERT classifier for 10 stress aspects.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| 6.1 | Load `vinai/phobert-base-v2` from HuggingFace (135M params) | R9.1 |
| 6.2 | Add classification head: Linear(768→256) → ReLU → Dropout(0.3) → Linear(256→10) → Sigmoid | R9.2 |
| 6.3 | Compute class weights: `weight_k = total_samples / (10 * positive_samples_k)` per aspect | R9.3.2 |
| 6.4 | Use `BCEWithLogitsLoss` with `pos_weight` for class imbalance | R9.3.1 |
| 6.5 | Early stopping: patience=3 epochs, monitor val_loss, min_delta=0.001 | R9.3.3 |
| 6.6 | Set random seed=42 for PyTorch, NumPy, and Python random | R9.3.3 |
| 6.7 | Save metadata JSON with all training configs and data versions | R9.4 |

### Acceptance Criteria

- [ ] Base model: `vinai/phobert-base-v2` (768-dim hidden, 135M params)
- [ ] Classification head: 768 → 256 → 10 with ReLU, Dropout(0.3), Sigmoid
- [ ] Loss: BCEWithLogitsLoss with per-aspect pos_weight
- [ ] Optimizer: AdamW, lr=2e-5, weight_decay=0.01
- [ ] Batch size: 16, max_seq_length: 256 tokens
- [ ] Epochs: max 10, early stopping patience=3
- [ ] Training hardware: 1x GPU with ≥16GB VRAM
- [ ] Expected training time: ~2 hours on RTX 3090
- [ ] Checkpoints saved every epoch to `ml/models/phobert_stress_v1/checkpoints/`
- [ ] Final model saved as `model.pt` (state_dict) and `config.json`
- [ ] Metadata includes: `dataset_version`, `aspects_version`, `prompt_hash`, `hyperparams`, `seed`, `training_time`, `best_epoch`, `val_loss`

### Deliverables

- `ml/training/train_phobert.py`
- `ml/models/phobert_stress_v1/model.pt`
- `ml/models/phobert_stress_v1/config.json`
- `ml/models/phobert_stress_v1/metadata.json`
- `ml/models/phobert_stress_v1/checkpoints/` (epoch checkpoints)

---

## Sprint 7: Evaluation & Error Analysis

**Requires:** Sprint 6 (trained model)

### Input
- **Test set:** `data/splits/test_v1.jsonl` (~800 posts, read-only)
- **Validation set:** `data/splits/val_v1.jsonl` (~800 posts, for calibration)
- **Trained model:** `ml/models/phobert_stress_v1/model.pt`
- **Model config:** `ml/models/phobert_stress_v1/config.json`
- **Aspect schema:** `config/aspects_v1.json` (for aspect names in reports)

### Goal
Evaluate model on test set and analyze prediction errors for each aspect.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| 7.1 | Compute Micro-F1 (global TP/FP/FN) and Macro-F1 (avg of per-aspect F1) | R10.1 |
| 7.2 | Compute Hamming Loss (fraction of wrong labels) and Exact Match Ratio (all 10 correct) | R10.1 |
| 7.3 | Compute per-aspect: Precision, Recall, F1, Support (positive count) | R10.1 |
| 7.4 | Compute FNR (False Negative Rate) for high-risk aspects: Health(4), Existential(6), Life_Events(8) | R10.1.1 |
| 7.5 | Generate aspect co-occurrence confusion matrix (10x10) | R10.2 |
| 7.6 | Extract 5 FP and 5 FN examples per aspect with post text and prediction scores | R10.2 |
| 7.7 | Apply Platt scaling calibration on validation set, save calibrator | R11.2 |

### Acceptance Criteria

- [ ] All metrics computed on frozen test set (800 posts)
- [ ] Target metrics: Micro-F1 ≥0.75, Macro-F1 ≥0.70, Exact Match ≥0.50
- [ ] Per-aspect metrics table with columns: `aspect_id`, `aspect_name`, `precision`, `recall`, `f1`, `support`, `fnr`
- [ ] High-risk FNR threshold: Health ≤0.20, Existential ≤0.25, Life_Events ≤0.20
- [ ] Confusion matrix: 10x10 showing co-prediction rates between aspects
- [ ] Error examples JSON: 5 FP + 5 FN per aspect = 100 examples total
- [ ] Each error example includes: `post_id`, `text`, `true_labels`, `pred_labels`, `pred_scores`, `error_type`
- [ ] Platt scaling calibrator saved as `calibrator.pkl`
- [ ] Calibration plot (reliability diagram) saved as `calibration_plot.png`

### Deliverables

- `scripts/evaluate_model.py`
- `reports/evaluation_v1.json` (all metrics)
- `reports/error_analysis_v1.json` (100 error examples)
- `reports/confusion_patterns_v1.json` (10x10 matrix)
- `ml/models/phobert_stress_v1/calibrator.pkl`
- `reports/calibration_plot.png`

---

## Sprint 8: Deployment + Real-Time Demographics & Dashboard

**Combines:** Deployment & Inference API + Real-Time Demographic Inference + Streamlit Dashboard (requires Sprint 7)

### Input
- **Trained model:** `ml/models/phobert_stress_v1/model.pt`
- **Model config:** `ml/models/phobert_stress_v1/config.json`
- **Calibrator:** `ml/models/phobert_stress_v1/calibrator.pkl`
- **Aspect schema:** `config/aspects_v1.json` (for aspect ID → name mapping)
- **Kafka topic:** `voz.posts.raw.v1` (incoming posts from crawler)
- **Ollama model:** `mixtral:8x7b` (for demographic extraction)

### Goal
Deploy PhoBERT model for real-time stress inference via Spark Streaming, use Mixtral 8x7B for demographic extraction, and display results on Streamlit dashboard.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| **Deployment** | | |
| 8.1 | Build `StressInferenceWrapper` class: load model, tokenizer, calibrator from `ml/models/phobert_stress_v1/` | R11.1 |
| 8.2 | Return JSON: `{"post_id", "aspects": [0,2,5], "aspect_probs": [0.1,...,0.9], "confidence", "model_version", "timestamp"}` | R11.1 |
| 8.3 | Benchmark latency: single post ≤500ms on GPU, ≤2s on CPU | R18.1 |
| 8.4 | Implement batch inference: accept list of 1-32 posts, return list of results | R18.1 |
| 8.5 | Integrate wrapper into Spark Structured Streaming with Kafka source | Existing |
| 8.6 | Create Cassandra table `voz_classified_posts` with columns for aspects + demographics | R11.1 |
| **Real-Time Demographics (Mixtral 8x7B)** | | |
| 8.7 | Run Mixtral 8x7B via Ollama: `ollama run mixtral:8x7b` (requires 26GB VRAM or CPU offload) | R14.3.1 |
| 8.8 | Create gender prompt: extract from text, output `{"gender": "nam"|"nữ"|"unknown"}` | R14.3.2 |
| 8.9 | Create age prompt: infer from context, output `{"age_group": "teen"|"young_adult"|"adult"|"middle_aged"|"senior"|"unknown"}` | R14.3.5 |
| 8.10 | Create occupation prompt: detect from text, output `{"occupation": "<category>"|"unknown"}` with 8 categories | R14.3.3 |
| 8.11 | Create relationship prompt: output `{"relationship": "single"|"dating"|"married"|"divorced"|"unknown"}` | R14.3.6 |
| 8.12 | Run demographic inference async: Spark writes to Kafka topic `voz.demographics.pending`, separate consumer processes with LLM | R14.4 |
| 8.13 | Update Cassandra row with demographics after LLM inference completes (eventual consistency) | R14.4 |
| 8.14 | If LLM returns invalid JSON or low-confidence response, set all demographics to "unknown" | R14.3.4 |
| **Real-Time Streamlit Dashboard** | | |
| 8.15 | Post feed: query Cassandra `SELECT * FROM voz_classified_posts WHERE hour_bucket = ? ORDER BY classified_at DESC LIMIT 50` | R22.1 |
| 8.16 | Post card component: show text (first 200 chars), stress badge, aspect chips with colors (Occupational=blue, Health=red, etc.) | R22.2 |
| 8.17 | Demographics row: icons + labels for gender (👨/👩), age group, occupation, relationship | R22.3 |
| 8.18 | Aspect distribution: Plotly bar chart, query `SELECT aspect, COUNT(*) FROM voz_classified_posts GROUP BY aspect` | R22.4 |
| 8.19 | Demographics charts: Plotly pie charts for gender distribution, occupation distribution | R22.5 |
| 8.20 | Co-occurrence heatmap: Plotly heatmap 10x10, compute from `aspects` array in Cassandra | R22.6 |
| 8.21 | Time-series: Plotly line chart showing stress_rate (stress_count/total_count) per hour for last 24h | R22.7 |
| 8.22 | Sidebar filters: multi-select aspects, gender dropdown, occupation dropdown, date range picker | R22.8 |
| 8.23 | Auto-refresh: `st.experimental_rerun()` every 5 seconds via `time.sleep()` in loop | R22.9 |

### Acceptance Criteria

**Deployment:**
- [ ] `StressInferenceWrapper.predict(text) -> dict` returns all required fields
- [ ] `StressInferenceWrapper.predict_batch(texts: list) -> list` handles 1-32 posts
- [ ] Single post latency: ≤500ms GPU (RTX 3090), ≤2000ms CPU
- [ ] Batch of 32 posts: ≤3s GPU, ≤30s CPU
- [ ] Model version string: `phobert_stress_v1_<timestamp>`
- [ ] Calibrated probabilities using saved `calibrator.pkl`

**Real-Time Demographics:**
- [ ] Mixtral 8x7B responds via Ollama API `POST http://localhost:11434/api/generate`
- [ ] Gender values: `nam`, `nữ`, `unknown` (no guessing from name)
- [ ] Age groups: `teen` (13-17), `young_adult` (18-25), `adult` (26-40), `middle_aged` (41-60), `senior` (60+), `unknown`
- [ ] Occupation categories: `student`, `office_worker`, `it_engineer`, `healthcare`, `teacher`, `blue_collar`, `freelance`, `unemployed`, `unknown`
- [ ] Relationship: `single`, `dating`, `married`, `divorced`, `unknown`
- [ ] Async processing: demographics appear 5-30s after stress classification (eventual consistency)
- [ ] Cassandra columns: `gender TEXT`, `age_group TEXT`, `occupation TEXT`, `relationship TEXT`

**Real-Time Dashboard:**
- [ ] Post feed: 50 most recent posts, sorted by `classified_at DESC`
- [ ] Aspect chips color mapping: `{0: "#3498db", 1: "#2ecc71", 2: "#e74c3c", 3: "#9b59b6", 4: "#e67e22", 5: "#1abc9c", 6: "#34495e", 7: "#f39c12", 8: "#d35400", 9: "#c0392b"}`
- [ ] Charts update on page refresh (every 5s)
- [ ] Filters persist in session state
- [ ] Dashboard loads in <3s on first visit
- [ ] Mobile-responsive layout (Streamlit default)

### Deliverables

- `spark/stress_inference_wrapper.py` (PhoBERT inference class)
- `spark/voz_streaming_pipeline.py` (Kafka → PhoBERT → Cassandra)
- `spark/demographic_consumer.py` (Kafka → Mixtral → Cassandra update)
- `cassandra/schema/05_voz_classified_posts.cql` (with demographic columns)
- `config/demographic_prompts/gender_v1.txt`
- `config/demographic_prompts/age_v1.txt`
- `config/demographic_prompts/occupation_v1.txt`
- `config/demographic_prompts/relationship_v1.txt`
- `streamlit_app/pages/realtime_insights.py`
- `streamlit_app/components/post_card.py`
- `streamlit_app/components/charts.py`
- `streamlit_app/utils/cassandra_client.py`

---

## Sprint 9: Insights + Retraining Pipeline

**Combines:** Insight Generation + Retraining Pipeline (both require Sprint 8)

### Input
- **Classified posts:** Cassandra table `reddit_rt.voz_classified_posts` (with aspects + demographics)
- **Medium confidence pool:** `data/voted/medium_confidence.jsonl` (for retraining)
- **High confidence pool:** `data/voted/high_confidence.jsonl` (for retraining sampling)
- **Current model:** `ml/models/phobert_stress_v1/` (for comparison)
- **Query filter:** `confidence >= 0.8 AND gender != 'unknown'` (for insights)

### Goal
Generate statistical insights by demographic groups and set up automated weekly retraining pipeline.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| **Insights** | | |
| 9.1 | Query Cassandra for posts with confidence ≥0.8 and demographics != "unknown" | R15.1 |
| 9.2 | Compute aspect frequency by gender: `{aspect_id: {nam: count, nữ: count}}` for all 10 aspects | R15.2 |
| 9.3 | Compute aspect frequency by occupation: `{aspect_id: {student: count, ...}}` for all 8 occupations | R15.2 |
| 9.4 | Compute 10x10 aspect co-occurrence matrix per gender and per occupation | R15.2 |
| 9.5 | Add metadata to all reports: `sample_size`, `date_range`, `confidence_threshold`, `limitations` | R15.3 |
| **Retraining** | | |
| 9.6 | Compose retraining batch: 75% from medium-confidence pool + 25% from high-confidence (random sample) | R12.2 |
| 9.7 | Cap high-confidence sampling: max 40 posts per aspect to prevent overfitting | R12.3 |
| 9.8 | Create Airflow DAG: schedule `0 2 * * 0` (Sunday 2AM), tasks: export → label → train → evaluate → deploy | R12.1 |
| 9.9 | Set Docker limits: `mem_limit: 32g`, `cpus: 8`, GPU passthrough for training task | R20.1 |
| 9.10 | Use Airflow pool `training_pool` with 1 slot to prevent parallel training | R20.2 |

### Acceptance Criteria

**Insights:**
- [ ] Query filters: `confidence >= 0.8 AND gender != 'unknown'` (or occupation)
- [ ] Gender insight JSON: `{"aspect_0": {"nam": 450, "nữ": 380, "chi_square": 12.5, "p_value": 0.0004}, ...}`
- [ ] Occupation insight JSON: same structure with 8 occupation categories
- [ ] Co-occurrence JSON: `{"by_gender": {"nam": [[...10x10...]], "nữ": [[...]]}, "by_occupation": {...}}`
- [ ] All reports include: `sample_size` (int), `date_range` (str), `confidence_threshold` (0.8), `limitations` (str describing biases)
- [ ] Chi-square test computed for each aspect × demographic to detect significant differences

**Retraining:**
- [ ] Retraining batch size: 1000 posts (750 medium-conf + 250 high-conf)
- [ ] High-confidence cap: max 40 posts per aspect (400 total max)
- [ ] Sampling: stratified by aspect, without replacement
- [ ] Airflow DAG schedule: weekly Sunday 2:00 AM UTC
- [ ] DAG tasks: `export_data` → `run_llm_labeling` → `train_model` → `evaluate_model` → `deploy_if_improved`
- [ ] Docker resource limits enforced via `docker-compose.override.yml`
- [ ] Airflow pool `training_pool` with `slots=1` prevents concurrent training
- [ ] Model deployed only if `new_macro_f1 > current_macro_f1 + 0.01`

### Deliverables

- `scripts/generate_insights.py`
- `reports/insights_gender_v1.json`
- `reports/insights_occupation_v1.json`
- `reports/insights_cooccurrence_v1.json`
- `scripts/compose_retraining_data.py`
- `airflow/dags/voz_weekly_retrain.py`
- `airflow/pools/training_pool.json`
- `docker-compose.override.yml` (resource limits)

---

## Sprint 10: Drift Monitoring + Governance

**Combines:** Drift Monitoring & Safeguards + Governance & Traceability (both require Sprint 9)

### Input
- **Weekly predictions:** Cassandra table `reddit_rt.voz_classified_posts` (last 7 days)
- **Previous week stats:** `reports/weekly_stats_v1.jsonl` (for drift comparison)
- **Gold set:** `data/gold/gold_v1.csv` (300 posts for calibration check)
- **Gold baseline:** `reports/gold_baseline.json` (original F1 scores)
- **Current model:** `ml/models/phobert_stress_v1/metadata.json` (hashes for verification)
- **All data files:** For checksum computation and lineage tracking

### Goal
Detect model performance drift and data distribution shifts; ensure full reproducibility and traceability of all artifacts.

### Tasks

| ID | Task | Requirement |
|----|------|-------------|
| **Drift Monitoring** | | |
| 10.1 | Compute weekly aspect frequency: `freq_k = count(aspect_k) / total_posts` for each aspect | R13.1 |
| 10.2 | Compute mean prediction entropy: `H = -Σ(p_k * log(p_k))` averaged across all posts | R13.1 |
| 10.3 | Compute KL divergence: `KL(P_current || P_previous)` comparing this week vs last week aspect distributions | R13.1 |
| 10.4 | Halt retraining if: any aspect freq changes >±15%, entropy increases >0.20, or KL >0.30 | R13.2 |
| 10.5 | Log drift event to `reports/drift_log_v1.jsonl` and send Slack webhook alert | R13.2 |
| 10.6 | Run model on gold set (300 posts) weekly, compare F1 to baseline, alert if drop >5% | R7.3 |
| **Governance** | | |
| 10.7 | Compute SHA-256 checksum for all dataset files, store in `checksums.json` | R16.1 |
| 10.8 | Verify aspect schema hash matches `config/aspects_v1.sha256` before training | R16.1 |
| 10.9 | Store prompt hash in model metadata, verify before LLM labeling | R16.1 |
| 10.10 | Model metadata must include: `data_sha256`, `aspects_sha256`, `prompt_sha256`, `train_config`, `git_commit` | R16.2 |
| 10.11 | Implement retention: raw posts 90d TTL, labeled 2yr, predictions 1yr, gold permanent, logs 180d | R21 |
| 10.12 | Generate model lineage markdown with full artifact links and training history | R16.2 |

### Acceptance Criteria

**Drift Monitoring:**
- [ ] Aspect frequency tracked: `{"week": "2024-W03", "aspect_0_freq": 0.15, ..., "aspect_9_freq": 0.08}`
- [ ] Entropy baseline established from first week, compared weekly
- [ ] KL divergence computed using scipy `entropy(p, q)` function
- [ ] Drift thresholds: freq_change >15%, entropy_increase >0.20, KL >0.30
- [ ] Drift detection halts `voz_weekly_retrain` DAG via Airflow variable `drift_detected=true`
- [ ] Slack alert format: `🚨 Drift detected: aspect_2 frequency changed +18% (threshold: 15%)`
- [ ] Gold set evaluation: run `evaluate_model.py --test data/gold/gold_v1.csv` weekly
- [ ] Alert if gold set F1 drops >5% from baseline (stored in `reports/gold_baseline.json`)

**Governance:**
- [ ] All data files have SHA-256 in `data/checksums.json`: `{"train_v1.jsonl": "abc123...", ...}`
- [ ] Training script validates: `assert sha256(aspects_v1.json) == open(aspects_v1.sha256).read()`
- [ ] Model `metadata.json` includes: `data_sha256`, `aspects_sha256`, `prompt_sha256`, `config`, `git_commit`, `training_date`
- [ ] Retention policy YAML: `{raw_posts: {ttl_days: 90}, labeled: {ttl_days: 730}, ...}`
- [ ] Cassandra TTL set via `default_time_to_live` in table schema
- [ ] Lineage doc includes: data source → cleaning → labeling → training → evaluation → deployment (with file paths and hashes)

### Deliverables

- `scripts/drift_monitor.py`
- `airflow/dags/voz_drift_check.py` (schedule: daily 6AM)
- `reports/drift_log_v1.jsonl`
- `reports/gold_baseline.json`
- `scripts/version_artifacts.py`
- `data/checksums.json`
- `docs/model_lineage_v1.md`
- `config/retention_policy.yaml`
- `config/slack_webhook.env` (optional)

---

## Sprint Summary (Consolidated)

| Sprint | Focus | Dependencies |
|--------|-------|--------------|
| 1 | Data Collection | None | ✓ COMPLETED |
| 2 | Data Cleaning + Aspect Schema | Sprint 1 |
| 3 | LLM Labeling | Sprint 2 |
| 4 | Voting & Confidence | Sprint 3 |
| 5 | Dataset Splits & Gold | Sprint 4 |
| 6 | PhoBERT Training | Sprint 5 |
| 7 | Evaluation | Sprint 6 |
| 8 | Deployment + Real-Time Demographics & Dashboard | Sprint 7 |
| 9 | Insights + Retraining | Sprint 8 |
| 10 | Drift Monitoring + Governance | Sprint 9 |

**Total: 10 Sprints** (consolidated from 14)

---

## Dependencies

```
Sprint 1 (Crawler) ✓
       ↓
Sprint 2 (Cleaning + Aspects)
       ↓
Sprint 3 (LLM Labeling)
       ↓
Sprint 4 (Voting)
       ↓
Sprint 5 (Splits + Gold)
       ↓
Sprint 6 (Training)
       ↓
Sprint 7 (Evaluation)
       ↓
Sprint 8 (Deployment + Demographics)
       ↓
Sprint 9 (Insights + Retraining)
       ↓
Sprint 10 (Drift + Governance)
```

**Critical Path:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

**Parallelization within sprints:**
- Sprint 2: Data cleaning and aspect schema can be done by different team members
- Sprint 8: Deployment and demographics inference are independent tasks
- Sprint 9: Insights and retraining setup are independent tasks
- Sprint 10: Drift monitoring and governance are independent tasks
