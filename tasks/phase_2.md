# Phase 2: Data Preparation

## Goal
Clean, label, validate, balance, and split 10k VOZ posts for PhoBERT training.

## Pipeline
```
voz_raw_posts → Clean → Qwen Label → Claude Validate → Balance → Split → data/splits/
```

## Tasks

### 2.1 Data Cleaning
- [ ] Export from Cassandra to JSONL
- [ ] Remove HTML entities & special chars
- [ ] Normalize Vietnamese unicode (NFC)
- [ ] Remove URLs, emails, phone numbers
- [ ] Collapse multiple whitespace
- [ ] Filter: 50 < len < 2000 chars
- [ ] Deduplicate by text hash

### 2.2 Define Aspect Labels
- [ ] Create aspect schema JSON
- [ ] 10 stress aspects (0-9 indices)

### 2.3 LLM Labeling (Qwen)
- [ ] Setup Ollama with Qwen2.5
- [ ] Batch labeling script
- [ ] Output: aspects[], confidence, reasoning

### 2.4 Claude Validation
- [ ] Sample 20% for validation
- [ ] Cross-check Qwen labels
- [ ] Flag disagreements (>2 aspect diff)
- [ ] Human review for conflicts
- [ ] Calculate inter-rater agreement (Cohen's Kappa)

### 2.5 Data Balancing
- [ ] Analyze aspect distribution
- [ ] Augmentation (40%): synonym swap, word shuffle
- [ ] Synthetic generation (60%): Qwen prompts for underrepresented aspects
- [ ] Target: >80% coverage per aspect

### 2.6 Data Splitting
- [ ] Train: 80% (~8000 posts)
- [ ] Validation: 10% (~1000 posts)
- [ ] Test: 10% (~1000 posts)
- [ ] Stratified by aspect distribution

## Aspect Schema

```json
// File: ml/aspects/stress_aspects.json
{
  "aspects": [
    {"id": 0, "name": "work_stress", "vi": "Áp lực công việc"},
    {"id": 1, "name": "financial_anxiety", "vi": "Lo âu tài chính"},
    {"id": 2, "name": "relationship_issues", "vi": "Vấn đề tình cảm"},
    {"id": 3, "name": "academic_pressure", "vi": "Áp lực học tập"},
    {"id": 4, "name": "exhaustion", "vi": "Kiệt sức"},
    {"id": 5, "name": "depression", "vi": "Trầm cảm"},
    {"id": 6, "name": "loneliness", "vi": "Cô đơn"},
    {"id": 7, "name": "health_concerns", "vi": "Lo lắng sức khỏe"},
    {"id": 8, "name": "family_conflict", "vi": "Mâu thuẫn gia đình"},
    {"id": 9, "name": "future_uncertainty", "vi": "Bất an tương lai"}
  ],
  "version": "1.0"
}
```

## Files Structure

```
data/
  raw/
    voz_exported.jsonl          # Raw export from Cassandra
  cleaned/
    voz_cleaned.jsonl           # After cleaning
  labeled/
    qwen_labels.jsonl           # Qwen outputs
    claude_validation.jsonl     # Claude validation results
    conflicts.jsonl             # Disagreements for review
    final_labels.jsonl          # Merged final labels
  balanced/
    augmented.jsonl             # Augmented samples
    synthetic.jsonl             # Qwen-generated samples
  splits/
    train.jsonl                 # 80%
    val.jsonl                   # 10%
    test.jsonl                  # 10%
ml/
  aspects/
    stress_aspects.json         # Aspect definitions
scripts/
  data_cleaning.py              # Cleaning pipeline
  qwen_labeling.py              # Qwen batch labeling
  claude_validation.py          # Claude validation
  data_augmentation.py          # Augmentation
  dataset_splitting.py          # Train/val/test split
```

## Data Formats

### Cleaned Data
```json
{
  "post_id": "12345",
  "text": "Tôi cảm thấy rất áp lực với công việc hiện tại...",
  "text_hash": "abc123...",
  "char_count": 156,
  "cleaned_at": "2024-01-15T12:00:00Z"
}
```

### Qwen Labels
```json
{
  "post_id": "12345",
  "text": "...",
  "aspects": [0, 4, 5],
  "aspect_probs": [0.92, 0.15, 0.08, 0.05, 0.85, 0.78, 0.12, 0.03, 0.11, 0.22],
  "confidence": 0.85,
  "reasoning": "Bài viết đề cập đến áp lực deadline...",
  "model": "qwen2.5:7b",
  "labeled_at": "2024-01-15T14:00:00Z"
}
```

### Claude Validation
```json
{
  "post_id": "12345",
  "qwen_aspects": [0, 4, 5],
  "claude_aspects": [0, 4],
  "agreement": true,
  "disagreement_count": 1,
  "claude_reasoning": "Không thấy dấu hiệu trầm cảm rõ ràng...",
  "needs_review": false,
  "validated_at": "2024-01-15T16:00:00Z"
}
```

### Final Training Format
```json
{
  "text": "Tôi cảm thấy rất áp lực với công việc hiện tại...",
  "labels": [1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
  "source": "original"
}
```

## Commands

```bash
# Export from Cassandra
python scripts/export_from_cassandra.py --output data/raw/voz_exported.jsonl

# Clean data
python scripts/data_cleaning.py \
  --input data/raw/voz_exported.jsonl \
  --output data/cleaned/voz_cleaned.jsonl

# Label with Qwen
python scripts/qwen_labeling.py \
  --input data/cleaned/voz_cleaned.jsonl \
  --output data/labeled/qwen_labels.jsonl \
  --model qwen2.5:7b \
  --batch-size 10

# Validate with Claude
python scripts/claude_validation.py \
  --input data/labeled/qwen_labels.jsonl \
  --output data/labeled/claude_validation.jsonl \
  --sample-rate 0.2

# Balance dataset
python scripts/data_augmentation.py \
  --input data/labeled/final_labels.jsonl \
  --output data/balanced/

# Split dataset
python scripts/dataset_splitting.py \
  --input data/balanced/ \
  --output data/splits/ \
  --train 0.8 --val 0.1 --test 0.1
```

## Claude Validation Prompt

```
You are validating stress aspect labels for Vietnamese social media posts.

POST: {text}

QWEN LABELS: {aspects}
QWEN REASONING: {reasoning}

ASPECTS:
0: Work stress (Áp lực công việc)
1: Financial anxiety (Lo âu tài chính)
2: Relationship issues (Vấn đề tình cảm)
3: Academic pressure (Áp lực học tập)
4: Exhaustion (Kiệt sức)
5: Depression (Trầm cảm)
6: Loneliness (Cô đơn)
7: Health concerns (Lo lắng sức khỏe)
8: Family conflict (Mâu thuẫn gia đình)
9: Future uncertainty (Bất an tương lai)

TASK:
1. Review the post and Qwen's labels
2. Provide your own aspect labels (list of indices)
3. Note any disagreements with reasoning
4. Flag if human review needed

OUTPUT JSON:
{
  "claude_aspects": [...],
  "agreement": true/false,
  "disagreement_reason": "...",
  "needs_human_review": true/false
}
```

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Multi-aspect posts | Allow multiple labels (multi-label) |
| No stress detected | Label as empty array [] |
| Ambiguous text | Flag for human review |
| Sarcasm/irony | Include in validation prompt context |
| Code-mixed (Viet+Eng) | Keep as-is, PhoBERT handles |
| Slang/abbreviations | Keep as-is (common on VOZ) |
| Very long posts | Truncate to 512 tokens for labeling |
| Qwen timeout | Retry 3x, skip if fails |
| Claude rate limit | Exponential backoff |
| Class imbalance | Augment minority classes first |
| Near-duplicate texts | Dedupe by 90% text similarity |

## Validation Criteria

- [ ] Cleaned data: 10k+ posts
- [ ] All posts: 50-2000 chars
- [ ] No duplicates (by text hash)
- [ ] Qwen labels: 100% coverage
- [ ] Claude validation: 20% sample
- [ ] Inter-rater agreement: Kappa > 0.7
- [ ] Each aspect: >800 samples (>80% coverage)
- [ ] Splits sum to 100%
- [ ] Stratified distribution across splits

## Metrics to Track

```python
# After cleaning
{
  "total_raw": 12000,
  "after_cleaning": 10500,
  "removed_short": 800,
  "removed_long": 200,
  "removed_duplicates": 500
}

# After labeling
{
  "aspect_distribution": {
    "work_stress": 2100,
    "financial_anxiety": 1800,
    "relationship_issues": 2500,
    ...
  },
  "multi_label_avg": 1.8,
  "no_stress_count": 1200
}

# After validation
{
  "qwen_claude_agreement": 0.82,
  "cohens_kappa": 0.75,
  "needs_review": 150,
  "conflicts_resolved": 120
}
```
