#!/usr/bin/env python3
"""Data augmentation and synthetic generation for underrepresented aspects."""

import json
import argparse
import random
import time
from datetime import datetime
from pathlib import Path
from collections import Counter
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
NUM_ASPECTS = 9

ASPECT_NAMES = {
    0: "Công việc (áp lực công việc, sự nghiệp)",
    1: "Hình ảnh bản thân (tự ti, ngoại hình)",
    2: "Sức khỏe (lo lắng sức khỏe)",
    3: "Học tập (áp lực học hành, thi cử)",
    4: "Tình cảm (tình yêu, chia tay)",
    5: "Gia đình (mâu thuẫn gia đình)",
    6: "Tài chính (tiền bạc, nợ nần)",
    7: "Sự kiện (mất mát, chấn thương)",
    8: "Hiện sinh (cô đơn, ý nghĩa cuộc sống)",
}

# Vietnamese synonym replacements for augmentation
SYNONYMS = {
    "stress": ["căng thẳng", "áp lực", "mệt mỏi"],
    "buồn": ["đau khổ", "chán nản", "tủi thân"],
    "lo lắng": ["lo âu", "bất an", "sợ hãi"],
    "mệt": ["kiệt sức", "uể oải", "rã rời"],
    "khó khăn": ["vất vả", "gian nan", "trắc trở"],
    "vấn đề": ["rắc rối", "khó xử", "nan giải"],
}

def synonym_replacement(text: str, n: int = 2) -> str:
    """Replace n random words with synonyms."""
    words = text.split()
    for _ in range(n):
        for i, word in enumerate(words):
            word_lower = word.lower()
            if word_lower in SYNONYMS:
                words[i] = random.choice(SYNONYMS[word_lower])
                break
    return " ".join(words)

def word_shuffle(text: str) -> str:
    """Shuffle middle words while keeping sentence structure."""
    sentences = text.split(".")
    result = []
    for sent in sentences:
        words = sent.split()
        if len(words) > 4:
            middle = words[1:-1]
            random.shuffle(middle)
            words = [words[0]] + middle + [words[-1]]
        result.append(" ".join(words))
    return ".".join(result)

def augment_text(text: str) -> list:
    """Generate augmented versions of a text."""
    augmented = []
    # Synonym replacement
    augmented.append(synonym_replacement(text, n=2))
    # Word shuffle
    augmented.append(word_shuffle(text))
    return augmented

def generate_synthetic(aspect_id: int, model: str = "qwen3:8b") -> str:
    """Generate synthetic post for an aspect using Qwen."""
    aspect_name = ASPECT_NAMES.get(aspect_id, "stress")

    prompt = f"""Viết một bài đăng ngắn (100-200 từ) trên diễn đàn Việt Nam về chủ đề stress liên quan đến: {aspect_name}

Yêu cầu:
- Viết như người thật chia sẻ vấn đề của họ
- Dùng ngôn ngữ tự nhiên, có thể có tiếng lóng
- Thể hiện cảm xúc chân thật về stress
- KHÔNG dùng markdown hay format đặc biệt

Bài viết:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 400}
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"Error generating synthetic: {e}")
        return ""

def analyze_distribution(input_path: str) -> dict:
    """Analyze aspect distribution in dataset."""
    aspect_counts = Counter()
    total = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                aspects = record.get("aspects", [])
                for a in aspects:
                    aspect_counts[a] += 1
                total += 1
            except json.JSONDecodeError:
                continue

    print(f"\nCurrent distribution ({total} posts):")
    for i in range(NUM_ASPECTS):
        count = aspect_counts.get(i, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {i}: {ASPECT_NAMES.get(i, 'Unknown')[:20]:20} - {count:5} ({pct:.1f}%)")

    return dict(aspect_counts)

def balance_dataset(input_path: str, augmented_path: str, synthetic_path: str,
                    target_coverage: float = 0.8, model: str = "qwen3:8b"):
    """Balance dataset through augmentation and synthetic generation."""
    Path(augmented_path).parent.mkdir(parents=True, exist_ok=True)
    Path(synthetic_path).parent.mkdir(parents=True, exist_ok=True)

    # Load data and analyze
    posts_by_aspect = {i: [] for i in range(NUM_ASPECTS)}
    all_posts = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                all_posts.append(record)
                for a in record.get("aspects", []):
                    posts_by_aspect[a].append(record)
            except json.JSONDecodeError:
                continue

    total = len(all_posts)
    target_count = int(total * target_coverage)
    print(f"\nTarget count per aspect: {target_count}")

    # Identify underrepresented aspects
    aspect_gaps = {}
    for i in range(NUM_ASPECTS):
        current = len(posts_by_aspect[i])
        if current < target_count:
            aspect_gaps[i] = target_count - current
            print(f"  Aspect {i} needs {aspect_gaps[i]} more samples")

    # Generate augmented samples (40% of gap)
    augmented_count = 0
    with open(augmented_path, "w", encoding="utf-8") as f:
        for aspect_id, gap in aspect_gaps.items():
            aug_target = int(gap * 0.4)
            source_posts = posts_by_aspect[aspect_id]

            if not source_posts:
                continue

            for i in range(aug_target):
                source = random.choice(source_posts)
                aug_texts = augment_text(source["text"])

                for aug_text in aug_texts[:1]:  # One augmentation per source
                    record = {
                        "post_id": f"aug_{aspect_id}_{augmented_count}",
                        "text": aug_text,
                        "aspects": source.get("aspects", []),
                        "source": "augmented",
                        "original_id": source["post_id"],
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    augmented_count += 1

    print(f"\nGenerated {augmented_count} augmented samples")

    # Generate synthetic samples (60% of gap)
    synthetic_count = 0
    with open(synthetic_path, "w", encoding="utf-8") as f:
        for aspect_id, gap in aspect_gaps.items():
            syn_target = int(gap * 0.6)
            print(f"\nGenerating {syn_target} synthetic posts for aspect {aspect_id}...")

            for i in range(syn_target):
                text = generate_synthetic(aspect_id, model)
                if text and len(text) > 50:
                    record = {
                        "post_id": f"syn_{aspect_id}_{synthetic_count}",
                        "text": text,
                        "aspects": [aspect_id],
                        "source": "synthetic",
                        "model": model,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    synthetic_count += 1

                if (i + 1) % 10 == 0:
                    print(f"  Generated {i+1}/{syn_target}")

                time.sleep(0.5)  # Rate limiting

    print(f"\nGenerated {synthetic_count} synthetic samples")
    print(f"\nTotal new samples: {augmented_count + synthetic_count}")

    return {"augmented": augmented_count, "synthetic": synthetic_count}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Balance dataset through augmentation")
    parser.add_argument("--input", "-i", default="data/labeled/qwen_labels.jsonl")
    parser.add_argument("--augmented", "-a", default="data/balanced/augmented.jsonl")
    parser.add_argument("--synthetic", "-s", default="data/balanced/synthetic.jsonl")
    parser.add_argument("--target-coverage", "-t", type=float, default=0.8)
    parser.add_argument("--model", "-m", default="qwen3:8b")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    if args.analyze_only:
        analyze_distribution(args.input)
    else:
        analyze_distribution(args.input)
        balance_dataset(args.input, args.augmented, args.synthetic,
                        args.target_coverage, args.model)
