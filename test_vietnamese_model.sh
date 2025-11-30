#!/bin/bash

# Test Vietnamese Stress Detection Model (PhoBERT)
# Evaluates model performance and provides interactive testing

set -e  # Exit on error

echo "======================================================================"
echo "Vietnamese Stress Detection Model Testing"
echo "======================================================================"
echo ""

# Configuration
MODEL_DIR="ml/models/vietnamese_stress_phobert"
DATA_DIR="ml/dataset/splits"
TEST_SCRIPT="ml/models/test_vietnamese_model.py"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠ Virtual environment not active. Activating..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    elif [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo "✗ No virtual environment found"
        exit 1
    fi
fi

# Check if model exists
if [ ! -d "$MODEL_DIR" ]; then
    echo "✗ Model not found: $MODEL_DIR"
    echo ""
    echo "Train the model first:"
    echo "  ./train_vietnamese_stress.sh"
    exit 1
fi

echo "✓ Model found: $MODEL_DIR"

# Check if test dataset exists
if [ ! -f "$DATA_DIR/test_vietnamese.csv" ]; then
    echo "✗ Test dataset not found: $DATA_DIR/test_vietnamese.csv"
    exit 1
fi

# Count actual rows using Python (wc -l counts newlines in text)
TEST_COUNT=$(python -c "import pandas as pd; print(len(pd.read_csv('$DATA_DIR/test_vietnamese.csv')))" 2>/dev/null || echo "0")
echo "✓ Test dataset: $TEST_COUNT samples"
echo ""

# Create test script if it doesn't exist
if [ ! -f "$TEST_SCRIPT" ]; then
    echo "Creating test script..."
    cat > "$TEST_SCRIPT" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
Test Vietnamese Stress Detection Model

Evaluates model on test set and provides interactive testing.
"""

import os
import sys
import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)

MODEL_DIR = "ml/models/vietnamese_stress_phobert"
TEST_FILE = "ml/dataset/splits/test_vietnamese.csv"

def load_model():
    """Load Vietnamese PhoBERT model."""
    print(f"Loading model from {MODEL_DIR}...")

    # Check device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Using MPS (Apple Silicon)")
    else:
        device = torch.device("cpu")
        print("Using CPU")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.to(device)
    model.eval()

    print(f"✓ Model loaded ({sum(p.numel() for p in model.parameters()):,} parameters)")
    return model, tokenizer, device

def predict_text(text, model, tokenizer, device):
    """Predict stress label for a single text."""
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=256,
        padding=True
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)
        pred_label = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][pred_label].item()

    label_name = "STRESS" if pred_label == 1 else "NON_STRESS"
    return label_name, confidence

def evaluate_test_set(model, tokenizer, device):
    """Evaluate model on test set."""
    print(f"\nLoading test set from {TEST_FILE}...")
    df = pd.read_csv(TEST_FILE)
    print(f"✓ Loaded {len(df)} test samples")

    # Get predictions
    print("\nRunning predictions...")
    predictions = []
    true_labels = []

    for idx, row in df.iterrows():
        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(df)} samples...")

        text = row['text']
        true_label = int(row['binary_label'])

        pred_label, _ = predict_text(text, model, tokenizer, device)
        pred_binary = 1 if pred_label == "STRESS" else 0

        predictions.append(pred_binary)
        true_labels.append(true_label)

    # Compute metrics
    print("\n" + "="*70)
    print("Test Set Evaluation Results")
    print("="*70)

    accuracy = accuracy_score(true_labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_labels, predictions, average='binary'
    )

    print(f"\nOverall Metrics:")
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1 Score:  {f1:.4f}")

    # Per-class metrics
    print(f"\nDetailed Classification Report:")
    print(classification_report(
        true_labels,
        predictions,
        target_names=['NON_STRESS', 'STRESS'],
        digits=4
    ))

    # Confusion matrix
    cm = confusion_matrix(true_labels, predictions)
    print("Confusion Matrix:")
    print(f"                 Predicted")
    print(f"              NON  STRESS")
    print(f"Actual NON    {cm[0][0]:4d}  {cm[0][1]:4d}")
    print(f"       STRESS {cm[1][0]:4d}  {cm[1][1]:4d}")

    # Target check
    print("\n" + "="*70)
    targets_met = accuracy >= 0.92 and precision >= 0.88 and recall >= 0.92 and f1 >= 0.90
    if targets_met:
        print("✓ Model meets all target metrics!")
        print("  Targets: Accuracy≥92%, Precision≥88%, Recall≥92%, F1≥90%")
    else:
        print("⚠ Model performance:")
        print(f"  Accuracy:  {accuracy:.1%} (target: ≥92%)")
        print(f"  Precision: {precision:.1%} (target: ≥88%)")
        print(f"  Recall:    {recall:.1%} (target: ≥92%)")
        print(f"  F1 Score:  {f1:.1%} (target: ≥90%)")

    print("="*70)

    # Save results
    results = {
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1': float(f1),
        'targets_met': targets_met
    }

    import json
    results_file = os.path.join(MODEL_DIR, 'test_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {results_file}")

    return results

def interactive_testing(model, tokenizer, device):
    """Interactive testing mode."""
    print("\n" + "="*70)
    print("Interactive Testing Mode")
    print("="*70)
    print("\nEnter Vietnamese text to test stress detection.")
    print("Type 'quit' or 'exit' to stop.\n")

    examples = [
        "Tôi đang rất căng thẳng và lo âu về công việc",
        "Hôm nay tôi rất vui vẻ và hạnh phúc",
        "Cảm thấy mệt mỏi và kiệt sức sau một tuần dài",
        "Cuối tuần đi du lịch thật tuyệt vời"
    ]

    print("Example texts (or type your own):")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {ex}")
    print()

    while True:
        try:
            text = input("Enter text (or number 1-4, or 'quit'): ").strip()

            if text.lower() in ['quit', 'exit', 'q']:
                print("\nExiting interactive mode...")
                break

            # Check if user entered a number (example selection)
            if text.isdigit() and 1 <= int(text) <= len(examples):
                text = examples[int(text) - 1]
                print(f"Using example: {text}")

            if not text:
                continue

            # Predict
            label, confidence = predict_text(text, model, tokenizer, device)

            # Color output
            if label == "STRESS":
                print(f"  → Prediction: \033[91m{label}\033[0m (confidence: {confidence:.2%})")
            else:
                print(f"  → Prediction: \033[92m{label}\033[0m (confidence: {confidence:.2%})")
            print()

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue

def main():
    """Main execution."""
    # Load model
    model, tokenizer, device = load_model()

    # Evaluate on test set
    results = evaluate_test_set(model, tokenizer, device)

    # Interactive testing
    print("\n")
    response = input("Start interactive testing? (y/n): ").strip().lower()
    if response in ['y', 'yes']:
        interactive_testing(model, tokenizer, device)

    print("\nTesting complete!")

if __name__ == '__main__':
    main()
PYTHON_SCRIPT

    chmod +x "$TEST_SCRIPT"
    echo "✓ Test script created: $TEST_SCRIPT"
fi

# Run test
echo "======================================================================"
echo "Running Model Test..."
echo "======================================================================"
echo ""

python "$TEST_SCRIPT"

echo ""
echo "======================================================================"
echo "Testing Complete!"
echo "======================================================================"
