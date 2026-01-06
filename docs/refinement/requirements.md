# System Requirements: Stress Detection, Training, and Insight Pipeline

## 1. Scope and Objectives

### R1.1 Objective

The system shall detect and analyze stress aspects in Vietnamese social media posts, train a multi-label classifier, and generate demographic-based stress insights.

### R1.2 Constraints

- No manual large-scale annotation is allowed
- Annotation must use LLM ensemble voting
- System must be reproducible and auditable
- Demographic attributes must not be used for training

---

## 2. Stress Aspect Taxonomy

### R2.1 Aspect Count

The system shall support exactly 10 stress aspects.

### R2.2 Aspect Definitions (Complete Taxonomy)

| ID | Aspect Name | Vietnamese | Description | Academic Sources |
|----|-------------|------------|-------------|------------------|
| 0 | Occupational | Công việc | Workload, boss, deadlines, job insecurity | Karasek (1979); Siegrist (1996) |
| 1 | Financial | Tài chính | Income, debt, expenses, financial insecurity | Prawitz et al. (2006); Sweet et al. (2013) |
| 2 | Academic | Học tập | Exams, grades, school pressure | Lin & Chen (2009); Misra & McKean (2000) |
| 3 | Familial | Gia đình | Parents, children, family conflict | Conger et al. (1990); Pearlin (1989) |
| 4 | Health | Sức khỏe | Illness, sleep, fatigue, pain | Cohen et al. (1983); Lazarus & Folkman (1984) |
| 5 | Romantic | Tình cảm | Love, breakup, loneliness | Hendrick (1988); Stack & Eshleman (1998) |
| 6 | Existential | Hiện sinh | Meaning, self-worth, identity | Crumbaugh (1964); Frankl (1959) |
| 7 | Social–Interpersonal | Xã hội | Friends, isolation, peer conflict | Thoits (1995); Cacioppo & Hawkley (2009) |
| 8 | Life Events / Transitional | Sự kiện | Loss, relocation, divorce, major change | Holmes & Rahe (1967); Wheaton (1999) |
| 9 | Environmental / Contextual | Môi trường | Noise, traffic, housing, surroundings | Evans & Cohen (1987); Stokols (1992) |

### R2.2.1 High-Risk Aspects

The following aspects require special recall/FNR reporting:

- **4** — Health
- **6** — Existential
- **8** — Life Events

### R2.2.2 Aspect Properties

Each stress aspect must include:

- Unique integer ID (0-9)
- English name
- Vietnamese name
- Formal definition
- Academic source(s)
- Inclusion rules
- Exclusion rules
- Vietnamese keywords
- ≥2 positive examples
- ≥2 negative examples

### R2.3 Aspect Versioning

- Aspect definitions must be stored in a versioned JSON file
- Aspect file version must not change during a training cycle
- Model metadata must reference the aspect version used

---

## 3. Data Collection

### R3.1 Data Sources

#### R3.1.1 Allowed Source (ONLY)

The system shall ingest data exclusively from:

- **VOZ.vn** — Forum: `voz.vn/f/tam-su.17`

No other sources are allowed in the current phase.

#### R3.1.2 Explicitly Excluded Sources

The system must not ingest data from:

- Reddit (including r/vozforums)
- Tinh Tế
- VnExpress (articles or comments)
- Any news site comment sections
- Any long-form discussion platforms

#### R3.1.3 Rationale

The exclusion is based on data quality constraints:

- Posts on Tinh Tế and VnExpress are frequently too long, often informational/argumentative, and contain low stress signal density
- Reddit is excluded to maintain Vietnamese-native linguistic style and avoid cross-cultural stress expression bias

#### R3.1.4 Crawling Strategy

- Crawl all pages, newest first
- Continue until 12,000 posts reached
- No programmatic stress filtering during collection

### R3.2 Post Requirements

#### R3.2.1 Required Fields

Each post must contain:

