#!/usr/bin/env python3
"""
PARALLEL Sentiment Validation with Multiple Ollama Instances

Strategy:
- Run 4 parallel workers (each with its own Ollama process)
- Use llama3.2:1b (much faster than llama3.1:8b)
- Process 4 posts simultaneously
- Each worker handles one post at a time sequentially
"""

import json
import subprocess
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import sys
import os

def log(message):
    """Simple logging"""
    print(message, flush=True)


def load_aspects(file='ml/lda/absa_mental_health_aspects.json'):
    """Load ABSA aspects"""
    with open(file, 'r', encoding='utf-8') as f:
        return json.load(f)['aspects']


def create_prompt(text: str, aspect: str) -> str:
    """Ultra-short prompt for speed"""
    return f"""Sentiment of "{aspect}" in this text? Reply ONLY -1, 0, or 1.

Text: {text[:300]}

Reply: """


def call_ollama_single(prompt: str, worker_id: int) -> int:
    """Single Ollama call (subprocess handles isolation)"""
    try:
        # Use llama3.2:1b (much faster!)
        result = subprocess.run(
            ['ollama', 'run', 'llama3.2:1b'],
            input=prompt.encode('utf-8'),
            capture_output=True,
            timeout=15  # Reduced timeout for 1b model
        )

        output = result.stdout.decode('utf-8').strip()

        # Direct number extraction
        if '-1' in output[:10]:
            return -1
        elif '1' in output[:10]:
            return 1
        else:
            return 0

    except Exception as e:
        return 0


def process_sample_worker(args):
    """Worker function for multiprocessing (each gets its own Ollama instance)"""
    idx, row_dict, aspects, worker_id = args

    text = row_dict['text']
    result = {'index': idx}

    aspect_count = 0
    start_time = time.time()

    # Only validate detected aspects (label=1)
    for i, aspect in enumerate(aspects):
        label_col = f'label_{i}_{aspect["aspect_name"]}'
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'

        if row_dict.get(label_col, 0) == 1:
            aspect_count += 1
            prompt = create_prompt(text, aspect['aspect_name'])
            sentiment = call_ollama_single(prompt, worker_id)
            result[sentiment_col] = sentiment
        else:
            result[sentiment_col] = 0

    elapsed = time.time() - start_time
    log(f"  [Worker {worker_id}] Post {idx}: {aspect_count} aspects in {elapsed:.1f}s")

    return result


def main():
    log("="*70)
    log("PARALLEL SENTIMENT VALIDATION (Multi-Process)")
    log("="*70)

    # Load data
    log("\n1. Loading data...")
    df = pd.read_csv('ml/dataset/labeled/vozforums_absa_labeled.csv')
    log(f"   Loaded {len(df)} samples")

    # Load aspects
    aspects = load_aspects()
    log(f"   Loaded {len(aspects)} aspects")

    # Count aspects to validate
    total_aspects = 0
    for i in range(10):
        col = f'label_{i}_{aspects[i]["aspect_name"]}'
        if col in df.columns:
            total_aspects += df[col].sum()

    log(f"   Total aspects to validate: {int(total_aspects)}")

    # Configuration
    max_workers = 4  # 4 separate processes = 4 Ollama instances
    log(f"\n2. Configuration:")
    log(f"   Workers: {max_workers} (4 separate Ollama processes)")
    log(f"   Model: llama3.2:1b (faster than 8b)")
    log(f"   Estimated time: ~{int(total_aspects * 1 / max_workers / 60)} minutes (avg 1s/call)")

    # Convert DataFrame to list of dicts for multiprocessing
    log(f"\n3. Preparing data for parallel processing...")
    rows = df.to_dict('records')

    # Create work items with worker IDs
    work_items = [
        (idx, row, aspects, idx % max_workers)
        for idx, row in enumerate(rows)
    ]

    # Process in parallel using separate processes
    log(f"\n4. Processing with {max_workers} parallel workers...")
    start_time = time.time()
    results = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_sample_worker, item): item[0]
            for item in work_items
        }

        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results[result['index']] = result
                completed += 1

                if completed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (len(df) - completed) / rate if rate > 0 else 0
                    log(f"✓ Progress: {completed}/{len(df)} ({completed*100/len(df):.1f}%) - {rate:.1f} posts/s - ETA: {remaining/60:.1f}m")

            except Exception as e:
                log(f"   ERROR at index {idx}: {e}")
                # Add empty sentiments
                results[idx] = {'index': idx}
                for i, aspect in enumerate(aspects):
                    results[idx][f'sentiment_{i}_{aspect["aspect_name"]}'] = 0

    # Build final DataFrame
    log(f"\n5. Building output...")
    sentiment_data = []
    for i in range(len(df)):
        if i in results:
            sentiment_data.append(results[i])

    # Merge with original
    df_sentiments = pd.DataFrame(sentiment_data)
    df_final = df.copy()

    for col in df_sentiments.columns:
        if col != 'index':
            df_final[col] = df_sentiments[col]

    # Save
    output_file = 'ml/dataset/labeled/vozforums_absa_sentiment.csv'
    df_final.to_csv(output_file, index=False)

    elapsed = time.time() - start_time

    log(f"\n{'='*70}")
    log("VALIDATION COMPLETE")
    log("="*70)
    log(f"✓ Processed: {len(df_final)} samples")
    log(f"✓ Time: {elapsed/60:.1f} minutes")
    log(f"✓ Speed: {len(df_final)/elapsed:.2f} samples/second")
    log(f"✓ Output: {output_file}")

    # Show sentiment distribution
    log(f"\nSENTIMENT DISTRIBUTION:")
    for i, aspect in enumerate(aspects):
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'
        if sentiment_col in df_final.columns:
            counts = df_final[sentiment_col].value_counts().sort_index()
            if len(counts) > 1:
                log(f"\n{aspect['aspect_name']}:")
                for val, count in counts.items():
                    if val != 0:
                        label = {-1: "Negative", 1: "Positive"}.get(val, "Unknown")
                        log(f"  {label}: {count}")


if __name__ == "__main__":
    main()
