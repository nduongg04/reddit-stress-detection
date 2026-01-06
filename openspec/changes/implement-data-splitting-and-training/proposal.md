# Proposal: Implement Data Splitting and PhoBERT Training

## Change ID
`implement-data-splitting-and-training`

## Problem Statement
The LLM labeling pipeline has produced `data/labeled/llm_outputs_v1.jsonl` with 920 posts (719 with aspects). To train a production PhoBERT model, we need:
1. Stratified train/val/test splits for multi-label classification
2. A gold calibration set for human verification
3. A trained PhoBERT model with proper class weighting

## Current State
- **Input data:** `data/labeled/llm_outputs_v1.jsonl` (920 posts, 719 with aspects)
- **Aspect distribution:** [512, 332, 410, 400, 388, 305, 188, 131, 158, 90] (highly imbalanced)
- **Existing model:** `ml/models/train_absa_phobert.py` exists but uses different data format
- **Aspect schema:** `config/aspects_v1.json` defines 10 mental health aspects

## Proposed Solution

### Phase 1: Data Splitting (Sprint 5 simplified)
Given limited data (920 posts vs expected 8,500), adapt the splitting strategy:
- **Train:** 70% (~644 posts)
- **Val:** 15% (~138 posts)
- **Test:** 15% (~138 posts)
- **Gold set:** 100 posts (10 per aspect) sampled from medium-confidence posts
- Use `iterative_stratification` from `scikit-multilearn` for multi-label stratification

### Phase 2: PhoBERT Training (Sprint 6)
Adapt existing `train_absa_phobert.py`:
- Load from JSONL splits
- Add class weights based on aspect frequency
- Configure BCEWithLogitsLoss with pos_weight
- Save model with full metadata (dataset version, training config)

## Scope

### In Scope
- Multi-label stratified splitting script
- Gold set sampling with per-aspect quotas
- PhoBERT training with class weighting
- Model metadata and versioning

### Out of Scope
- Human annotation workflow (deferred)
- Comprehensive evaluation metrics (Sprint 7)
- Real-time inference integration

## Dependencies
- Completed: `add-llm-labeling-pipeline` (provides input data)
- Completed: `clean-data-and-define-aspects` (provides aspect schema)

## Risks
| Risk | Mitigation |
|------|------------|
| Limited data (920 vs 8,500 expected) | Adjust split ratios; use data augmentation if needed |
| Aspect imbalance (90-512 range) | Use class weights in loss function |
| Existing model format mismatch | Adapt data loader in training script |

## Success Criteria
- [ ] Stratified splits created with <5% aspect frequency deviation
- [ ] Gold set with 10 posts per aspect (100 total)
- [ ] PhoBERT model trained with val_loss tracked
- [ ] Model saved with metadata.json including dataset version
