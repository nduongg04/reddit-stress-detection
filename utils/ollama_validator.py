#!/usr/bin/env python3
"""
Ollama Validator for Uncertain PhoBERT Predictions
Active Learning Component for Airflow Retraining Pipeline

Selects low-confidence predictions and re-labels them using Ollama
"""

import json
import subprocess
import re
import numpy as np
from typing import List, Dict, Tuple
import torch
from scipy.stats import entropy


class OllamaValidator:
    """
    Validates uncertain PhoBERT predictions using Ollama LLM

    Used for active learning in daily retraining pipeline:
    1. Calculate prediction uncertainty (entropy-based)
    2. Select top-N most uncertain predictions
    3. Re-label using Ollama with detailed prompts
    4. Add validated labels to retraining dataset
    """

    def __init__(
        self,
        aspects_file='ml/lda/absa_mental_health_aspects.json',
        model_name='llama3.1:8b',
        uncertainty_threshold=0.5,
        max_retries=3
    ):
        """
        Initialize Ollama validator

        Args:
            aspects_file: Path to ABSA aspects JSON
            model_name: Ollama model to use for validation
            uncertainty_threshold: Minimum entropy for "uncertain" classification
            max_retries: Max Ollama call retries on failure
        """
        self.model_name = model_name
        self.uncertainty_threshold = uncertainty_threshold
        self.max_retries = max_retries

        # Load aspects
        with open(aspects_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.aspects = data['aspects']

    def calculate_uncertainty(self, predictions: np.ndarray) -> np.ndarray:
        """
        Calculate prediction uncertainty using entropy

        Args:
            predictions: (N, 10) array of sigmoid probabilities [0-1]

        Returns:
            (N,) array of uncertainty scores (higher = more uncertain)

        Entropy for binary classification per aspect:
            H = -p*log(p) - (1-p)*log(1-p)

        Total uncertainty = mean entropy across all aspects
        """
        # Clip predictions to avoid log(0)
        predictions = np.clip(predictions, 1e-7, 1 - 1e-7)

        # Binary entropy for each aspect
        # H = -p*log2(p) - (1-p)*log2(1-p)
        binary_entropy = -(
            predictions * np.log2(predictions) +
            (1 - predictions) * np.log2(1 - predictions)
        )

        # Mean entropy across all 10 aspects
        uncertainty_scores = binary_entropy.mean(axis=1)

        return uncertainty_scores

    def select_uncertain_samples(
        self,
        texts: List[str],
        predictions: np.ndarray,
        top_n: int = 100
    ) -> List[Dict]:
        """
        Select most uncertain predictions for validation

        Args:
            texts: List of post texts
            predictions: (N, 10) array of model probabilities
            top_n: Number of uncertain samples to select

        Returns:
            List of dicts with {text, prediction, uncertainty}
        """
        uncertainties = self.calculate_uncertainty(predictions)

        # Get top-N most uncertain indices
        uncertain_indices = np.argsort(uncertainties)[-top_n:][::-1]

        uncertain_samples = []
        for idx in uncertain_indices:
            # Convert idx to scalar - handle multi-dimensional arrays
            if isinstance(idx, np.ndarray):
                idx_scalar = int(idx.flatten()[0])
            else:
                idx_scalar = int(idx)
            
            # Convert uncertainty to scalar - handle multi-dimensional arrays
            uncertainty_arr = uncertainties[idx_scalar]
            if isinstance(uncertainty_arr, np.ndarray):
                uncertainty_value = float(uncertainty_arr.item() if uncertainty_arr.size == 1 else uncertainty_arr.flatten()[0])
            else:
                uncertainty_value = float(uncertainty_arr)
            
            if uncertainty_value >= self.uncertainty_threshold:
                uncertain_samples.append({
                    'index': idx_scalar,
                    'text': texts[idx_scalar],
                    'prediction': predictions[idx_scalar].tolist() if isinstance(predictions[idx_scalar], np.ndarray) else predictions[idx_scalar],
                    'uncertainty': uncertainty_value
                })

        return uncertain_samples

    def create_validation_prompt(self, text: str, prediction: List[float]) -> str:
        """
        Create detailed Ollama prompt for validation

        Includes:
        - Post text
        - Model's prediction with probabilities
        - Request for validation/correction
        """
        # Build aspect list with model predictions
        aspect_list = []
        for i, asp in enumerate(self.aspects):
            prob = prediction[i]
            # Handle case where prob might be a list/array
            if isinstance(prob, (list, np.ndarray)):
                prob_value = float(prob[0] if isinstance(prob, list) else prob.flatten()[0])
            else:
                prob_value = float(prob)
            
            predicted = "✓" if prob_value > 0.5 else "✗"
            aspect_list.append(
                f"{i}. [{predicted}] {asp['aspect_name']} (model: {prob_value:.2f}) - {asp['mental_health_relevance']}"
            )

        prompt = f"""Bạn là chuyên gia phân tích sức khỏe tâm thần. Model AI đã phân tích bài viết dưới đây nhưng không chắc chắn. Hãy kiểm tra và sửa lại nếu cần.

BÀI VIẾT:
\"\"\"{text[:600]}\"\"\"

DỰ ĐOÁN CỦA MODEL (không chắc chắn):
{chr(10).join(aspect_list)}

NHIỆM VỤ CỦA BẠN:
1. Đọc kỹ bài viết
2. Kiểm tra dự đoán của model (✓ = có, ✗ = không)
3. Sửa lại nếu model sai
4. Trả về danh sách CHÍNH XÁC các khía cạnh có trong bài

HƯỚNG DẪN:
- Một bài có thể có NHIỀU khía cạnh (multi-label)
- Chỉ chọn khía cạnh NẾU bài viết đề cập RÕ RÀNG
- Nếu model đúng, trả về đúng dự đoán của model
- Nếu model sai, sửa lại cho chính xác

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON:
{{"aspects": [danh sách số 0-9], "confidence": 0.0-1.0, "corrected": true/false}}

Ví dụ:
- Model đúng: {{"aspects": [0,2,7], "confidence": 0.9, "corrected": false}}
- Model sai:  {{"aspects": [0,7,8], "confidence": 0.95, "corrected": true}}

Chỉ trả về JSON, không giải thích thêm."""

        return prompt

    def call_ollama(self, prompt: str) -> Dict:
        """
        Call Ollama API via HTTP with retry logic

        Returns:
            Dict with {aspects, confidence, corrected}
        """
        import os
        import requests
        
        # Get Ollama host from environment (set in docker-compose)
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        for attempt in range(self.max_retries):
            try:
                # Call Ollama HTTP API
                response = requests.post(
                    f'{ollama_host}/api/generate',
                    json={
                        'model': self.model_name,
                        'prompt': prompt,
                        'stream': False
                    },
                    timeout=60
                )
                response.raise_for_status()
                output = response.json().get('response', '').strip()

                # Try to extract JSON (multiple strategies)
                # Strategy 1: Find JSON with "aspects" key
                json_match = re.search(r'\{[^}]*"aspects"[^}]*\}', output, re.DOTALL)
                if json_match:
                    response = json.loads(json_match.group())
                    # Ensure all required fields
                    if 'aspects' in response:
                        response.setdefault('confidence', 0.5)
                        response.setdefault('corrected', False)
                        return response

                # Strategy 2: Try parsing entire output
                try:
                    response = json.loads(output)
                    if 'aspects' in response:
                        response.setdefault('confidence', 0.5)
                        response.setdefault('corrected', False)
                        return response
                except:
                    pass

                # Strategy 3: Extract array pattern [0,1,2]
                array_match = re.search(r'\[[\d,\s]+\]', output)
                if array_match:
                    aspects = json.loads(array_match.group())
                    return {
                        "aspects": aspects,
                        "confidence": 0.5,
                        "corrected": False
                    }

                # Retry on parse failure
                if attempt < self.max_retries - 1:
                    continue

                # Give up - return empty
                return {"aspects": [], "confidence": 0.0, "corrected": False}

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    continue
                return {"aspects": [], "confidence": 0.0, "corrected": False}
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    continue
                return {"aspects": [], "confidence": 0.0, "corrected": False}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    continue
                return {"aspects": [], "confidence": 0.0, "corrected": False}

        return {"aspects": [], "confidence": 0.0, "corrected": False}

    def validate_sample(self, text: str, prediction: List[float]) -> Dict:
        """
        Validate a single uncertain prediction

        Args:
            text: Post text
            prediction: Model's 10-dimensional probability vector

        Returns:
            Dict with validated labels and metadata
        """
        # Create validation prompt
        prompt = self.create_validation_prompt(text, prediction)

        # Get Ollama validation
        validation = self.call_ollama(prompt)

        # Create label vector from validated aspects
        label_vector = [0] * 10
        for raw_aspect_id in validation.get('aspects', []):
            try:
                aspect_id = int(raw_aspect_id)
                if 0 <= aspect_id < 10:
                    label_vector[aspect_id] = 1
            except (ValueError, TypeError):
                continue

        return {
            'text': text,
            'original_prediction': prediction,
            'validated_labels': label_vector,
            'aspects_detected': validation.get('aspects', []),
            'confidence': validation.get('confidence', 0.5),
            'corrected': validation.get('corrected', False)
        }

    def validate_batch(
        self,
        uncertain_samples: List[Dict],
        verbose: bool = True
    ) -> List[Dict]:
        """
        Validate a batch of uncertain predictions

        Args:
            uncertain_samples: List from select_uncertain_samples()
            verbose: Print progress

        Returns:
            List of validated samples with corrected labels
        """
        validated = []

        if verbose:
            print(f"\nValidating {len(uncertain_samples)} uncertain predictions with Ollama...")
            print(f"Model: {self.model_name}")
            print(f"Uncertainty threshold: {self.uncertainty_threshold}\n")

        for i, sample in enumerate(uncertain_samples):
            if verbose and (i + 1) % 10 == 0:
                print(f"  Validated {i + 1}/{len(uncertain_samples)} samples...")

            validated_sample = self.validate_sample(
                sample['text'],
                sample['prediction']
            )

            # Add original metadata
            validated_sample['index'] = sample['index']
            validated_sample['uncertainty'] = sample['uncertainty']

            validated.append(validated_sample)

        if verbose:
            print(f"\n✓ Validated {len(validated)} samples")

            # Stats
            corrected_count = sum(1 for v in validated if v['corrected'])
            print(f"  Corrected: {corrected_count} ({(corrected_count/len(validated))*100:.1f}%)")

            avg_conf = sum(v['confidence'] for v in validated) / len(validated)
            print(f"  Avg confidence: {avg_conf:.2f}")

        return validated


def main():
    """
    Test Ollama validator on sample predictions
    """
    print("="*70)
    print("OLLAMA VALIDATOR TEST")
    print("="*70)

    # Initialize validator
    validator = OllamaValidator(
        uncertainty_threshold=0.4,
        model_name='llama3.1:8b'
    )

    # Test sample
    test_texts = [
        "Mình stress quá, công việc nhiều, ngủ không được, cảm thấy mệt mỏi",
        "Tình yêu tan vỡ, mình buồn lắm, không muốn nói chuyện với ai"
    ]

    # Mock uncertain predictions (high entropy)
    test_predictions = np.array([
        [0.6, 0.4, 0.3, 0.7, 0.2, 0.1, 0.5, 0.6, 0.2, 0.3],  # Uncertain
        [0.1, 0.2, 0.8, 0.3, 0.1, 0.9, 0.4, 0.7, 0.5, 0.2]   # Uncertain
    ])

    # Calculate uncertainty
    uncertainties = validator.calculate_uncertainty(test_predictions)
    print(f"\nUncertainty scores: {uncertainties}")

    # Select uncertain samples
    uncertain = validator.select_uncertain_samples(test_texts, test_predictions, top_n=2)
    print(f"\nSelected {len(uncertain)} uncertain samples")

    # Validate
    validated = validator.validate_batch(uncertain, verbose=True)

    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)

    for v in validated:
        print(f"\nText: {v['text'][:60]}...")
        print(f"Original prediction: {v['original_prediction']}")
        print(f"Validated labels: {v['validated_labels']}")
        print(f"Corrected: {v['corrected']}")
        print(f"Confidence: {v['confidence']}")


if __name__ == "__main__":
    main()
