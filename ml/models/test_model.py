"""
Interactive Model Testing Script

This script allows you to test the trained model on custom text inputs.
"""

import argparse
from pathlib import Path
import logging

import torch
import pandas as pd
import numpy as np
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StressPredictor:
    """Simple predictor for testing the model"""

    def __init__(self, model_path: str):
        """
        Initialize predictor

        Args:
            model_path: Path to saved model directory
        """
        self.model_path = Path(model_path)
        logger.info(f"Loading model from {self.model_path}")

        # Load model and tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained(self.model_path)
        self.model = DistilBertForSequenceClassification.from_pretrained(self.model_path)

        # Set to evaluation mode
        self.model.eval()

        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        logger.info(f"Model ready on {self.device}")

    def predict(self, text: str):
        """
        Predict stress label for a single text

        Args:
            text: Input text

        Returns:
            Tuple of (label, confidence)
        """
        # Tokenize
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors='pt'
        )

        # Move to device
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)

        # Predict
        with torch.no_grad():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits

        # Get prediction
        probs = torch.softmax(logits, dim=1)
        pred_label = torch.argmax(logits, dim=1).item()
        confidence = probs[0][pred_label].item()

        label = "STRESS" if pred_label == 1 else "NON_STRESS"

        return label, confidence

    def predict_batch(self, texts):
        """
        Predict stress labels for multiple texts

        Args:
            texts: List of input texts

        Returns:
            List of (label, confidence) tuples
        """
        results = []
        for text in texts:
            label, confidence = self.predict(text)
            results.append((label, confidence))
        return results


def interactive_mode(model_path: str):
    """
    Run interactive testing mode

    Args:
        model_path: Path to saved model
    """
    predictor = StressPredictor(model_path)

    print("\n" + "="*60)
    print("REDDIT STRESS DETECTION - INTERACTIVE TESTING")
    print("="*60)
    print("Enter text to classify (or 'quit' to exit)")
    print("="*60 + "\n")

    while True:
        text = input("Text: ").strip()

        if text.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break

        if not text:
            print("Please enter some text.\n")
            continue

        # Predict
        label, confidence = predictor.predict(text)

        # Display result
        print(f"\n  Prediction: {label}")
        print(f"  Confidence: {confidence:.2%}")
        print()


def batch_test(model_path: str):
    """
    Test model on predefined examples

    Args:
        model_path: Path to saved model
    """
    predictor = StressPredictor(model_path)

    # Test examples
    examples = [
        ("I'm feeling so overwhelmed with work and can't handle it anymore", "STRESS"),
        ("Just finished reading a great book, highly recommend it", "NON_STRESS"),
        ("The anxiety is getting too much, I don't know what to do", "STRESS"),
        ("What are your favorite pizza toppings?", "NON_STRESS"),
        ("Feeling stressed out and exhausted all the time", "STRESS"),
        ("Planning a trip to Europe next summer, any tips?", "NON_STRESS"),
        ("Can't sleep, can't eat, everything feels like too much", "STRESS"),
        ("What TV shows are you watching these days?", "NON_STRESS")
    ]

    print("\n" + "="*60)
    print("BATCH TESTING ON SAMPLE TEXTS")
    print("="*60 + "\n")

    correct = 0
    total = len(examples)

    for text, true_label in examples:
        pred_label, confidence = predictor.predict(text)

        is_correct = pred_label == true_label
        if is_correct:
            correct += 1

        status = "✓" if is_correct else "✗"

        print(f"{status} Text: {text[:60]}...")
        print(f"  True: {true_label}, Predicted: {pred_label} ({confidence:.2%})")
        print()

    accuracy = correct / total
    print("="*60)
    print(f"Accuracy: {correct}/{total} ({accuracy:.1%})")
    print("="*60 + "\n")


