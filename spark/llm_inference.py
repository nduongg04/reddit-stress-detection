#!/usr/bin/env python3
"""
LLM Inference Wrapper for Real-Time Stress Detection and Demographics
Uses llama3.1:8b via Ollama for both stress classification and demographic extraction
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Aspect names for reference
ASPECT_NAMES = [
    "Occupational", "Financial", "Academic", "Familial", "Health",
    "Romantic", "Existential", "Social", "Life Events", "Self Image"
]

# Valid values for demographics
VALID_GENDERS = {"nam", "nữ", "unknown"}
VALID_AGE_GROUPS = {"teen", "young_adult", "adult", "middle_aged", "senior", "unknown"}
VALID_OCCUPATIONS = {
    "student", "office_worker", "it_engineer", "healthcare",
    "teacher", "blue_collar", "freelance", "unemployed", "unknown"
}
VALID_RELATIONSHIPS = {"single", "dating", "married", "divorced", "unknown"}


class LLMStressInference:
    """
    LLM-based stress detection and demographic extraction
    Uses llama3.1:8b for combined analysis in a single prompt
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        prompt_file: str = None,
        timeout: int = 60
    ):
        """
        Initialize LLM inference wrapper

        Args:
            ollama_url: Ollama API endpoint
            model: Model name (llama3.1:8b for demo)
            prompt_file: Path to prompt template
            timeout: Request timeout in seconds
        """
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout
        self.model_version = f"{model}_demo"

        # Load prompt template
        if prompt_file is None:
            prompt_file = Path(__file__).parent.parent / "config" / "demographic_prompts" / "stress_and_demographics_v1.txt"

        self.prompt_template = self._load_prompt(prompt_file)
        logger.info(f"LLM Inference initialized: model={model}, url={ollama_url}")

    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt template from file"""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_file}, using default")
            return self._default_prompt()

    def _default_prompt(self) -> str:
        """Default prompt if file not found"""
        return """Phân tích bài đăng tiếng Việt và trả về JSON:
- aspects: mảng số [0-9] cho các khía cạnh stress (0=Công việc, 1=Tài chính, 2=Học tập, 3=Gia đình, 4=Sức khỏe, 5=Tình cảm, 6=Hiện sinh, 7=Xã hội, 8=Sự kiện, 9=Hình ảnh bản thân)
- gender: "nam"/"nữ"/"unknown"
- age_group: "teen"/"young_adult"/"adult"/"middle_aged"/"senior"/"unknown"
- occupation: "student"/"office_worker"/"it_engineer"/"healthcare"/"teacher"/"blue_collar"/"freelance"/"unemployed"/"unknown"
- relationship: "single"/"dating"/"married"/"divorced"/"unknown"
- reasoning: giải thích ngắn

