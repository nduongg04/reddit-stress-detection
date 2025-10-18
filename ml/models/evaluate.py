"""
Model Evaluation Utilities for Reddit Stress Detection

This module provides utilities for evaluating trained models and generating
detailed performance reports.
"""

import json
import argparse
from pathlib import Path
import logging

import torch
import numpy as np
import pandas as pd
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve
)
import matplotlib.pyplot as plt
import seaborn as sns

from data_loader import StressDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Evaluate trained stress detection model"""

    def __init__(self, model_path: str):
        """
        Initialize evaluator with trained model

        Args:
            model_path: Path to saved model directory
        """
        self.model_path = Path(model_path)
        logger.info(f"Loading model from {self.model_path}")

        # Load model and tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained(self.model_path, local_files_only=True)
        self.model = DistilBertForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)

        # Set to evaluation mode
        self.model.eval()

        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        logger.info(f"Model loaded on {self.device}")

        # Load metadata if available
        self.metadata = None
        metadata_path = self.model_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                self.metadata = json.load(f)

    def predict(self, texts, batch_size=32, return_probs=False):
        """
        Make predictions on a list of texts

        Args:
            texts: List of text strings
            batch_size: Batch size for inference
            return_probs: If True, return probabilities instead of labels

        Returns:
            Predictions (labels or probabilities)
        """
        predictions = []
        probabilities = []

        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                # Tokenize
                encodings = self.tokenizer(
                    batch_texts,
                    truncation=True,
                    padding=True,
                    max_length=512,
                    return_tensors='pt'
                )

                # Move to device
                input_ids = encodings['input_ids'].to(self.device)
                attention_mask = encodings['attention_mask'].to(self.device)

                # Predict
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits

                # Get predictions
                batch_probs = torch.softmax(logits, dim=1)
                batch_preds = torch.argmax(logits, dim=1)

                predictions.extend(batch_preds.cpu().numpy())
                probabilities.extend(batch_probs.cpu().numpy())

        if return_probs:
            return np.array(probabilities)
        else:
            return np.array(predictions)

    def evaluate_dataset(self, texts, labels):
        """
        Evaluate model on a dataset

        Args:
            texts: List of text strings
            labels: List of true labels (0/1)

        Returns:
            Dictionary of metrics
        """
        logger.info(f"Evaluating on {len(texts)} samples...")

        # Get predictions and probabilities
        predictions = self.predict(texts, return_probs=False)
        probabilities = self.predict(texts, return_probs=True)

        # Calculate metrics
        accuracy = accuracy_score(labels, predictions)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average='binary'
        )

        # AUC
        auc = roc_auc_score(labels, probabilities[:, 1])

        # Confusion matrix
        cm = confusion_matrix(labels, predictions)

        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auc': auc,
            'confusion_matrix': cm.tolist(),
            'num_samples': len(texts),
            'num_correct': int((predictions == labels).sum()),
            'num_incorrect': int((predictions != labels).sum())
        }

        return metrics, predictions, probabilities

    def print_evaluation(self, metrics, title="Evaluation Results"):
        """
        Print evaluation metrics in a nice format

        Args:
            metrics: Dictionary of metrics
            title: Title for the report
        """
        print("\n" + "="*60)
        print(f"{title}")
        print("="*60)
        print(f"Samples: {metrics['num_samples']}")
        print(f"Correct: {metrics['num_correct']} ({metrics['num_correct']/metrics['num_samples']:.1%})")
        print(f"Incorrect: {metrics['num_incorrect']} ({metrics['num_incorrect']/metrics['num_samples']:.1%})")
        print(f"\nAccuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1 Score:  {metrics['f1']:.4f}")
        print(f"AUC:       {metrics['auc']:.4f}")

        cm = np.array(metrics['confusion_matrix'])
        print(f"\nConfusion Matrix:")
        print(f"                 Predicted")
        print(f"              NON  STRESS")
        print(f"Actual NON    {cm[0][0]:4d}  {cm[0][1]:4d}")
        print(f"       STRESS {cm[1][0]:4d}  {cm[1][1]:4d}")
        print("="*60 + "\n")

    def plot_confusion_matrix(self, cm, save_path=None):
        """
        Plot confusion matrix

        Args:
            cm: Confusion matrix
            save_path: Path to save plot (optional)
        """
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm,
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=['NON_STRESS', 'STRESS'],
            yticklabels=['NON_STRESS', 'STRESS']
        )
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')

        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            logger.info(f"Confusion matrix saved to {save_path}")

        plt.close()

    def plot_roc_curve(self, labels, probabilities, save_path=None):
        """
        Plot ROC curve

        Args:
            labels: True labels
            probabilities: Predicted probabilities
            save_path: Path to save plot (optional)
        """
        fpr, tpr, _ = roc_curve(labels, probabilities[:, 1])
        auc = roc_auc_score(labels, probabilities[:, 1])

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.4f})', linewidth=2)
        plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        plt.legend()
        plt.grid(alpha=0.3)

        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            logger.info(f"ROC curve saved to {save_path}")

        plt.close()

    def test_inference_speed(self, num_samples=100):
        """
        Test inference speed

        Args:
            num_samples: Number of samples to test

        Returns:
            Average inference time per sample (ms)
        """
        import time

        # Generate sample texts
        sample_texts = ["This is a sample text for testing inference speed"] * num_samples

        # Warm up
        _ = self.predict(sample_texts[:10])

        # Time inference
        start_time = time.time()
        _ = self.predict(sample_texts)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time_ms = (total_time / num_samples) * 1000

        logger.info(f"\nInference Speed Test:")
        logger.info(f"  Samples: {num_samples}")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(f"  Avg time per sample: {avg_time_ms:.2f}ms")
        logger.info(f"  Throughput: {num_samples/total_time:.1f} samples/sec")

        return avg_time_ms


def evaluate_model(model_path: str, data_dir: str = "ml/dataset/splits", plot=True):
    """
    Evaluate a trained model on test set

    Args:
        model_path: Path to saved model
        data_dir: Path to dataset splits
        plot: Whether to generate plots
    """
    # Initialize evaluator
    evaluator = ModelEvaluator(model_path)

    # Load test data
    dataset = StressDataset(data_dir)
    dataset.load_splits()
    test_texts, test_labels = dataset.get_texts_and_labels('test')

    # Evaluate
    metrics, predictions, probabilities = evaluator.evaluate_dataset(test_texts, test_labels)

    # Print results
    evaluator.print_evaluation(metrics, title="Test Set Evaluation")

    # Print detailed classification report
    print("\nDetailed Classification Report:")
    print(classification_report(
        test_labels,
        predictions,
        target_names=['NON_STRESS', 'STRESS'],
        digits=4
    ))

    # Generate plots
    if plot:
        output_dir = Path(model_path) / "evaluation"
        output_dir.mkdir(exist_ok=True)

        # Confusion matrix
        cm = np.array(metrics['confusion_matrix'])
        evaluator.plot_confusion_matrix(cm, save_path=output_dir / "confusion_matrix.png")

        # ROC curve
        evaluator.plot_roc_curve(test_labels, probabilities, save_path=output_dir / "roc_curve.png")

        logger.info(f"Plots saved to {output_dir}")

    # Test inference speed
    evaluator.test_inference_speed(num_samples=100)

    # Save evaluation results
    results_path = Path(model_path) / "evaluation_results.json"
    with open(results_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Results saved to {results_path}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained model")
    parser.add_argument("--model-path", default="ml/models/reddit_stress_v1", help="Path to saved model")
    parser.add_argument("--data-dir", default="ml/dataset/splits", help="Dataset directory")
    parser.add_argument("--no-plot", action="store_true", help="Skip generating plots")

    args = parser.parse_args()

    evaluate_model(args.model_path, args.data_dir, plot=not args.no_plot)


if __name__ == "__main__":
    main()
