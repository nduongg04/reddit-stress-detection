# Phase 3: Model Training

## Goal
Fine-tune PhoBERT-base for multi-label stress aspect classification with Claude validation.

## Pipeline
```
data/splits/ → PhoBERT Fine-tune → Evaluate → Claude Test Validation → Export ONNX
```

## Tasks

### 3.1 Environment Setup
- [ ] Install transformers, torch, underthesea
- [ ] Download vinai/phobert-base
- [ ] Configure GPU/MPS training

### 3.2 Dataset Loading
- [ ] Custom PyTorch Dataset class
- [ ] PhoBERT tokenizer (max_length=256)
- [ ] Multi-label binary encoding

### 3.3 Model Architecture
- [ ] PhoBERT + classification head
- [ ] 10-output sigmoid (multi-label)
- [ ] Dropout for regularization

### 3.4 Training Loop
- [ ] Loss: BCEWithLogitsLoss
- [ ] Optimizer: AdamW
- [ ] Scheduler: linear warmup + decay
- [ ] Early stopping on val loss

### 3.5 Evaluation
- [ ] Metrics: F1 (micro/macro), precision, recall
- [ ] Per-aspect breakdown
- [ ] Confusion matrix per aspect
- [ ] Threshold optimization

### 3.6 Claude Test Validation
- [ ] Sample 100 test predictions
- [ ] Compare PhoBERT vs ground truth vs Claude
- [ ] Error analysis report
- [ ] Identify systematic errors

### 3.7 Model Export
- [ ] Save PyTorch checkpoint
- [ ] Export to ONNX for Spark
- [ ] Verify ONNX inference

## Model Architecture

```python
class PhoBERTStressClassifier(nn.Module):
    def __init__(self, num_aspects=10, dropout=0.3):
        super().__init__()
        self.phobert = AutoModel.from_pretrained("vinai/phobert-base")
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(768, num_aspects)

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(input_ids, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        pooled = self.dropout(pooled)
        logits = self.classifier(pooled)
        return logits  # Apply sigmoid during inference
```

## Training Config

```yaml
# File: ml/training/config.yaml
model:
  name: vinai/phobert-base
  num_aspects: 10
  max_length: 256
  dropout: 0.3

training:
  batch_size: 16
  epochs: 10
  learning_rate: 2e-5
  weight_decay: 0.01
  warmup_ratio: 0.1
  gradient_accumulation: 2

early_stopping:
  patience: 3
  min_delta: 0.001
  monitor: val_f1_macro

thresholds:
  default: 0.5
  per_aspect: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
```

## Files Structure

```
ml/
  training/
    train_phobert.py            # Main training script
    config.yaml                 # Hyperparameters
    dataset.py                  # PyTorch Dataset
    model.py                    # Model architecture
    metrics.py                  # Evaluation metrics
    utils.py                    # Helpers
  evaluation/
    evaluate_model.py           # Full evaluation
    claude_validation.py        # Claude test validation
    error_analysis.py           # Error patterns
  checkpoints/
    phobert_stress_v1/          # Saved model
      config.json
      pytorch_model.bin
      tokenizer/
  exports/
    phobert_stress.onnx         # ONNX export
    label_encoder.json          # Aspect mapping
reports/
  training_metrics.json         # Training curves
  evaluation_v1.json            # Final metrics
  claude_validation_report.json # Claude analysis
  error_analysis.json           # Error patterns
```

## Training Script

```bash
# Train model
python ml/training/train_phobert.py \
  --train data/splits/train.jsonl \
  --val data/splits/val.jsonl \
  --config ml/training/config.yaml \
  --output ml/checkpoints/phobert_stress_v1

# Evaluate
python ml/evaluation/evaluate_model.py \
  --model ml/checkpoints/phobert_stress_v1 \
  --test data/splits/test.jsonl \
  --output reports/evaluation_v1.json

# Claude validation on test set
python ml/evaluation/claude_validation.py \
  --model ml/checkpoints/phobert_stress_v1 \
  --test data/splits/test.jsonl \
  --sample 100 \
  --output reports/claude_validation_report.json

# Export to ONNX
python ml/training/export_onnx.py \
  --model ml/checkpoints/phobert_stress_v1 \
  --output ml/exports/phobert_stress.onnx
```

