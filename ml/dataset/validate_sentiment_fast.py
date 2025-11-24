#!/usr/bin/env python3
"""
Fast Sentiment Validation for ABSA Labeled Data
Uses multi-threading to validate aspect sentiments: -1 (negative), 0 (neutral), 1 (positive)
"""

import json
import subprocess
import re
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm
import time

# Thread-safe progress tracking
progress_lock = Lock()
validated_count = 0


def load_aspects(aspects_file='ml/lda/absa_mental_health_aspects.json'):
    """Load ABSA aspects"""
    with open(aspects_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data['aspects']


def create_sentiment_prompt(text: str, aspect_name: str, aspect_relevance: str) -> str:
    """
    Create Ollama prompt for aspect sentiment classification

    Returns: -1 (negative), 0 (neutral), 1 (positive)
    """
    prompt = f"""Phân tích cảm xúc của khía cạnh trong bài viết.

BÀI VIẾT:
\"\"\"{text[:500]}\"\"\"

KHÍA CẠNH CẦN PHÂN TÍCH: {aspect_name}
Ý NGHĨA: {aspect_relevance}

NHIỆM VỤ:
Xác định cảm xúc của khía cạnh "{aspect_name}" trong bài viết:
- -1 = TIÊU CỰC (negative): stress, buồn, lo lắng, áp lực, khó khăn
- 0 = TRUNG TÍNH (neutral): bình thường, không rõ cảm xúc, khách quan
- 1 = TÍCH CỰC (positive): vui, hạnh phúc, cải thiện, giải quyết được

CHỈ TRẢ VỀ MỘT SỐ: -1, 0, hoặc 1

VÍ DỤ:
- "Công việc quá stress, áp lực" → -1
- "Công việc bình thường" → 0
- "Công việc suôn sẻ, vui vẻ" → 1

CHỈ TRẢ VỀ MỘT SỐ, KHÔNG GIẢI THÍCH:"""

    return prompt


def call_ollama_sentiment(prompt: str, max_retries: int = 2) -> int:
    """
    Call Ollama for sentiment classification

    Returns: -1, 0, or 1
    """
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b'],
                input=prompt.encode('utf-8'),
                capture_output=True,
                timeout=20  # Faster timeout for sentiment
            )

            output = result.stdout.decode('utf-8').strip()

            # Extract number: -1, 0, or 1
            # Try direct match first
            if output in ['-1', '0', '1']:
                return int(output)

            # Try finding number in output
            number_match = re.search(r'(-1|0|1)', output)
            if number_match:
                return int(number_match.group(1))

            # Default to neutral if unclear
            if attempt < max_retries - 1:
                continue
            return 0  # Neutral as fallback

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                continue
            return 0
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return 0

    return 0


def validate_single_sample(row_data: dict, aspects: list) -> dict:
    """
    Validate sentiments for a single sample

    Args:
        row_data: Dict with 'text' and label columns
        aspects: List of aspect definitions

    Returns:
        Dict with sentiment columns added
    """
    global validated_count

    text = row_data['text']
    result = row_data.copy()

    # For each aspect that has label=1 (detected), get sentiment
    for i, aspect in enumerate(aspects):
        label_col = f'label_{i}_{aspect["aspect_name"]}'
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'

        if row_data.get(label_col, 0) == 1:
            # Aspect is present, get sentiment
            prompt = create_sentiment_prompt(
                text,
                aspect['aspect_name'],
                aspect.get('mental_health_relevance', '')
            )

            sentiment = call_ollama_sentiment(prompt)
            result[sentiment_col] = sentiment
        else:
            # Aspect not present, no sentiment
            result[sentiment_col] = 0  # Neutral/not applicable

    with progress_lock:
        validated_count += 1

    return result


def validate_batch_parallel(df: pd.DataFrame, aspects: list, max_workers: int = 8) -> pd.DataFrame:
    """
    Validate sentiments in parallel using ThreadPoolExecutor

    Args:
        df: Input DataFrame with ABSA labels
        aspects: List of aspect definitions
        max_workers: Number of parallel threads

    Returns:
        DataFrame with sentiment columns added
    """
    global validated_count
    validated_count = 0

    print(f"\nValidating {len(df)} samples with {max_workers} parallel workers...")
    print("This will take approximately {:.1f} minutes".format(len(df) * 3 / max_workers / 60))

    # Convert DataFrame rows to dicts
    rows = df.to_dict('records')

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(validate_single_sample, row, aspects): i
            for i, row in enumerate(rows)
        }

        # Process completed tasks with progress bar
        with tqdm(total=len(df), desc="Validating sentiments") as pbar:
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append((futures[future], result))
                except Exception as e:
                    print(f"\nError processing sample: {e}")
                    # Add original row with neutral sentiments
                    idx = futures[future]
                    result = rows[idx].copy()
                    for i, aspect in enumerate(aspects):
                        result[f'sentiment_{i}_{aspect["aspect_name"]}'] = 0
                    results.append((idx, result))

                pbar.update(1)

    # Sort by original index and create new DataFrame
    results.sort(key=lambda x: x[0])
    validated_rows = [r[1] for r in results]

    return pd.DataFrame(validated_rows)


def main():
    print("="*70)
    print("FAST SENTIMENT VALIDATION FOR ABSA DATA")
    print("="*70)

    # Configuration
    input_file = 'ml/dataset/labeled/vozforums_absa_labeled.csv'
    output_file = 'ml/dataset/labeled/vozforums_absa_sentiment.csv'
    max_workers = 8  # Parallel threads

    # Load data
    print(f"\nLoading data from {input_file}...")
    df = pd.read_csv(input_file)
    print(f"✓ Loaded {len(df)} samples")

    # Load aspects
    aspects = load_aspects()
    print(f"✓ Loaded {len(aspects)} aspects")

    # Count aspects to validate
    total_aspects = 0
    for i in range(10):
        col = f'label_{i}_{aspects[i]["aspect_name"]}'
        if col in df.columns:
            total_aspects += df[col].sum()

    print(f"✓ Total aspects to validate: {int(total_aspects)}")
    print(f"✓ Using {max_workers} parallel workers")

    # Validate in parallel
    start_time = time.time()
    df_validated = validate_batch_parallel(df, aspects, max_workers=max_workers)
    elapsed = time.time() - start_time

    # Save results
    df_validated.to_csv(output_file, index=False)

    print(f"\n{'='*70}")
    print("VALIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"✓ Validated {len(df_validated)} samples")
    print(f"✓ Time taken: {elapsed/60:.1f} minutes")
    print(f"✓ Speed: {len(df_validated)/elapsed:.1f} samples/second")
    print(f"✓ Saved to: {output_file}")

    # Show sentiment distribution
    print(f"\nSENTIMENT DISTRIBUTION:")
    for i, aspect in enumerate(aspects):
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'
        if sentiment_col in df_validated.columns:
            counts = df_validated[sentiment_col].value_counts().sort_index()
            print(f"\n{aspect['aspect_name']}:")
            for val, count in counts.items():
                label = {-1: "Negative", 0: "Neutral", 1: "Positive"}.get(val, "Unknown")
                print(f"  {label:9s} ({val:2d}): {count:4d}")


if __name__ == "__main__":
    main()
