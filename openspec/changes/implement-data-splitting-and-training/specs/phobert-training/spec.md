# Spec: PhoBERT Training

## Capability
Train multi-label PhoBERT classifier for Vietnamese stress detection.

## ADDED Requirements

### Requirement: Model Architecture
The system SHALL use PhoBERT-base-v2 with a multi-label classification head.

#### Scenario: Model initialization
**Given** HuggingFace model `vinai/phobert-base-v2`
**When** initializing classifier
**Then** loads 768-dim hidden state encoder
**And** adds classification head: Linear(768→256) → ReLU → Dropout(0.3) → Linear(256→10) → Sigmoid

### Requirement: Class Imbalance Handling
The system SHALL compute per-aspect class weights to handle imbalanced data.

#### Scenario: Computing class weights
**Given** training set with aspect distribution [512, 332, 410, 400, 388, 305, 188, 131, 158, 90]
**When** computing weights
**Then** `pos_weight[k] = total_samples / (10 * positive_samples[k])`
**And** weights are clamped to range [0.5, 10.0] to prevent extreme values
**And** weights are logged before training

#### Scenario: Applying weights to loss
**Given** computed pos_weights
**When** configuring loss function
**Then** uses `BCEWithLogitsLoss(pos_weight=weights)`

### Requirement: Training Configuration
The system SHALL use standardized hyperparameters and early stopping.

#### Scenario: Standard training run
**Given** train_v1.jsonl and val_v1.jsonl
**When** training
**Then** uses:
- Optimizer: AdamW, lr=2e-5, weight_decay=0.01
- Batch size: 16
- Max sequence length: 256 tokens
- Max epochs: 10
- Early stopping: patience=3, monitor val_loss, min_delta=0.001
- Random seed: 42

### Requirement: Model Versioning
The system SHALL save trained models with full metadata.

#### Scenario: Saving trained model
**Given** training completes successfully
**When** saving model
**Then** creates `ml/models/phobert_stress_v2/`:
- `model.pt` (state_dict only)
- `config.json` (architecture config)
- `metadata.json` (training metadata)

#### Scenario: Metadata content
**Given** model is saved
**When** inspecting metadata.json
**Then** contains:
- `dataset_version`: "v1"
- `aspects_version`: "v1"
- `train_samples`: count
- `val_samples`: count
- `hyperparams`: {lr, batch_size, max_len, epochs, patience}
- `seed`: 42
- `best_epoch`: int
- `best_val_loss`: float
- `training_time_seconds`: float
- `class_weights`: list[10]

## Dependencies
- Input: `data/splits/train_v1.jsonl`, `data/splits/val_v1.jsonl`
- Config: `config/aspects_v1.json`
- Base model: `vinai/phobert-base-v2` (HuggingFace)
