#!/usr/bin/env python3
"""Validate Qwen labels using Claude API with sampling."""

import json
import argparse
import os
import random
import time
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

ASPECTS = [
    "0: Công việc (Occupational)",
    "1: Hình ảnh bản thân (Self Image)",
    "2: Sức khỏe (Health)",
    "3: Học tập (Academic)",
    "4: Tình cảm (Romantic)",
    "5: Gia đình (Familial)",
    "6: Tài chính (Financial)",
    "7: Sự kiện (Life Events)",
    "8: Hiện sinh (Existential)",
]

VALIDATION_PROMPT = """Bạn đang xác thực nhãn phân loại stress cho bài viết tiếng Việt.

BÀI VIẾT:
{text}

NHÃN TỪ QWEN: {qwen_aspects}
LÝ DO QWEN: {reasoning}

CÁC KHÍA CẠNH STRESS:
{aspects_list}

NHIỆM VỤ:
1. Đọc bài viết và nhãn của Qwen
2. Đưa ra nhãn của bạn (danh sách ID)
3. Ghi nhận sự khác biệt nếu có
4. Đánh dấu cần xem xét thủ công nếu mơ hồ

TRẢ LỜI JSON:
{{"claude_aspects": [...], "agreement": true/false, "disagreement_reason": "...", "needs_human_review": true/false}}"""

def validate_with_claude(client: Anthropic, text: str, qwen_aspects: list,
                         reasoning: str) -> dict:
    """Call Claude to validate labels."""
    aspects_list = "\n".join(ASPECTS)
    prompt = VALIDATION_PROMPT.format(
        text=text[:1500],
        qwen_aspects=qwen_aspects,
        reasoning=reasoning,
        aspects_list=aspects_list
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        output = response.content[0].text

        # Parse JSON
        json_start = output.find("{")
        json_end = output.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            parsed = json.loads(output[json_start:json_end])
            return {
                "claude_aspects": parsed.get("claude_aspects", []),
                "agreement": parsed.get("agreement", False),
                "disagreement_reason": parsed.get("disagreement_reason", ""),
                "needs_human_review": parsed.get("needs_human_review", False)
            }
    except Exception as e:
        return {
            "claude_aspects": [],
            "agreement": False,
            "disagreement_reason": f"Error: {str(e)}",
            "needs_human_review": True
        }

    return {
        "claude_aspects": [],
        "agreement": False,
        "disagreement_reason": "Failed to parse response",
        "needs_human_review": True
    }

def calculate_agreement(qwen_aspects: list, claude_aspects: list) -> dict:
    """Calculate agreement metrics between two label sets."""
    qwen_set = set(qwen_aspects)
    claude_set = set(claude_aspects)

    intersection = qwen_set & claude_set
    union = qwen_set | claude_set

    if not union:
        jaccard = 1.0  # Both empty = agreement
    else:
        jaccard = len(intersection) / len(union)

    diff_count = len(qwen_set.symmetric_difference(claude_set))

    return {
        "jaccard": jaccard,
        "diff_count": diff_count,
        "exact_match": qwen_set == claude_set
    }

def validate_dataset(input_path: str, output_path: str, conflicts_path: str,
                     sample_rate: float = 0.2, seed: int = 42):
    """Validate a sample of Qwen labels with Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    client = Anthropic(api_key=api_key)
    random.seed(seed)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Load all posts
    posts = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                posts.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Sample posts
    sample_size = int(len(posts) * sample_rate)
    sampled = random.sample(posts, min(sample_size, len(posts)))
    print(f"Validating {len(sampled)} posts ({sample_rate*100:.0f}% of {len(posts)})")

    stats = {
        "total_validated": 0,
        "agreements": 0,
        "disagreements": 0,
        "needs_review": 0,
        "exact_matches": 0,
        "avg_jaccard": 0.0
    }

    jaccard_sum = 0.0
    conflicts = []

    with open(output_path, "w", encoding="utf-8") as fout:
        for i, post in enumerate(sampled):
            result = validate_with_claude(
                client,
                post["text"],
                post.get("aspects", []),
                post.get("reasoning", "")
            )

            agreement = calculate_agreement(
                post.get("aspects", []),
                result["claude_aspects"]
            )

            output_record = {
                "post_id": post["post_id"],
                "qwen_aspects": post.get("aspects", []),
                "claude_aspects": result["claude_aspects"],
                "agreement": result["agreement"],
                "disagreement_count": agreement["diff_count"],
                "jaccard": agreement["jaccard"],
                "exact_match": agreement["exact_match"],
                "claude_reasoning": result.get("disagreement_reason", ""),
                "needs_review": result["needs_human_review"] or agreement["diff_count"] > 2,
                "validated_at": datetime.utcnow().isoformat() + "Z"
            }

            fout.write(json.dumps(output_record, ensure_ascii=False) + "\n")

            # Update stats
            stats["total_validated"] += 1
            jaccard_sum += agreement["jaccard"]
            if agreement["exact_match"]:
                stats["exact_matches"] += 1
            if result["agreement"]:
                stats["agreements"] += 1
            else:
                stats["disagreements"] += 1
            if output_record["needs_review"]:
                stats["needs_review"] += 1
                conflicts.append({
                    "post_id": post["post_id"],
                    "text": post["text"][:200],
                    "qwen": post.get("aspects", []),
                    "claude": result["claude_aspects"]
                })

            if (i + 1) % 10 == 0:
                print(f"Validated {i+1}/{len(sampled)}...")

            # Rate limiting
            time.sleep(0.5)

    # Save conflicts
    if conflicts:
        with open(conflicts_path, "w", encoding="utf-8") as f:
            for c in conflicts:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    stats["avg_jaccard"] = jaccard_sum / stats["total_validated"] if stats["total_validated"] > 0 else 0

    print(f"\nValidation Stats:")
    print(f"  Total validated: {stats['total_validated']}")
    print(f"  Agreements: {stats['agreements']}")
    print(f"  Disagreements: {stats['disagreements']}")
    print(f"  Exact matches: {stats['exact_matches']}")
    print(f"  Needs review: {stats['needs_review']}")
    print(f"  Avg Jaccard: {stats['avg_jaccard']:.3f}")

    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Qwen labels with Claude")
    parser.add_argument("--input", "-i", default="data/labeled/qwen_labels.jsonl")
    parser.add_argument("--output", "-o", default="data/labeled/claude_validation.jsonl")
    parser.add_argument("--conflicts", "-c", default="data/labeled/conflicts.jsonl")
    parser.add_argument("--sample-rate", "-s", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    validate_dataset(args.input, args.output, args.conflicts, args.sample_rate, args.seed)
