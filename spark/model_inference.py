"""ONNX model inference wrapper for Spark streaming."""

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


class StressClassifier:
    """ONNX-based stress classifier for real-time inference."""

    _instance = None

    def __init__(self, model_path: str, tokenizer_path: str, threshold: float = 0.5):
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.threshold = threshold
        self.max_length = 256
        self.num_aspects = 9
        self.aspect_names = [
            "occupational", "self_image", "health", "academic", "romantic",
            "familial", "financial", "life_events", "existential"
        ]

    @classmethod
    def get_instance(cls, model_path: str, tokenizer_path: str, threshold: float = 0.5):
        """Singleton pattern for Spark executors."""
        if cls._instance is None:
            cls._instance = cls(model_path, tokenizer_path, threshold)
        return cls._instance

    def predict(self, text: str) -> dict:
        """Predict stress aspects for a single text."""
        if not text or not text.strip():
            return {
                "aspects": [],
                "aspect_probs": [0.0] * self.num_aspects,
                "confidence": 0.0,
                "stress_label": False
            }

        # Tokenize
        inputs = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="np"
        )

        # ONNX inference
        outputs = self.session.run(None, {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        })

        # Sigmoid activation
        logits = outputs[0][0]
        probs = 1 / (1 + np.exp(-logits))

        # Apply threshold
        aspects = [int(i) for i, p in enumerate(probs) if p > self.threshold]
        aspect_probs = [float(p) for p in probs]

        return {
            "aspects": aspects,
            "aspect_probs": aspect_probs,
            "confidence": float(max(probs)) if aspects else 0.0,
            "stress_label": len(aspects) > 0
        }

    def predict_batch(self, texts: list) -> list:
        """Predict stress aspects for a batch of texts."""
        results = []
        for text in texts:
            results.append(self.predict(text))
        return results


# Global classifier instance for Spark UDF
_classifier = None


def get_classifier(model_path: str, tokenizer_path: str) -> StressClassifier:
    """Get or create classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = StressClassifier(model_path, tokenizer_path)
    return _classifier


def classify_text(text: str, model_path: str, tokenizer_path: str) -> dict:
    """Classify single text (for Spark UDF)."""
    classifier = get_classifier(model_path, tokenizer_path)
    return classifier.predict(text)
