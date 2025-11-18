#!/bin/bash

# Test the v4 model on the actual test_v2.csv dataset

set -e

echo "======================================"
echo "Testing Model v4 on test_v2.csv"
echo "======================================"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠ Virtual environment not activated!"
    echo "Please run: source .venv/bin/activate"
    exit 1
fi


# Check if model exists
if [ ! -d "ml/models/reddit_stress_v4" ]; then
    echo "❌ Error: Model not found at ml/models/reddit_stress_v4"
    echo ""
    echo "Please train the model first:"
    echo "  ./train_reddit_stress_v4.sh"
    echo ""
    exit 1
fi

# Check if test dataset exists
if [ ! -f "ml/dataset/splits/test_v2.csv" ]; then
    echo "❌ Error: Test dataset not found at ml/dataset/splits/test_v2.csv"
    echo ""
    exit 1
fi

echo "Model: ml/models/reddit_stress_v4"
echo "Dataset: ml/dataset/splits/test_v2.csv"
echo ""
echo "Running comprehensive test..."
echo ""

# Run the test
python3 ml/models/test_model.py \
    --model-path ml/models/reddit_stress_v4 \
    --dataset ml/dataset/splits/test_v2.csv

echo ""
echo "======================================"
echo "Test Complete!"
echo "======================================"
echo ""
echo "Compare with training metrics in:"
echo "  ml/models/reddit_stress_v4/metadata.json"
echo ""
