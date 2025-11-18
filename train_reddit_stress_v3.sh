#!/bin/bash

# Training script for Reddit Stress Detection Model v3
# Includes improvements for imbalanced dataset handling

set -e  # Exit on error

echo "======================================"
echo "Reddit Stress Detection - Training v3"
echo "======================================"
echo ""
echo "Improvements in this version:"
echo "  ✓ Class weighting for imbalanced data"
echo "  ✓ Data augmentation for minority class"
echo "  ✓ Increased epochs (5 instead of 3)"
echo "  ✓ Adjusted learning rate (3e-5)"
echo "  ✓ Early stopping with patience=3"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠ Virtual environment not activated!"
    echo "Please run: source .venv/bin/activate"
    exit 1
fi

# Check for GPU
echo "Checking GPU availability..."
python3 ml/models/check_gpu.py

# GPU will be auto-detected by PyTorch (MPS on Mac, CUDA on Linux/Windows)
# No need to specify --cpu flag unless you want to force CPU usage
USE_GPU=""

echo ""
echo "Note: Training will automatically use:"
echo "  - MPS (Apple Silicon GPU) if available on Mac"
echo "  - CUDA (NVIDIA GPU) if available"
echo "  - CPU as fallback"
echo ""

echo ""
echo "Starting training..."
echo ""

# Train the model with improved settings
python ml/models/train.py \
    --file-suffix "_v2" \
    --save-name "reddit_stress_v3" \
    --epochs 5 \
    --batch-size 16 \
    --learning-rate 3e-5 \
    --balance-data \
    --balance-ratio 0.4 \
    $USE_GPU

echo ""
echo "======================================"
echo "Training Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Test the model: python ml/models/test_model.py"
echo "  2. Check metrics in: ml/models/reddit_stress_v3/metadata.json"
echo ""
