#!/usr/bin/env python3
"""
Model Inference Module for Real-Time Stress Detection

Loads the v4 DistilBERT model and provides batch inference capabilities
for Spark Streaming pipeline.
"""
import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StressDetectionModel:
    """
    Wrapper for the v4 stress detection model.
    Optimized for batch inference in Spark.
    """

    def __init__(self, model_path: str = "/opt/ml/models/reddit_stress_v4"):
        """
        Initialize the model and tokenizer.

        Args:
            model_path: Path to the trained model directory
        """
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.model_version = "v4"

        logger.info(f"Initializing model from: {model_path}")
        logger.info(f"Using device: {self.device}")

        self._load_model()

    def _load_model(self):
        """Load the model and tokenizer from disk."""
        try:
            # Check if model path exists
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model path does not exist: {self.model_path}")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                local_files_only=True,
                trust_remote_code=False
            )

            # Load model
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path,
                local_files_only=True,
                trust_remote_code=False
            )
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode

            logger.info("✓ Model and tokenizer loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def predict_batch(self, texts: List[str], batch_size: int = 32) -> List[Dict[str, Any]]:
        """
        Predict stress labels for a batch of texts.

        Args:
            texts: List of text strings to classify
            batch_size: Batch size for inference

        Returns:
            List of dictionaries containing predictions:
            [
                {
                    "stress_label": bool,
                    "stress_score": float,
                    "model_version": str
                },
                ...
            ]
        """
        if not texts:
            return []

        results = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_results = self._predict_single_batch(batch_texts)
            results.extend(batch_results)

        return results

    def _predict_single_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Predict for a single batch.

        Args:
            texts: List of texts in this batch

        Returns:
            List of prediction dictionaries
        """
        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Inference
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1)

        # Extract predictions
        predictions = []
        for prob in probabilities:
            # prob[0] = non-stress, prob[1] = stress
            stress_score = prob[1].item()
            stress_label = stress_score > 0.5

            predictions.append({
                "stress_label": bool(stress_label),
                "stress_score": float(stress_score),
                "model_version": self.model_version
            })

        return predictions

    def predict_single(self, text: str) -> Dict[str, Any]:
        """
        Predict for a single text (convenience method).

        Args:
            text: Text to classify

        Returns:
            Dictionary with prediction
        """
        return self.predict_batch([text])[0]


# Singleton instance for Spark workers
_model_instance = None


def get_model_instance(model_path: str = "/opt/ml/models/reddit_stress_v4") -> StressDetectionModel:
    """
    Get or create the singleton model instance.
    This ensures the model is loaded only once per Spark executor.

    Args:
        model_path: Path to the model directory

    Returns:
        StressDetectionModel instance
    """
    global _model_instance

    if _model_instance is None:
        _model_instance = StressDetectionModel(model_path)

    return _model_instance


def predict_stress_udf(texts: List[str]) -> List[Dict[str, Any]]:
    """
    UDF-compatible prediction function for Spark.

    Args:
        texts: List of texts to classify

    Returns:
        List of prediction dictionaries
    """
    model = get_model_instance()
    return model.predict_batch(texts)


if __name__ == "__main__":
    # Test the model
    print("Testing stress detection model...")

    model = StressDetectionModel()

    test_texts = [
        "I'm feeling so overwhelmed with work and life right now",
        "Just had a great day at the park with friends",
        "Can't sleep, anxiety is killing me",
        "Looking forward to the weekend!"
    ]

    print("\nTest predictions:")
    print("-" * 60)

    results = model.predict_batch(test_texts)

    for text, result in zip(test_texts, results):
        label = "STRESS" if result["stress_label"] else "NON_STRESS"
        score = result["stress_score"]
        print(f"\nText: {text}")
        print(f"Label: {label} (score: {score:.4f})")

    print("\n" + "="*60)
    print("Model test complete!")
