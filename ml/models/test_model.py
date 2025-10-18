"""
Interactive Model Testing Script

This script allows you to test the trained model on custom text inputs.
"""

import argparse
from pathlib import Path
import logging

import torch
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

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


def main():
    parser = argparse.ArgumentParser(description="Test trained model")
    parser.add_argument("--model-path", default="ml/models/reddit_stress_v1", help="Path to saved model")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--batch", action="store_true", help="Run batch test on examples")
    parser.add_argument("--text", type=str, help="Single text to classify")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode(args.model_path)
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
