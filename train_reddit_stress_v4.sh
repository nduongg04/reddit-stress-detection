#!/bin/bash

# Training script for Reddit Stress Detection Model v4
# AGGRESSIVE improvements for extreme class imbalance (84% vs 16%)

set -e  # Exit on error

echo "======================================"
echo "Reddit Stress Detection - Training v4"
echo "======================================"
echo ""
echo "🚀 AGGRESSIVE IMPROVEMENTS for Class Imbalance:"
echo ""
echo "  ✓ Advanced text augmentation (EDA)"
echo "    - Synonym replacement"
echo "    - Random insertion"
echo "    - Random swap"
echo "    - Random deletion"
echo ""
echo "  ✓ Focal Loss (γ=2.5)"
echo "    - Focuses on hard-to-classify examples"
echo "    - Reduces weight on easy examples"
echo ""
echo "  ✓ Full dataset balancing (50:50)"
echo "    - Oversamples minority class to match majority"
echo "    - Uses multiple augmentation techniques"
echo ""
echo "  ✓ Class weighting"
echo "    - Automatically computed inverse frequency weights"
echo ""
echo "  ✓ Increased training (6 epochs)"
echo "    - More time to learn from augmented data"
echo ""
echo "Target: 80-90% accuracy on balanced predictions"
echo "======================================"
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

echo ""
echo "Note: Training will automatically use:"
echo "  - MPS (Apple Silicon GPU) if available on Mac"
echo "  - CUDA (NVIDIA GPU) if available"
echo "  - CPU as fallback"
echo ""

echo ""
echo "Starting training with AGGRESSIVE settings..."
echo ""

# Train the model with AGGRESSIVE imbalance handling
python3 ml/models/train.py \
    --file-suffix "_v2" \
    --save-name "reddit_stress_v4" \
    --epochs 3  \
    --batch-size 16 \
    --learning-rate 3e-5 \
    --balance-data \
    --balance-ratio 0.5 \
    --focal-loss \
    --focal-gamma 2.5

echo ""
echo "======================================"
echo "Training Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Test the model: python3 ml/models/test_model.py"
echo "  2. Check metrics in: ml/models/reddit_stress_v4/metadata.json"
echo ""
echo "Expected improvements:"
echo "  - Balanced predictions (not just predicting one class)"
echo "  - 80-90% overall accuracy"
echo "  - Good performance on BOTH stress and non-stress"
echo ""
