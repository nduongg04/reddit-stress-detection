# Reddit Stress Detection - Model Training

**Version**: 1.0.0
**Task**: TASK-019 - Model Selection & Fine-Tuning
**Created**: 2025-10-12

---

## Overview

This directory contains the model training pipeline for Reddit stress detection. The system uses a fine-tuned DistilBERT model for binary classification of stress-related content.

---

## Quick Start

### 1. Install Dependencies

```bash
cd ml/models
pip install -r requirements.txt
```

### 2. Prepare Dataset

You need labeled data in `ml/dataset/splits/` from TASK-018.

If you don't have real data yet, create sample data for testing:

```bash
python data_loader.py --create-sample
```

### 3. Train Model

```bash
# Basic training (with sample data)
python train.py --create-sample-data

# Full training on real data
python train.py \
    --data-dir ml/dataset/splits \
    --epochs 3 \
    --batch-size 16 \
    --learning-rate 2e-5
```

### 4. Evaluate Model

```bash
python evaluate.py --model-path ml/models/reddit_stress_v1
```

### 5. Test Model

```bash
# Interactive testing
python test_model.py --interactive

# Batch test on examples
python test_model.py --batch

# Single prediction
python test_model.py --text "I'm feeling so overwhelmed with work"
```

---

## Directory Structure

```
ml/models/
├── checkpoints/              # Training checkpoints
├── registry/                 # Model registry
│   ├── v1/                   # Version 1 models
│   │   └── metadata.json     # Model metadata
│   └── metadata/             # Additional metadata
├── logs/                     # Training logs
├── reddit_stress_v1/         # Saved model (after training)
│   ├── config.json           # Model configuration
│   ├── pytorch_model.bin     # Model weights
│   ├── tokenizer_config.json # Tokenizer config
│   ├── vocab.txt             # Vocabulary
│   ├── metadata.json         # Training metadata
│   └── evaluation/           # Evaluation results
│       ├── confusion_matrix.png
│       ├── roc_curve.png
│       └── evaluation_results.json
├── data_loader.py            # Dataset loading utilities
├── train.py                  # Training script
├── evaluate.py               # Evaluation utilities
├── test_model.py             # Interactive testing
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## Model Architecture

### Base Model
- **Model**: DistilBERT (`distilbert-base-uncased`)
- **Parameters**: ~66M (smaller, faster than BERT)
- **Architecture**: 6-layer Transformer with 768 hidden dimensions
- **Max Sequence Length**: 512 tokens

### Fine-tuning
- **Task**: Binary sequence classification
- **Classes**:
  - 0 = NON_STRESS
  - 1 = STRESS
- **Loss**: Cross-entropy loss
- **Optimizer**: AdamW with weight decay

---

## Training Configuration

### Default Hyperparameters

```python
{
    "model_name": "distilbert-base-uncased",
    "num_epochs": 3,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "weight_decay": 0.01,
    "max_length": 512,
    "warmup_steps": 100,
    "early_stopping_patience": 2
}
```

### Target Metrics

The model should achieve:
- **Accuracy**: ≥0.80 (80%)
- **Precision**: ≥0.82 (82%)
- **Recall**: ≥0.85 (85%)
- **F1 Score**: ≥0.83 (83%)

---

## Scripts

### 1. data_loader.py

Dataset loading and preprocessing utilities.

**Features**:
- Load train/val/test splits
- Convert labels to binary format
- Compute dataset statistics
- Create sample dataset for testing

**Usage**:
```bash
# Create sample dataset
python data_loader.py --create-sample

# Test data loading
python data_loader.py
```

### 2. train.py

Main training script.

**Features**:
- Fine-tune DistilBERT on stress detection
- Track training metrics
- Early stopping based on validation F1
- Save model with metadata
- Model versioning

**Usage**:
```bash
# Basic training
python train.py

# Custom configuration
python train.py \
    --epochs 5 \
    --batch-size 32 \
    --learning-rate 3e-5 \
    --save-name reddit_stress_v2

# Train on CPU
python train.py --cpu

# Create sample data and train
python train.py --create-sample-data
```

**Output**:
- Model saved to `ml/models/{save_name}/`
- Metadata in `metadata.json`
- Checkpoints in `ml/models/checkpoints/`
- Registry entry in `ml/models/registry/v1/`

### 3. evaluate.py

Model evaluation utilities.

**Features**:
- Evaluate on test set
- Generate classification report
- Plot confusion matrix and ROC curve
- Test inference speed
- Save evaluation results

**Usage**:
```bash
# Evaluate model
python evaluate.py

# Custom model path
python evaluate.py --model-path ml/models/reddit_stress_v2

# Skip plots
python evaluate.py --no-plot
```

**Output**:
- Prints detailed metrics
- Saves plots to `{model_path}/evaluation/`
- Saves results to `evaluation_results.json`

### 4. test_model.py

Interactive model testing.

**Features**:
- Interactive mode for manual testing
- Batch testing on examples
- Single text prediction
- Confidence scores

**Usage**:
```bash
# Interactive mode
python test_model.py --interactive

