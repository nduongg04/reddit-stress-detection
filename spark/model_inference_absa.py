#!/usr/bin/env python3
"""
Multi-Label ABSA Model Inference for Real-Time Vietnamese Mental Health Detection

Supports:
- Model versioning with hot-reload
- Multi-label ABSA (10 Vietnamese aspects)
- Automatic registry-based model loading
- Graceful model updates during runtime
"""

import os
import json
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
from typing import List, Dict, Any, Tuple
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhoBERTMultiLabelClassifier(nn.Module):
    """PhoBERT with multi-label classification head"""

    def __init__(self, model_name, num_labels):
        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(self.phobert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        pooled_output = outputs.last_hidden_state[:, 0, :]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


class ABSAModelRegistry:
    """
    Model registry for versioned ABSA models

    Supports:
    - Loading active model from registry
    - Hot-reload when new model is available
    - Fallback to default model if registry unavailable
    """

    def __init__(
        self,
        registry_file: str = "/opt/ml/models/registry/registry.json",
        default_model: str = "/opt/ml/models/vietnamese_absa_sentiment_phobert_v1"
    ):
        self.registry_file = registry_file
        self.default_model = default_model
        self.current_version = None
        self.last_check = None

    def get_active_model_path(self) -> str:
        """
        Get path to currently active model

        Returns:
            str: Path to model directory
        """
        # Try loading from registry
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    registry = json.load(f)

                # Find active model
                active_models = [m for m in registry.get('models', []) if m.get('active', False)]

                if active_models:
                    active_model = active_models[-1]  # Most recent active
                    self.current_version = active_model['version']
                    logger.info(f"Loaded active model from registry: {self.current_version}")
                    return active_model['model_dir']

            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")

        # Fallback to default model
        logger.info(f"Using default model: {self.default_model}")
        return self.default_model

    def should_reload(self) -> Tuple[bool, str]:
        """
        Check if model should be reloaded

        Returns:
            (should_reload: bool, new_model_path: str)
        """
        if not os.path.exists(self.registry_file):
            return False, None

        try:
            with open(self.registry_file, 'r') as f:
                registry = json.load(f)

            # Find active model
            active_models = [m for m in registry.get('models', []) if m.get('active', False)]

            if active_models:
                active_model = active_models[-1]
                new_version = active_model['version']

                # Check if version changed
                if self.current_version and new_version != self.current_version:
                    logger.info(f"New model version detected: {new_version}")
                    return True, active_model['model_dir']

        except Exception as e:
            logger.warning(f"Failed to check registry: {e}")

        return False, None


class ABSAStressDetectionModel:
    """
    Multi-label ABSA model for Vietnamese mental health detection

    Features:
    - 10-dimensional aspect predictions
    - Model versioning with hot-reload
    - Batch inference for Spark streaming
    """

    def __init__(
        self,
        registry_file: str = "/opt/ml/models/registry/registry.json",
        default_model: str = "/opt/ml/models/vietnamese_absa_phobert_v1",
        aspects_file: str = "/opt/ml/lda/absa_mental_health_aspects.json",
        auto_reload: bool = True
    ):
        """
        Initialize ABSA model with versioning

        Args:
            registry_file: Path to model registry JSON
            default_model: Fallback model path
            aspects_file: ABSA aspects definition
            auto_reload: Enable automatic model reloading
        """
        self.registry = ABSAModelRegistry(registry_file, default_model)
        self.auto_reload = auto_reload
        self.aspects_file = aspects_file

        # Detect device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        logger.info(f"Using device: {self.device}")

        # Load aspects
        self.aspects = self._load_aspects()

        # Load initial model
        self.model_path = None
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_aspects(self) -> List[Dict]:
        """Load ABSA aspect definitions"""
        if os.path.exists(self.aspects_file):
            with open(self.aspects_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data['aspects']
        else:
            logger.warning(f"Aspects file not found: {self.aspects_file}")
            return []

    def _load_model(self, model_path: str = None):
        """
        Load PhoBERT ABSA model

        Args:
            model_path: Optional model path (uses registry if None)
        """
        if model_path is None:
            model_path = self.registry.get_active_model_path()

        if model_path == self.model_path:
            logger.info("Model already loaded, skipping")
            return

        logger.info(f"Loading model from: {model_path}")

        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)

            # Load model architecture (30 labels = 10 aspects × 3 sentiments)
            self.model = PhoBERTMultiLabelClassifier('vinai/phobert-base-v2', num_labels=30)

            # Load weights
            weights_path = os.path.join(model_path, 'model.pt')
            self.model.load_state_dict(
                torch.load(weights_path, map_location=self.device)
            )

            self.model.to(self.device)
            self.model.eval()

            self.model_path = model_path

            logger.info(f"✓ Model loaded successfully")
            logger.info(f"  Version: {self.registry.current_version or 'unknown'}")
            logger.info(f"  Device: {self.device}")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def reload_if_needed(self):
        """Check registry and reload model if new version available"""
        if not self.auto_reload:
            return

        should_reload, new_model_path = self.registry.should_reload()

        if should_reload and new_model_path:
            logger.info(f"Reloading model: {new_model_path}")
            self._load_model(new_model_path)

    def predict_batch(
        self,
        texts: List[str],
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Predict ABSA aspects for batch of texts

        Args:
            texts: List of post texts
            threshold: Probability threshold (not used for 3-class)

        Returns:
            List of dicts with predictions:
            {
                'aspect_sentiments': {'công_việc': 1, 'tình_yêu': -1, ...},  # aspect → sentiment
                'stress_score': 0.7,                # overall stress (0-1)
                'stress_label': True,               # binary stress (has negative sentiment)
                'model_version': 'v1'
            }
        """
        # Check for model reload
        self.reload_if_needed()

        if not texts:
            return []

        predictions = []

        # Batch processing
        with torch.no_grad():
            for text in texts:
                # Tokenize
                encoding = self.tokenizer(
                    text,
                    max_length=256,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )

                input_ids = encoding['input_ids'].to(self.device)
                attention_mask = encoding['attention_mask'].to(self.device)

                # Forward pass
                logits = self.model(input_ids, attention_mask)

                # Reshape logits: [30] → [10 aspects, 3 sentiments]
                # Format: [aspect0_neg, aspect0_neu, aspect0_pos, aspect1_neg, ...]
                logits_reshaped = logits.squeeze().view(10, 3).cpu()

                # Softmax over sentiments for each aspect
                probs = torch.softmax(logits_reshaped, dim=1).numpy()

                # Get predicted sentiment for each aspect (-1, 0, 1)
                sentiment_labels = probs.argmax(axis=1) - 1  # [0,1,2] → [-1,0,1]

                # Build aspect → sentiment map (only include non-neutral)
                aspect_sentiments = {}
                for i, sentiment in enumerate(sentiment_labels):
                    if sentiment != 0:  # Skip neutral
                        aspect_name = self.aspects[i]['aspect_name']
                        aspect_sentiments[aspect_name] = int(sentiment)

                # Overall stress score: max probability of negative sentiment
                # across all aspects
                neg_probs = probs[:, 0]  # Negative sentiment probabilities
                stress_score = float(neg_probs.max())

                # Binary stress label: any aspect has negative sentiment
                stress_label = bool((sentiment_labels == -1).any())

                predictions.append({
                    'aspect_sentiments': aspect_sentiments,
                    'stress_score': stress_score,
                    'stress_label': stress_label,
                    'model_version': self.registry.current_version or 'vietnamese_absa_phobert_v1'
                })

        return predictions

    def predict_single(self, text: str, threshold: float = 0.5) -> Dict[str, Any]:
        """
        Predict ABSA aspects for single text

        Args:
            text: Post text
            threshold: Probability threshold

        Returns:
            Dict with prediction
        """
        results = self.predict_batch([text], threshold)
        return results[0] if results else None


def test_model():
    """Test ABSA model with sample Vietnamese texts"""
    print("="*70)
    print("ABSA MODEL INFERENCE TEST")
    print("="*70)

    # Initialize model
    model = ABSAStressDetectionModel(
        default_model="ml/models/vietnamese_absa_sentiment_phobert_v1",
        aspects_file="ml/lda/absa_mental_health_aspects.json"
    )

    # Test samples
    test_texts = [
        "Mình stress quá, công việc nhiều, ngủ không được, cảm thấy mệt mỏi",
        "Tình yêu tan vỡ, mình buồn lắm, không muốn nói chuyện với ai",
        "Hôm nay thời tiết đẹp quá"
    ]

    print("\nRunning predictions...")
    predictions = model.predict_batch(test_texts)

    print("\n" + "="*70)
    print("PREDICTIONS")
    print("="*70)

    for i, (text, pred) in enumerate(zip(test_texts, predictions)):
        print(f"\n{i+1}. Text: {text}")
        print(f"   Stress Score: {pred['stress_score']:.3f}")
        print(f"   Stress Label: {pred['stress_label']}")
        print(f"   Detected Aspects: {', '.join(pred['aspects']) if pred['aspects'] else 'None'}")
        print(f"   Probabilities: {[f'{p:.2f}' for p in pred['probabilities']]}")


if __name__ == "__main__":
    test_model()
