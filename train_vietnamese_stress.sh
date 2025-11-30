#!/bin/bash

# Train Vietnamese Stress Detection Model (PhoBERT)
# Optimized for maximum accuracy with Vietnamese data

set -e  # Exit on error

echo "======================================================================"
echo "Vietnamese Stress Detection Model Training (PhoBERT)"
echo "======================================================================"
echo ""

# Configuration
MODEL_NAME="vinai/phobert-base-v2"
SAVE_NAME="vietnamese_stress_phobert"
DATA_DIR="ml/dataset/splits"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/vietnamese_training.log"

# Hyperparameters (optimized for PhoBERT)
EPOCHS=5
BATCH_SIZE=16
LEARNING_RATE=2e-5  # PhoBERT sweet spot (lower than DistilBERT's 3e-5)
MAX_LENGTH=256      # Vietnamese posts are typically shorter
BALANCE_RATIO=0.5   # 50:50 balance
FOCAL_GAMMA=2.5     # Focus on hard examples

# Create log directory
mkdir -p "$LOG_DIR"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠ Virtual environment not active. Activating..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        echo "✓ Activated .venv"
    elif [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo "✓ Activated venv"
    else
        echo "✗ No virtual environment found (.venv or venv)"
        echo "Create one with: python3 -m venv .venv"
        exit 1
    fi
fi

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if required packages are installed
echo "Checking required packages..."
python -c "import torch; import transformers; import sklearn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ Required packages not found. Installing..."
    pip install -r requirements.txt
fi

# Check for GPU/MPS
echo ""
echo "Checking compute device..."
python -c "
import torch
if torch.cuda.is_available():
    print(f'✓ CUDA GPU detected: {torch.cuda.get_device_name(0)}')
elif torch.backends.mps.is_available():
    print('✓ MPS (Apple Silicon GPU) detected')
else:
    print('⚠ No GPU detected - training will use CPU (slower)')
"

# Check if dataset exists
echo ""
echo "Checking Vietnamese dataset..."
if [ ! -f "$DATA_DIR/vietnamese_train.csv" ]; then
    echo "✗ Vietnamese dataset not found!"
    echo ""
    echo "Please run the dataset pipeline first:"
    echo "  1. Export from Cassandra: python scripts/export_vietnamese_from_cassandra.py"
    echo "  2. Label with Ollama: python ml/dataset/label_vietnamese_with_ollama.py"
    echo "  3. Review (optional): python ml/dataset/review_low_confidence.py"
    echo "  4. Create splits: python ml/dataset/create_vietnamese_splits.py"
    exit 1
fi

# Count samples
TRAIN_COUNT=$(tail -n +2 "$DATA_DIR/vietnamese_train.csv" | wc -l | tr -d ' ')
VAL_COUNT=$(tail -n +2 "$DATA_DIR/vietnamese_val.csv" | wc -l | tr -d ' ')
TEST_COUNT=$(tail -n +2 "$DATA_DIR/vietnamese_test.csv" | wc -l | tr -d ' ')

echo "✓ Dataset found:"
echo "  Train: $TRAIN_COUNT samples"
echo "  Val:   $VAL_COUNT samples"
echo "  Test:  $TEST_COUNT samples"

# Check if model directory already exists
if [ -d "ml/models/$SAVE_NAME" ]; then
    echo ""
    echo "⚠ Model directory 'ml/models/$SAVE_NAME' already exists!"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Training cancelled."
        exit 0
    fi
    echo "Removing existing model..."
    rm -rf "ml/models/$SAVE_NAME"
fi

# Display training configuration
echo ""
echo "======================================================================"
echo "Training Configuration"
echo "======================================================================"
echo "Model: $MODEL_NAME"
echo "Save to: ml/models/$SAVE_NAME"
echo ""
echo "Hyperparameters:"
echo "  Epochs: $EPOCHS"
echo "  Batch size: $BATCH_SIZE"
echo "  Learning rate: $LEARNING_RATE"
echo "  Max sequence length: $MAX_LENGTH"
echo "  Balance ratio: $BALANCE_RATIO (50:50)"
echo "  Focal loss gamma: $FOCAL_GAMMA"
echo ""
echo "Optimizations:"
echo "  ✓ Vietnamese-specific augmentation"
echo "  ✓ Class balancing with oversampling"
echo "  ✓ Focal loss for hard examples"
echo "  ✓ Class weighting"
echo "  ✓ Early stopping (patience=3)"
echo ""
echo "Log file: $LOG_FILE"
echo "======================================================================"
echo ""

# Confirm before training
read -p "Start training? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Training cancelled."
    exit 0
fi

# Start training
echo ""
echo "======================================================================"
echo "Starting Training..."
echo "======================================================================"
echo ""
echo "Training logs will be saved to: $LOG_FILE"
echo "You can monitor progress with: tail -f $LOG_FILE"
echo ""

# Record start time
START_TIME=$(date +%s)

# Run training with all optimizations enabled
python ml/models/train.py \
    --model-name "$MODEL_NAME" \
    --save-name "$SAVE_NAME" \
    --data-dir "$DATA_DIR" \
    --file-suffix "" \
    --epochs "$EPOCHS" \
    --batch-size "$BATCH_SIZE" \
    --learning-rate "$LEARNING_RATE" \
    --max-length "$MAX_LENGTH" \
    --balance-data \
    --balance-ratio "$BALANCE_RATIO" \
    --focal-loss \
    --focal-gamma "$FOCAL_GAMMA" \
    --language vietnamese \
    2>&1 | tee "$LOG_FILE"

# Record end time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "======================================================================"
echo "Training Complete!"
echo "======================================================================"
echo "Duration: ${MINUTES}m ${SECONDS}s"
echo "Model saved to: ml/models/$SAVE_NAME"
echo "Log file: $LOG_FILE"
echo ""

# Check if model was created successfully
if [ -f "ml/models/$SAVE_NAME/config.json" ]; then
    echo "✓ Model files verified:"
    ls -lh "ml/models/$SAVE_NAME/"
    echo ""

    # Extract metrics from metadata if available
    if [ -f "ml/models/$SAVE_NAME/metadata.json" ]; then
        echo "Model Performance (from metadata.json):"
        python -c "
import json
with open('ml/models/$SAVE_NAME/metadata.json', 'r') as f:
    metadata = json.load(f)
    metrics = metadata.get('metrics', {})
    print(f\"  Test Accuracy:  {metrics.get('test_accuracy', 0):.4f}\")
    print(f\"  Test Precision: {metrics.get('test_precision', 0):.4f}\")
    print(f\"  Test Recall:    {metrics.get('test_recall', 0):.4f}\")
    print(f\"  Test F1 Score:  {metrics.get('test_f1', 0):.4f}\")
    print()
    if metadata.get('targets_met', False):
        print('  ✓ Model meets all target metrics!')
    else:
        print('  ⚠ Model does not meet all target metrics.')
        print('  Consider collecting more data or adjusting hyperparameters.')
"
    fi

    echo ""
    echo "Next steps:"
    echo "  1. Test model: ./test_vietnamese_model.sh"
    echo "  2. Update Spark: Update spark/model_inference.py to use this model"
    echo "  3. Deploy: Update run.sh to validate vietnamese_stress_phobert"
else
    echo "✗ Error: Model files not found. Check logs for errors."
    exit 1
fi

echo "======================================================================"