Bài đăng:
"""

    def _call_ollama(self, text: str) -> dict | None:
        """Call Ollama API and parse response"""
        prompt = self.prompt_template + text

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500,
                        "num_ctx": 4096,
                    }
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"Ollama API error: {response.status_code}")
                return None

            data = response.json()
            response_text = data.get("response", "").strip()

            # Extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start >= 0 and end > start:
                return json.loads(response_text[start:end])

            logger.warning(f"No valid JSON in response: {response_text[:100]}")
            return None

        except requests.Timeout:
            logger.warning("Ollama request timed out")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None

    def _validate_and_normalize(self, result: dict) -> dict:
        """Validate and normalize LLM output"""
        # Validate aspects
        aspects = result.get("aspects", [])
        if isinstance(aspects, list):
            aspects = [a for a in aspects if isinstance(a, int) and 0 <= a <= 9]
        else:
            aspects = []

        # Validate demographics with fallback to unknown
        gender = result.get("gender", "unknown")
        if gender not in VALID_GENDERS:
            gender = "unknown"

        age_group = result.get("age_group", "unknown")
        if age_group not in VALID_AGE_GROUPS:
            age_group = "unknown"

        occupation = result.get("occupation", "unknown")
        if occupation not in VALID_OCCUPATIONS:
            occupation = "unknown"

        relationship = result.get("relationship", "unknown")
        if relationship not in VALID_RELATIONSHIPS:
            relationship = "unknown"

        return {
            "aspects": aspects,
            "gender": gender,
            "age_group": age_group,
            "occupation": occupation,
            "relationship": relationship,
            "reasoning": result.get("reasoning", "")
        }

    def predict(self, text: str) -> dict[str, Any]:
        """
        Predict stress aspects and demographics for a single text

        Args:
            text: Vietnamese post text

        Returns:
            Dict with:
            - aspects: list[int] - detected aspect IDs [0-9]
            - aspect_probs: list[float] - probabilities for each aspect
            - confidence: float - overall confidence
            - stress_label: bool - True if any stress detected
            - gender: str - detected gender
            - age_group: str - detected age group
            - occupation: str - detected occupation
            - relationship: str - detected relationship status
            - reasoning: str - LLM explanation
            - model_version: str - model identifier
            - processing_time_ms: int - inference time
        """
        start_time = time.time()

        # Call LLM
        result = self._call_ollama(text)

        if result is None:
            # Return default values on failure
            return {
                "aspects": [],
                "aspect_probs": [0.0] * 10,
                "confidence": 0.0,
                "stress_label": False,
                "gender": "unknown",
                "age_group": "unknown",
                "occupation": "unknown",
                "relationship": "unknown",
                "reasoning": "LLM inference failed",
                "model_version": self.model_version,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Validate and normalize
        normalized = self._validate_and_normalize(result)

        # Build aspect probabilities (1.0 for detected, 0.0 for not detected)
        aspect_probs = [1.0 if i in normalized["aspects"] else 0.0 for i in range(10)]

        # Calculate confidence (average of detected aspect probs)
        confidence = sum(aspect_probs) / len(aspect_probs) if aspect_probs else 0.0

        processing_time = int((time.time() - start_time) * 1000)

        return {
            "aspects": normalized["aspects"],
            "aspect_probs": aspect_probs,
            "confidence": confidence,
            "stress_label": len(normalized["aspects"]) > 0,
            "gender": normalized["gender"],
            "age_group": normalized["age_group"],
            "occupation": normalized["occupation"],
            "relationship": normalized["relationship"],
            "reasoning": normalized["reasoning"],
            "model_version": self.model_version,
            "processing_time_ms": processing_time
        }

    def predict_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        """
        Predict for a batch of texts (sequential for LLM)

        Args:
            texts: List of Vietnamese post texts

        Returns:
            List of prediction dicts
        """
        return [self.predict(text) for text in texts]

    def health_check(self) -> bool:
        """Check if Ollama is available and model is loaded"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(self.model in name for name in model_names):
                    return True
                logger.warning(f"Model {self.model} not found in Ollama")
            return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


def test_inference():
    """Test LLM inference with sample texts"""
    print("=" * 70)
    print("LLM INFERENCE TEST")
    print("=" * 70)

    # Initialize
    inference = LLMStressInference()

    # Health check
    if not inference.health_check():
        print("ERROR: Ollama not available or model not loaded")
        print(f"Please run: ollama pull {inference.model}")
        return

    # Test samples
    test_texts = [
        "Mình là sinh viên năm 3, sắp thi rồi mà chưa học gì. Lo lắm không biết có qua được không.",
        "Vợ chồng em cãi nhau suốt, chồng em đi làm về cứ uống rượu rồi mắng chửi.",
        "Công ty mới cắt giảm nhân sự, mình lo quá không biết có bị cho nghỉ không.",
        "Hôm nay trời đẹp quá, đi cafe với bạn bè vui ghê.",
        "Mình là dev, làm overtime suốt mà lương thấp. Stress quá, muốn nghỉ việc.",
    ]

    print("\nRunning predictions...")
    print("-" * 70)

    for i, text in enumerate(test_texts):
        result = inference.predict(text)

        print(f"\n{i+1}. Text: {text[:60]}...")
        print(f"   Aspects: {result['aspects']} ({[ASPECT_NAMES[a] for a in result['aspects']]})")
        print(f"   Stress: {result['stress_label']}")
        print(f"   Gender: {result['gender']}, Age: {result['age_group']}")
        print(f"   Occupation: {result['occupation']}, Relationship: {result['relationship']}")
        print(f"   Time: {result['processing_time_ms']}ms")
        print(f"   Reasoning: {result['reasoning'][:100]}...")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_inference()