- Unique post ID
- Text content
- Timestamp
- Source identifier

#### R3.2.2 Length Constraints

- Minimum length: 20 tokens
- Maximum length: 300 tokens
- Posts outside this range must be discarded

### R3.3 Dataset Size

- Target raw posts collected: ≥12,000
- Expected usable posts after filtering: 8,000–10,000

### R3.4 Data Cleaning

#### R3.4.1 Duplicate Removal

- Algorithm: Cosine similarity on sentence embeddings
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Threshold: ≥0.90
- Keep earliest timestamped post

#### R3.4.2 Token Filter

- Remove posts with <20 tokens
- Remove posts with >300 tokens
- Preserve original timestamps and IDs

---

## 4. LLM Ensemble Labeling

### R4.1 Models

The ensemble shall use exactly:

- LLaMA 3.1 8B (`llama3.1:8b`)
- GPT-OSS 20B (`gpt-oss:20b`)
- Gemma 2 9B (`gemma2:9b`)

### R4.2 Prompt Control

#### R4.2.1 Frozen Prompt (LOCKED)

```
You are a mental health expert analyzing Vietnamese forum posts.

TASK:
Identify which types of psychological stress are present in the post below.

STRESS ASPECTS:
0. Occupational – work, boss, deadlines, job pressure
1. Financial – money, debt, expenses, income
2. Academic – exams, grades, school, thesis
3. Familial – parents, children, family conflict
4. Health – illness, sleep problems, fatigue, pain
5. Romantic – love, breakup, loneliness
6. Existential – meaninglessness, self-doubt, identity
7. Social – friends, isolation, peer conflict
8. Life Events – loss, relocation, major life changes
9. Environmental – noise, traffic, housing, surroundings

RULES:
- Select ALL applicable aspects
- Select only if stress is clearly expressed or strongly implied
- If no stress is present, return an empty list
- Do NOT guess or speculate

POST:
"{TEXT}"

OUTPUT FORMAT (JSON ONLY):
{"aspects": [list of aspect IDs]}
```

#### R4.2.2 Prompt Hashing

- Hash algorithm: SHA-256
- Store hash with model metadata

### R4.3 Output Format

Each model output must conform to:

```json
{"aspects": [int, int, ...]}
```

- Invalid outputs must be logged to `invalid_outputs.jsonl` before discard

---

## 5. Voting and Confidence Assignment

### R5.1 Voting Unit

Voting must be performed per aspect, not per post.

### R5.2 Aspect Voting Rules

For each post and aspect k:

- 3 votes → aspect = 1, confidence = 1.0
- 2 votes → aspect = 1, confidence = 0.67
- ≤1 vote → aspect = 0

### R5.3 Post Confidence

Post confidence must be computed as:

```
mean(confidence of selected aspects)
```

### R5.4 Post Filtering (FINAL RULES)

| Confidence | Action |
|------------|--------|
| ≥ 0.8 | Training + Insight generation |
| 0.6 – 0.8 | Retraining pool |
| < 0.6 | Discard permanently |

#### R5.4.1 Retraining Pool Size

- Maximum: 10,000 posts
- If exceeded: Drop oldest entries first (FIFO)

#### R5.4.2 Enforcement

Posts with confidence < 0.6 must not be stored beyond raw logs.

---

## 6. Agreement Tracking

### R6.1 Aspect Agreement Rate

For each aspect k, the system shall compute:

```
agreement_rate_k = (# times votes ≥ 2) / (# times aspect predicted)
```

### R6.2 Logging

- Agreement rates must be logged per dataset version and model run
- Format: JSON Lines (`.jsonl`)

---

## 7. Gold Calibration Subset

### R7.1 Gold Size and Selection

#### R7.1.1 Selection Rules

- Total gold posts: 300
- Target: ≥20 per aspect
- Stratification:
  - 50% from high-confidence posts
  - 50% from medium-confidence posts