# Batch test
python test_model.py --batch

# Single prediction
python test_model.py --text "I'm so stressed about finals"
```

---

## Training Pipeline

### Step 1: Data Preparation

Ensure you have labeled data from TASK-018:
```bash
ls ml/dataset/splits/
# Should show: train.csv, val.csv, test.csv
```

Or create sample data:
```bash
python data_loader.py --create-sample
```

### Step 2: Train Model

```bash
python train.py --epochs 3 --batch-size 16
```

**What happens**:
1. Loads dataset from splits
2. Initializes DistilBERT model
3. Tokenizes all texts
4. Fine-tunes for N epochs
5. Evaluates on validation set
6. Saves best model based on F1 score
7. Tests on test set
8. Saves model and metadata

**Training time**:
- Sample data (1000 samples): ~5-10 minutes on CPU
- Real data (10k+ samples): ~30-60 minutes on GPU, 2-4 hours on CPU

### Step 3: Evaluate Model

```bash
python evaluate.py
```

**Output**:
- Accuracy, precision, recall, F1, AUC
- Confusion matrix
- ROC curve
- Inference speed test
- Saved plots and results

### Step 4: Test Model

```bash
python test_model.py --interactive
```

Test the model on custom inputs to verify it works as expected.

---

## Model Metadata

Each trained model includes metadata in `metadata.json`:

```json
{
  "version": "1.0.0",
  "model_name": "distilbert-base-uncased",
  "training_date": "2025-10-12T10:30:00",
  "training_samples": 7000,
  "validation_samples": 1500,
  "test_samples": 1500,
  "hyperparameters": {
    "num_epochs": 3,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "max_length": 512
  },
  "metrics": {
    "test_accuracy": 0.85,
    "test_precision": 0.84,
    "test_recall": 0.87,
    "test_f1": 0.86
  },
  "targets_met": true,
  "dataset_version": "1.0.0"
}
```

---

## Model Registry

Models are versioned and stored in the registry:

```
ml/models/registry/
├── v1/
│   ├── metadata.json
│   └── (model files symlinked or copied)
├── v2/
│   └── ...
└── metadata/
    └── version_history.json
```

---

## Integration with Spark

Once trained, integrate the model with Spark streaming (TASK-020):

```python
from transformers import pipeline

# Load model
model = pipeline("text-classification", model="ml/models/reddit_stress_v1")

# Use in PandasUDF
@pandas_udf("struct<label:string, score:double>")
def predict_stress(texts):
    results = model(texts.tolist(), batch_size=32)
    return pd.DataFrame({
        'label': [r['label'] for r in results],
        'score': [r['score'] for r in results]
    })
```

---

## Performance Targets

### Inference Speed
- **Target**: <100ms per post
- **Batch size**: 32 for optimal throughput
- **Device**: CPU acceptable, GPU recommended for production

### Model Quality
- **Minimum F1**: 0.83
- **Production threshold**: 0.85+
- **Retraining trigger**: F1 drops below 0.80

---

## Troubleshooting

### Issue: Out of memory during training

**Solution**:
```bash
# Reduce batch size
python train.py --batch-size 8

# Use gradient accumulation (not implemented yet)
# Or train on machine with more RAM/GPU memory
```

### Issue: Model not converging

**Solution**:
```bash
# Increase epochs
python train.py --epochs 5

# Adjust learning rate
python train.py --learning-rate 3e-5

# Check dataset quality
python data_loader.py  # Review statistics
```

### Issue: No dataset found

**Solution**:
```bash
# Create sample data for testing
python train.py --create-sample-data

# Or prepare real dataset (TASK-018)
cd ml/dataset
python scripts/prepare_dataset.py
```

### Issue: Poor performance on test set

**Possible causes**:
- Dataset too small or imbalanced
- Need more training epochs
- Hyperparameters need tuning
- Dataset quality issues

**Solution**:
```bash
# Check dataset statistics
python data_loader.py

# Try different hyperparameters
python train.py --epochs 5 --learning-rate 3e-5

# Collect more/better labeled data (TASK-018)
```

---

## Next Steps

After completing TASK-019:

1. **TASK-020**: Deploy model to Spark streaming
2. **TASK-021**: Set up model versioning and registry
3. **TASK-022**: Create Airflow DAG for automated training
4. **TASK-033**: Implement model drift detection

---

## References

- **DistilBERT Paper**: [Sanh et al., 2019](https://arxiv.org/abs/1910.01108)
- **Hugging Face Transformers**: https://huggingface.co/docs/transformers
- **PyTorch**: https://pytorch.org/docs/stable/index.html

---

## Notes

- Model files (~250MB) are not committed to git
- Use DVC or git-lfs for model versioning in production
- Always validate model on test set before deployment
- Monitor model performance in production (drift detection)
- Retrain periodically with new labeled data

---

## Support

For issues or questions:
1. Check this README
2. Review `tasks/detailed/task019.md`
3. Check training logs in `ml/models/logs/`
4. Test with sample data first

---

**Created as part of TASK-019: Model Selection & Fine-Tuning**
