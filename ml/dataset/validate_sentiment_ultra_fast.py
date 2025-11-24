#!/usr/bin/env python3
"""
ULTRA-FAST Sentiment Validation for ABSA (Optimized)

Improvements:
1. Shorter prompts (50% reduction)
2. Faster timeout (10s instead of 20s)
3. More workers (16 instead of 8)
4. Batch logging (every 10 samples)
5. Direct number extraction (no complex parsing)
"""

import json
import subprocess
import re
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
import sys

# Thread-safe progress
progress_lock = Lock()
progress_count = 0
log_file = None


def log(message):
    """Thread-safe logging with immediate output"""
    with progress_lock:
        # Print to console immediately with explicit flush
        print(message, flush=True)
        sys.stdout.flush()
        # Write to log file
        if log_file:
            log_file.write(message + '\n')
            log_file.flush()


def load_aspects(file='ml/lda/absa_mental_health_aspects.json'):
    """Load ABSA aspects"""
    with open(file, 'r', encoding='utf-8') as f:
        return json.load(f)['aspects']


def create_prompt(text: str, aspect: str) -> str:
    """Ultra-short prompt for speed"""
    return f"""Sentiment of "{aspect}" in this text? Reply ONLY -1, 0, or 1.

Text: {text[:300]}

Reply: """


def call_ollama(prompt: str, aspect_name: str = "", idx: int = -1) -> int:
    """Ollama call with 30s timeout (handles concurrent requests better)"""
    call_start = time.time()
    try:
        result = subprocess.run(
            ['ollama', 'run', 'llama3.1:8b'],
            input=prompt.encode('utf-8'),
            capture_output=True,
            timeout=30  # Increased for concurrent requests
        )

        output = result.stdout.decode('utf-8').strip()

        # Direct number extraction
        if '-1' in output[:5]:
            sentiment = -1
        elif '1' in output[:5]:
            sentiment = 1
        else:
            sentiment = 0

        elapsed = time.time() - call_start
        if idx >= 0 and aspect_name:
            log(f"    [{idx}] {aspect_name}: {sentiment} ({elapsed:.1f}s)")

        return sentiment

    except Exception as e:
        elapsed = time.time() - call_start
        if idx >= 0 and aspect_name:
            log(f"    [{idx}] {aspect_name}: ERROR ({elapsed:.1f}s) - {e}")
        return 0  # Default neutral


def process_sample(idx: int, row: pd.Series, aspects: list) -> dict:
    """Process single sample (optimized for pandas Series)"""
    global progress_count

    sample_start = time.time()
    log(f"\n  [{idx}] Starting sample (text length: {len(row['text'])} chars)")

    text = row['text']
    result = {'index': idx}

    # Only validate detected aspects (label=1)
    aspect_count = 0
    for i, aspect in enumerate(aspects):
        label_col = f'label_{i}_{aspect["aspect_name"]}'
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'

        # Use .get() for Series (handles missing columns)
        if row.get(label_col, 0) == 1:
            aspect_count += 1
            # Get sentiment
            prompt = create_prompt(text, aspect['aspect_name'])
            sentiment = call_ollama(prompt, aspect['aspect_name'], idx)
            result[sentiment_col] = sentiment
        else:
            result[sentiment_col] = 0

    sample_elapsed = time.time() - sample_start
    log(f"  [{idx}] Completed {aspect_count} aspects in {sample_elapsed:.1f}s")

    # Update progress
    with progress_lock:
        progress_count += 1
        log(f"✓ Progress: {progress_count}/1095 ({progress_count*100/1095:.1f}%)")

    return result


def main():
    global log_file, progress_count

    # Setup logging
    log_file = open('ml/dataset/labeled/sentiment_ultra_fast.log', 'w')

    log("="*70)
    log("ULTRA-FAST SENTIMENT VALIDATION")
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

    # Configuration - MUST use 1 worker (Ollama handles 1 request at a time)
    max_workers = 1
    log(f"\n2. Configuration:")
    log(f"   Workers: {max_workers} (Ollama processes sequentially)")
    log(f"   Timeout: 30s per call")
    log(f"   Estimated time: ~{int(total_aspects * 2 / max_workers / 60)} minutes (avg 2s/call)")
    log(f"   Note: Using 1 worker because Ollama can't handle concurrent requests")

    # Process in parallel
    log(f"\n3. Processing...")
    start_time = time.time()
    results = {}

    log(f"   DEBUG: Starting ThreadPoolExecutor with {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        log(f"   DEBUG: Submitting {len(df)} tasks using iterrows()...")
        # Use iterrows() instead of to_dict('records') - much faster!
        futures = {
            executor.submit(process_sample, idx, row, aspects): idx
            for idx, row in df.iterrows()
        }
        log(f"   DEBUG: All {len(futures)} tasks submitted. Waiting for completion...")

        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results[result['index']] = result
            except Exception as e:
                log(f"   ERROR at index {idx}: {e}")
                # Add empty sentiments
                results[idx] = {'index': idx}
                for i, aspect in enumerate(aspects):
                    results[idx][f'sentiment_{i}_{aspect["aspect_name"]}'] = 0

    # Build final DataFrame
    log(f"\n4. Building output...")
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
    log(f"✓ Speed: {len(df_final)/elapsed:.1f} samples/second")
    log(f"✓ Output: {output_file}")

    # Show sentiment distribution
    log(f"\nSENTIMENT DISTRIBUTION:")
    for i, aspect in enumerate(aspects):
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'
        if sentiment_col in df_final.columns:
            counts = df_final[sentiment_col].value_counts().sort_index()
            if len(counts) > 1:  # Only show if has sentiments
                log(f"\n{aspect['aspect_name']}:")
                for val, count in counts.items():
                    if val != 0:  # Skip neutral/not-applicable
                        label = {-1: "Negative", 1: "Positive"}.get(val, "Unknown")
                        log(f"  {label}: {count}")

    log_file.close()


if __name__ == "__main__":
    main()