#### R7.1.2 Edge Case Handling

If an aspect has <20 high-confidence posts:

1. Take all available high-confidence posts
2. Supplement from medium-confidence posts
3. Never use low-confidence posts
4. Log shortage per aspect

#### R7.1.3 Annotation Method

- Annotated by 1 trained human annotator
- Annotation guidelines identical to LLM prompt
- Stored separately as `gold_v1.csv`

### R7.2 Usage Restrictions

Gold data shall NOT be used for:

- Training
- Validation
- Retraining
- Hyperparameter tuning

### R7.3 Allowed Uses

Gold data shall be used ONLY for:

- Confidence threshold calibration
- Bias analysis
- Drift monitoring

---

## 8. Dataset Splitting

### R8.1 Split Ratios

- Train: 80%
- Validation: 10%
- Test: 10%

### R8.2 Stratification

Splits must preserve:

- Aspect frequency
- Aspect co-occurrence patterns

### R8.3 Test Set

- Test set must be immutable
- No retraining on test data is allowed

---

## 9. Model Training

### R9.1 Model Type

The system shall use a Vietnamese pretrained transformer (PhoBERT or equivalent).

### R9.2 Task Definition

- Multi-label classification
- Independent sigmoid output per aspect

### R9.3 Training Controls

#### R9.3.1 Loss Function

- Binary cross-entropy loss

#### R9.3.2 Class Imbalance Weighting

Use inverse frequency weighting:

```
weight_k = total_samples / (num_aspects * samples_k)
```

**Disallowed methods:**
- Focal loss — NOT allowed
- Manual fixed weights — NOT allowed

#### R9.3.3 Other Controls

- Early stopping
- Fixed random seeds

### R9.4 Metadata

Each trained model must log:

- Dataset version
- Aspect version
- Prompt version (SHA-256 hash)
- Hyperparameters
- Random seed

---

## 10. Evaluation

### R10.1 Required Metrics

The system shall compute:

- Micro-F1
- Macro-F1
- Hamming Loss
- Exact Match Ratio
- Per-aspect precision and recall

#### R10.1.1 High-Risk Aspect Metrics

For aspects 4 (Health), 6 (Existential), 8 (Life Events):

- Recall
- False Negative Rate (FNR)

### R10.2 Error Analysis

The system must store:

- Confusion patterns
- Example false positives and negatives per aspect

---

## 11. Deployment

### R11.1 Inference Output

Each prediction must include:

- Aspect probabilities
- Model version
- Timestamp
- Confidence score

### R11.2 Calibration

- Probabilities must be calibrated using validation data
- Heuristic confidence formulas are not allowed

---

## 12. Retraining Pipeline

### R12.1 Weekly Retraining

Retraining shall occur weekly or manually triggered.

### R12.2 Retraining Data Composition

Each retraining batch must include:

- 70–80% low-confidence posts (from retraining pool)
- 20–30% high-confidence posts

### R12.3 High-Confidence Sampling

#### R12.3.1 Cap Definition

- Maximum: **40 samples per aspect** per retraining cycle
- This is enforced, not an example

#### R12.3.2 Sampling Method

- Uniform random sampling
- Aspect-stratified
- Without replacement

---

## 13. Drift Monitoring

### R13.1 Drift Signals

The system shall monitor:

- Aspect frequency shifts
- Prediction entropy changes
- Distribution divergence over time

### R13.2 Drift Thresholds (NUMERIC)

Retraining must halt if any of the following occur:

| Signal | Threshold |
|--------|-----------|
| Frequency drift | Absolute change > ±15% week-over-week |
| Entropy drift | Mean prediction entropy increase > 0.20 |
| Distribution drift | KL divergence > 0.30 |

If halted → log + alert, no deployment.

---

## 14. Demographic Inference (Insights Only)

### R14.1 Separation Rule

Demographic attributes must not be used for training.

