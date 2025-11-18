#!/bin/bash

# =============================================================================
# Train Reddit Stress Detection Model V2 (using Ollama-labeled data)
# =============================================================================

set -e  # Exit on error

# Configuration
MODEL_TYPE="${1:-distilbert}"  # Default to distilbert, or use first argument

# Map model types to HuggingFace model names
case $MODEL_TYPE in
    "distilbert")
        MODEL_NAME="distilbert-base-uncased"
        MODEL_SUFFIX="distilbert"
        ;;
    "bert")
        MODEL_NAME="bert-base-uncased"
        MODEL_SUFFIX="bert"
        ;;
    "bert-large")
        MODEL_NAME="bert-large-uncased"
        MODEL_SUFFIX="bert_large"
        ;;
    "roberta")
        MODEL_NAME="roberta-base"
        MODEL_SUFFIX="roberta"
        ;;
    "roberta-large")
        MODEL_NAME="roberta-large"
        MODEL_SUFFIX="roberta_large"
        ;;
    "mental-bert")
        MODEL_NAME="mental/mental-bert-base-uncased"
        MODEL_SUFFIX="mental_bert"
        ;;
    *)
        echo "❌ Unknown model type: $MODEL_TYPE"
        echo ""
        echo "Available options:"
        echo "  distilbert      - DistilBERT (fast, recommended)"
        echo "  bert            - BERT Base"
        echo "  bert-large      - BERT Large (GPU recommended)"
        echo "  roberta         - RoBERTa Base"
        echo "  roberta-large   - RoBERTa Large (GPU recommended)"
        echo "  mental-bert     - Mental Health BERT"
        echo ""
        echo "Usage: ./train_reddit_stress_v2.sh [model_type]"
        echo "Example: ./train_reddit_stress_v2.sh roberta"
        exit 1
        ;;
esac

echo "======================================================================"
echo "TRAINING REDDIT STRESS DETECTION MODEL V2"
echo "Model: $MODEL_NAME"
echo "======================================================================"
echo ""

# Check if Ollama labeling is complete
LABELED_FILE="ml/dataset/labeled/reddit_crawl_ollama_labeled.csv"

if [ ! -f "$LABELED_FILE" ]; then
    echo "❌ Error: Ollama-labeled file not found at $LABELED_FILE"
    echo "   Please wait for labeling to complete first."
    exit 1
fi

# Count rows in labeled file
TOTAL_ROWS=$(wc -l < "$LABELED_FILE" | tr -d ' ')
echo "✓ Found labeled data: $LABELED_FILE"
echo "  Total rows (including header): $TOTAL_ROWS"
echo ""

# Step 1: Create train/val/test splits
echo "======================================================================"
echo "STEP 1: Creating train/val/test splits from Ollama-labeled data"
echo "======================================================================"
echo ""

# Use virtual environment if available
if [ -f "ml/.venv/bin/python" ]; then
    PYTHON="ml/.venv/bin/python"
    echo "Using virtual environment: ml/.venv"
else
    PYTHON="python3"
    echo "Using system Python"
fi

$PYTHON ml/dataset/create_splits_from_ollama.py \
    --input "$LABELED_FILE" \
    --output-dir ml/dataset/splits \
    --confidence HIGH \
    --train-ratio 0.7 \
    --val-ratio 0.15 \
    --test-ratio 0.15

echo ""
echo "✓ Splits created successfully!"
echo ""

# Step 2: Train the model
echo "======================================================================"
echo "STEP 2: Training model reddit_stress_v2_${MODEL_SUFFIX}"
echo "Using pre-trained model: $MODEL_NAME"
echo "======================================================================"
echo ""

$PYTHON ml/models/train.py \
    --data-dir ml/dataset/splits \
    --save-name reddit_stress_v2_${MODEL_SUFFIX} \
    --model-name "$MODEL_NAME" \
    --file-suffix _v2 \
    --epochs 3 \
    --batch-size 16 \
    --learning-rate 2e-5 \
    --max-length 512

echo ""
echo "======================================================================"
echo "✓ TRAINING COMPLETE!"
echo "======================================================================"
echo ""
echo "Model: $MODEL_NAME"
echo "Saved to: ml/models/reddit_stress_v2_${MODEL_SUFFIX}"
echo ""
echo "Next steps:"
echo "  1. Check model performance in the training output above"
echo "  2. Test the model with: python ml/models/test_model.py"
echo "  3. Use the model for inference on new data"
echo ""
echo "To train with a different BERT model:"
echo "  ./train_reddit_stress_v2.sh roberta"
echo "  ./train_reddit_stress_v2.sh bert"
echo "  ./train_reddit_stress_v2.sh bert-large"
echo ""