## Claude Test Validation Prompt

```
You are validating PhoBERT stress classification predictions.

POST: {text}

GROUND TRUTH LABELS: {true_labels}
PHOBERT PREDICTIONS: {pred_labels} (probs: {pred_probs})

ASPECTS:
0: Work stress, 1: Financial anxiety, 2: Relationship issues
3: Academic pressure, 4: Exhaustion, 5: Depression
6: Loneliness, 7: Health concerns, 8: Family conflict
9: Future uncertainty

TASK:
1. Are PhoBERT's predictions correct?
2. What did it miss or incorrectly predict?
3. Why might the model have made this error?
4. Suggest improvements

OUTPUT JSON:
{
  "correct": true/false,
  "missed_aspects": [...],
  "false_positives": [...],
  "error_type": "threshold|context|ambiguous|none",
  "analysis": "...",
  "suggested_fix": "..."
}
```

## Expected Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| F1 Macro | > 0.75 | 0.70 |
| F1 Micro | > 0.80 | 0.75 |
| Precision (avg) | > 0.75 | 0.70 |
| Recall (avg) | > 0.75 | 0.70 |
| Per-aspect F1 | > 0.70 | 0.65 |

## Per-Aspect Targets

| Aspect | F1 Target | Notes |
|--------|-----------|-------|
| work_stress | 0.78 | High data availability |
| financial_anxiety | 0.75 | Clear keywords |
| relationship_issues | 0.80 | Most common |
| academic_pressure | 0.76 | Student-heavy forum |
| exhaustion | 0.72 | Often co-occurs |
| depression | 0.70 | Harder to detect |
| loneliness | 0.72 | Subtle signals |
| health_concerns | 0.74 | Clear indicators |
| family_conflict | 0.73 | Context-dependent |
| future_uncertainty | 0.70 | Abstract concept |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| GPU OOM | Reduce batch_size, use gradient accumulation |
| Overfitting | Early stopping, increase dropout |
| Class imbalance | Weighted loss, focal loss |
| Long texts | Truncate to 256 tokens |
| Very short texts | Pad to min length |
| All-zero labels | Valid (no stress detected) |
| All-one labels | Rare but valid (multi-stress) |
| Threshold sensitivity | Per-aspect threshold tuning |
| ONNX export fails | Trace with dummy input |
| MPS (Apple Silicon) | Use torch.device("mps") |

## Training Monitoring

```python
# Metrics to log per epoch
{
  "epoch": 1,
  "train_loss": 0.45,
  "val_loss": 0.38,
  "val_f1_macro": 0.72,
  "val_f1_micro": 0.78,
  "learning_rate": 1.8e-5,
  "per_aspect_f1": {
    "work_stress": 0.75,
    "financial_anxiety": 0.71,
    ...
  }
}
```

## Validation Criteria

- [ ] Training completes without OOM
- [ ] Val loss decreases over epochs
- [ ] No overfitting (train/val gap < 0.1)
- [ ] F1 Macro > 0.70 on test set
- [ ] All aspects F1 > 0.65
- [ ] ONNX export loads correctly
- [ ] ONNX inference matches PyTorch
- [ ] Claude validation agreement > 80%
- [ ] Error analysis identifies < 5 systematic issues

## ONNX Export Verification

```python
# Verify ONNX matches PyTorch
import onnxruntime as ort
import torch

# PyTorch inference
with torch.no_grad():
    pt_output = model(input_ids, attention_mask)

# ONNX inference
session = ort.InferenceSession("phobert_stress.onnx")
onnx_output = session.run(None, {
    "input_ids": input_ids.numpy(),
    "attention_mask": attention_mask.numpy()
})

# Compare
assert np.allclose(pt_output.numpy(), onnx_output[0], atol=1e-5)
```
