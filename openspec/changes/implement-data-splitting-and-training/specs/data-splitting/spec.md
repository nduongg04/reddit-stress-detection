# Spec: Data Splitting

## Capability
Multi-label stratified dataset splitting for Vietnamese stress detection.

## ADDED Requirements

### Requirement: Multi-label Stratified Splitting
The system SHALL split labeled data into train/val/test sets using iterative stratification to maintain aspect distribution.

#### Scenario: Standard split with sufficient data
**Given** `data/labeled/llm_outputs_v1.jsonl` with ≥500 labeled posts
**When** running `scripts/dataset_splitting.py`
**Then** creates:
- `data/splits/train_v1.jsonl` (70% of data)
- `data/splits/val_v1.jsonl` (15% of data)
- `data/splits/test_v1.jsonl` (15% of data)
**And** aspect frequency deviation <5% across all splits

#### Scenario: Handling imbalanced aspects
**Given** aspect 9 has only 90 positive samples
**When** splitting data
**Then** each split contains proportional samples of aspect 9
**And** logs warning if any aspect has <10 samples in a split

### Requirement: Gold Set Sampling
The system SHALL sample a gold calibration set for human verification.

#### Scenario: Standard gold sampling
**Given** 719 posts with aspects across 10 categories
**When** sampling gold set
**Then** creates `data/gold/gold_v1.csv` with 100 posts (10 per aspect)
**And** prefers medium-confidence posts (0.6-0.79)
**And** excludes gold posts from train/val/test splits

#### Scenario: Insufficient samples for an aspect
**Given** aspect has <10 medium-confidence posts
**When** sampling gold set
**Then** takes all available medium-confidence posts
**And** fills remainder from high-confidence posts
**And** logs exception to `reports/gold_sampling_exceptions.json`

### Requirement: Test Set Protection
The system SHALL protect test set from accidental modification.

#### Scenario: Test set immutability
**Given** test split is created
**When** setting permissions
**Then** `data/splits/test_v1.jsonl` is chmod 444 (read-only)
**And** `data/splits/.immutable` marker file exists

## Input Format
```json
{"post_id": "1030024", "text": "...", "aspects": [0, 2, 5], "aspect_confidences": [...], "confidence": 0.85}
```

## Output Format
```json
{"post_id": "1030024", "text": "...", "aspects": [0, 2, 5], "confidence": 0.85, "split": "train"}
```
