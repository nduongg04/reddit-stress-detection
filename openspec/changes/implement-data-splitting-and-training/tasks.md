# Tasks: Implement Data Splitting and PhoBERT Training

## Phase 1: Data Splitting

### 1.1 Create splitting script
- [ ] Create `scripts/dataset_splitting.py`
- [ ] Load `data/labeled/llm_outputs_v1.jsonl`
- [ ] Filter posts with at least one aspect (719 posts)
- [ ] Install `scikit-multilearn` for `iterative_stratification`

### 1.2 Implement stratified splitting
- [ ] Convert aspects list to binary matrix (N×10)
- [ ] Apply `iterative_train_test_split` for 70/30 train/temp
- [ ] Apply again for 50/50 val/test from temp
- [ ] Verify aspect frequency deviation <5% across splits

### 1.3 Gold set sampling
- [ ] Sample 10 posts per aspect (100 total)
- [ ] Prefer medium-confidence posts (0.6-0.79) for manual review
- [ ] Exclude gold posts from train/val/test
- [ ] Log any aspects with insufficient posts

### 1.4 Output splits
- [ ] Create `data/splits/` directory
- [ ] Write `train_v1.jsonl`, `val_v1.jsonl`, `test_v1.jsonl`
- [ ] Write `data/gold/gold_v1.csv` with annotation columns
- [ ] Make test set read-only (chmod 444)

## Phase 2: PhoBERT Training

### 2.1 Adapt training script
- [ ] Copy `ml/models/train_absa_phobert.py` as base
- [ ] Update `load_data()` to read from JSONL splits
- [ ] Add aspect configuration from `config/aspects_v1.json`

### 2.2 Implement class weighting
- [ ] Compute `pos_weight` per aspect: `total / (10 * positive_count)`
- [ ] Pass weights to `BCEWithLogitsLoss`
- [ ] Verify weights are reasonable (log them)

### 2.3 Training configuration
- [ ] Set hyperparameters: lr=2e-5, batch=16, max_len=256
- [ ] Configure early stopping: patience=3, monitor val_loss
- [ ] Set random seed=42 for reproducibility

### 2.4 Model output
- [ ] Save to `ml/models/phobert_stress_v2/`
- [ ] Export `model.pt`, `config.json`, `metadata.json`
- [ ] Include in metadata: dataset_version, split_hash, training_time

## Validation

### V1. Data integrity
- [ ] Total posts = train + val + test + gold (no overlap)
- [ ] Aspect frequency deviation <5% in each split
- [ ] Gold set has 10 posts per aspect (or documented exception)

### V2. Model quality
- [ ] Training completes without OOM
- [ ] Val loss decreases over epochs
- [ ] Checkpoint saved each epoch

## Dependencies Graph
```
1.1 → 1.2 → 1.3 → 1.4 (sequential)
         ↓
       2.1 → 2.2 → 2.3 → 2.4 (sequential)
```

## Parallelizable Work
- None (tasks are sequential due to data dependencies)