### R14.2 Allowed Categories

#### R14.2.1 Gender

- male
- female
- unknown

#### R14.2.2 Occupation (Final Set)

- student
- it
- healthcare
- teacher
- worker
- unemployed
- retired
- unknown

### R14.3 Inference Method

#### R14.3.1 Inference Order

1. Rule-based keyword detection (primary)
2. LLM inference (secondary, only if rule-based fails)

#### R14.3.2 Gender Keywords

```
nam, nữ, con trai, con gái, đàn ông, phụ nữ
```

#### R14.3.3 Occupation Keywords

| Category | Keywords |
|----------|----------|
| student | sinh viên, học sinh |
| it | dev, lập trình, IT |
| healthcare | bác sĩ, y tá |
| teacher | giáo viên, giảng viên |
| worker | công nhân, đi làm |

#### R14.3.4 Enforcement Rule

- If not explicitly stated or strongly implied → assign `unknown`
- No guessing based on tone or vocabulary

### R14.4 Storage

Each post may include:

```json
{
  "gender": "male | female | unknown",
  "occupation": "student | it | healthcare | teacher | worker | unemployed | retired | unknown"
}
```

---

## 15. Insight Generation

### R15.1 Analysis Scope

Insights shall be computed only on high-confidence posts (confidence ≥ 0.8).

### R15.2 Required Analyses

The system shall support:

- Stress aspect distribution by gender
- Stress aspect distribution by occupation
- Aspect co-occurrence by demographic group

### R15.3 Reporting

All insights must include:

- Sample size
- Confidence filtering rule
- Limitations statement

---

## 16. Reproducibility and Governance

### R16.1 Version Control

The system shall version:

- Datasets
- Aspect definitions
- Prompts (SHA-256 hash)
- Models

### R16.2 Traceability

Each deployed model must be traceable to:

- Exact data snapshot
- Aspect schema
- Prompt hash
- Training configuration

---

## 17. Infrastructure Requirements

### R17.1 Hardware Requirements

#### R17.1.1 Training Node (PhoBERT)

- GPU: 1× NVIDIA T4 (16GB)
- RAM: 32 GB
- Disk: 100 GB

#### R17.1.2 LLM Labeling Node (Ollama)

- GPU: 1× NVIDIA A10 or L4
- RAM: 64 GB
- Max concurrent models: 1

### R17.2 LLM Execution

- LLaMA, GPT-OSS, Gemma2 must run sequentially
- Only one model loaded in GPU memory at a time
- Models may be swapped between batches

#### R17.2.1 Estimated Labeling Time

- Batch size: 8 posts
- Avg latency per batch: ~20 seconds
- Total time for 12,000 posts (3 models): ~25 hours

---

## 18. Inference Latency SLA

### R18.1 Real-Time Inference

- Max latency per post: ≤ 500 ms
- Batch size: ≤ 32 posts

### R18.2 LLM Labeling (Offline)

- No SLA (offline job)
- Max batch size: 8 posts per model

---

## 19. LLM Failure Handling

### R19.1 Retry Policy

- Retry failed model call up to 2 times
- Timeout per call: 60 seconds

### R19.2 Fallback Logic

| Scenario | Action |
|----------|--------|
| 1 model fails | Use remaining 2 models |
| 2 models fail | Discard post |

- Log failure reason for all failures

---

## 20. Airflow Resource Control

### R20.1 Docker Limits

Each Airflow task must define:

- `mem_limit`
- `cpu_limit`
- `gpu_access` (if applicable)

### R20.2 Parallelism

- Max parallel LLM labeling tasks: 1
- Max parallel training tasks: 1
- No exceptions

---

## 21. Data Retention Policy

| Data Type | Retention |
|-----------|-----------|
| Raw posts | 90 days |
| Labeled datasets | 2 years |
| Predictions | 1 year |
| Gold set | Permanent |
| Logs | 180 days |