def test_on_dataset(model_path: str, dataset_path: str, max_samples: int = None):
    """
    Test model on actual test dataset from CSV

    Args:
        model_path: Path to saved model
        dataset_path: Path to test CSV file
        max_samples: Maximum number of samples to test (None = all)
    """
    predictor = StressPredictor(model_path)

    # Load test dataset
    logger.info(f"Loading test dataset from {dataset_path}")
    df = pd.read_csv(dataset_path)

    if max_samples:
        df = df.head(max_samples)

    print("\n" + "="*80)
    print("TESTING ON ACTUAL DATASET")
    print("="*80)
    print(f"Dataset: {dataset_path}")
    print(f"Total samples: {len(df)}")
    print("="*80 + "\n")

    # Get texts and true labels
    texts = df['text'].tolist()
    true_labels = df['binary_label'].tolist()
    label_names = df['label'].tolist()

    # Predict on all samples
    logger.info("Making predictions...")
    predictions = []
    confidences = []

    for i, text in enumerate(texts):
        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i + 1}/{len(texts)}")

        pred_label, confidence = predictor.predict(text)
        # Convert to binary (0 or 1)
        pred_binary = 1 if pred_label == "STRESS" else 0
        predictions.append(pred_binary)
        confidences.append(confidence)

    # Calculate metrics
    accuracy = accuracy_score(true_labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        true_labels, predictions, average='binary'
    )

    # Per-class metrics
    precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(
        true_labels, predictions, average=None, labels=[0, 1]
    )

    # Confusion matrix
    cm = confusion_matrix(true_labels, predictions)

    # Print results
    print("\n" + "="*80)
    print("OVERALL METRICS")
    print("="*80)
    print(f"Accuracy:  {accuracy:.4f} ({accuracy:.2%})")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print()

    print("="*80)
    print("PER-CLASS METRICS")
    print("="*80)
    print(f"NON_STRESS (Class 0):")
    print(f"  Precision: {precision_per_class[0]:.4f}")
    print(f"  Recall:    {recall_per_class[0]:.4f}")
    print(f"  F1 Score:  {f1_per_class[0]:.4f}")
    print()
    print(f"STRESS (Class 1):")
    print(f"  Precision: {precision_per_class[1]:.4f}")
    print(f"  Recall:    {recall_per_class[1]:.4f}")
    print(f"  F1 Score:  {f1_per_class[1]:.4f}")
    print()

    print("="*80)
    print("CONFUSION MATRIX")
    print("="*80)
    print(f"                  Predicted")
    print(f"              NON_STRESS  STRESS")
    print(f"Actual NON    {cm[0][0]:10d}  {cm[0][1]:6d}")
    print(f"       STRESS {cm[1][0]:10d}  {cm[1][1]:6d}")
    print()

    # Classification report
    print("="*80)
    print("DETAILED CLASSIFICATION REPORT")
    print("="*80)
    print(classification_report(
        true_labels,
        predictions,
        target_names=['NON_STRESS', 'STRESS'],
        digits=4
    ))

    # Show some examples of misclassifications
    print("="*80)
    print("SAMPLE MISCLASSIFICATIONS (First 10)")
    print("="*80)

    misclassified = []
    for i, (true, pred) in enumerate(zip(true_labels, predictions)):
        if true != pred:
            misclassified.append({
                'index': i,
                'text': texts[i],
                'true_label': label_names[i],
                'pred_label': 'STRESS' if pred == 1 else 'NON_STRESS',
                'confidence': confidences[i]
            })

    for i, item in enumerate(misclassified[:10], 1):
        print(f"\n{i}. Text: {item['text'][:100]}...")
        print(f"   True: {item['true_label']}, Predicted: {item['pred_label']} ({item['confidence']:.2%})")

    print(f"\nTotal misclassified: {len(misclassified)}/{len(texts)}")
    print("="*80 + "\n")

    # Return metrics for programmatic use
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'confusion_matrix': cm,
        'per_class_metrics': {
            'non_stress': {
                'precision': precision_per_class[0],
                'recall': recall_per_class[0],
                'f1': f1_per_class[0]
            },
            'stress': {
                'precision': precision_per_class[1],
                'recall': recall_per_class[1],
                'f1': f1_per_class[1]
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Test trained model")
    parser.add_argument("--model-path", default="ml/models/reddit_stress_v4", help="Path to saved model")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--batch", action="store_true", help="Run batch test on examples")
    parser.add_argument("--text", type=str, help="Single text to classify")
    parser.add_argument("--dataset", type=str, help="Path to CSV dataset to test on")
    parser.add_argument("--max-samples", type=int, help="Maximum number of samples to test from dataset")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode(args.model_path)
    elif args.dataset:
        test_on_dataset(args.model_path, args.dataset, args.max_samples)
    elif args.batch:
        batch_test(args.model_path)
    elif args.text:
        predictor = StressPredictor(args.model_path)
        label, confidence = predictor.predict(args.text)
        print(f"\nPrediction: {label}")
        print(f"Confidence: {confidence:.2%}\n")
    else:
        # Default to batch test
        batch_test(args.model_path)


if __name__ == "__main__":
    main()
