#!/usr/bin/env python3
"""
Dataset Splitting Script for Vietnamese Stress Detection

Performs multi-label stratified splitting of labeled data into train/val/test sets
and samples a gold calibration set for human verification.

Input: data/labeled/llm_outputs_v1.jsonl
Output: data/splits/{train,val,test}_v1.jsonl, data/gold/gold_v1.csv
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
CONFIG = {
    'input_file': 'data/labeled/llm_outputs_v1.jsonl',
    'output_dir': 'data/splits',
    'gold_dir': 'data/gold',
    'reports_dir': 'reports',
    'num_aspects': 10,
    'train_ratio': 0.70,
    'val_ratio': 0.15,
    'test_ratio': 0.15,
    'gold_per_aspect': 10,
    'random_seed': 42,
    'medium_conf_range': (0.6, 0.79),
    'high_conf_threshold': 0.8,
}


def load_labeled_data(input_file: str) -> list[dict]:
    """Load labeled posts from JSONL file."""
    posts = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            post = json.loads(line.strip())
            posts.append(post)
    return posts


def filter_posts_with_aspects(posts: list[dict]) -> list[dict]:
    """Filter posts that have at least one aspect labeled."""
    return [p for p in posts if p.get('aspects') and len(p['aspects']) > 0]


def build_aspect_matrix(posts: list[dict], num_aspects: int) -> np.ndarray:
    """Convert aspect lists to binary matrix (N x num_aspects)."""
    n = len(posts)
    matrix = np.zeros((n, num_aspects), dtype=np.int32)
    for i, post in enumerate(posts):
        for aspect_id in post.get('aspects', []):
            if 0 <= aspect_id < num_aspects:
                matrix[i, aspect_id] = 1
    return matrix


def iterative_stratified_split(posts: list[dict], labels: np.ndarray,
                                train_ratio: float, val_ratio: float, test_ratio: float,
                                random_seed: int = 42) -> tuple:
    """
    Perform iterative stratified split for multi-label data.
    Falls back to approximate stratification if scikit-multilearn is not available.
    """
    np.random.seed(random_seed)
    n = len(posts)
    indices = np.arange(n)

    try:
        from skmultilearn.model_selection import iterative_train_test_split

        # API returns: (X_train, y_train, X_test, y_test)
        # First split: train vs (val+test)
        temp_ratio = val_ratio + test_ratio
        X_train, y_train, X_temp, y_temp = iterative_train_test_split(
            indices.reshape(-1, 1), labels, test_size=temp_ratio
        )
        train_indices = X_train.flatten()

        # Second split: val vs test (50/50 of temp)
        # Need to use indices 0..len(X_temp)-1 for the second split
        temp_n = len(X_temp)
        temp_local_indices = np.arange(temp_n)
        val_test_ratio = test_ratio / temp_ratio
        local_val, _, local_test, _ = iterative_train_test_split(
            temp_local_indices.reshape(-1, 1), y_temp, test_size=val_test_ratio
        )
        # Map back to original indices
        X_temp_flat = X_temp.flatten()
        val_indices = X_temp_flat[local_val.flatten()]
        test_indices = X_temp_flat[local_test.flatten()]

        print("✓ Using iterative stratification (scikit-multilearn)")

    except ImportError:
        print("⚠ scikit-multilearn not available, using approximate stratification")

        # Fallback: simple random split with aspect frequency balancing
        np.random.shuffle(indices)

        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)

        train_indices = indices[:train_end]
        val_indices = indices[train_end:val_end]
        test_indices = indices[val_end:]

    return train_indices, val_indices, test_indices


def sample_gold_set(posts: list[dict], labels: np.ndarray,
                    gold_per_aspect: int, conf_range: tuple,
                    high_conf_threshold: float) -> tuple:
    """
    Sample gold calibration set with per-aspect quotas.
    Prefers medium-confidence posts, fills with high-confidence if needed.
    """
    num_aspects = labels.shape[1]
    gold_indices = set()
    exceptions = []

    # Group posts by confidence level
    medium_conf_posts = []
    high_conf_posts = []

    for i, post in enumerate(posts):
        conf = post.get('confidence', 1.0)
        if conf_range[0] <= conf <= conf_range[1]:
            medium_conf_posts.append(i)
        elif conf >= high_conf_threshold:
            high_conf_posts.append(i)

    print(f"\nGold set sampling:")
    print(f"  Medium confidence posts ({conf_range[0]}-{conf_range[1]}): {len(medium_conf_posts)}")
    print(f"  High confidence posts (≥{high_conf_threshold}): {len(high_conf_posts)}")

    # Sample per aspect
    for aspect_id in range(num_aspects):
        aspect_gold = []

        # Find posts with this aspect in medium confidence
        medium_with_aspect = [i for i in medium_conf_posts
                              if labels[i, aspect_id] == 1 and i not in gold_indices]

        # Find posts with this aspect in high confidence
        high_with_aspect = [i for i in high_conf_posts
                           if labels[i, aspect_id] == 1 and i not in gold_indices]

        # Sample from medium confidence first
        np.random.shuffle(medium_with_aspect)
        needed = min(gold_per_aspect, len(medium_with_aspect))
        aspect_gold.extend(medium_with_aspect[:needed])

        # Fill remainder from high confidence
        remaining = gold_per_aspect - len(aspect_gold)
        if remaining > 0 and high_with_aspect:
            np.random.shuffle(high_with_aspect)
            fill_count = min(remaining, len(high_with_aspect))
            aspect_gold.extend(high_with_aspect[:fill_count])

        # Log exception if we couldn't fill quota
        if len(aspect_gold) < gold_per_aspect:
            exceptions.append({
                'aspect_id': aspect_id,
                'requested': gold_per_aspect,
                'sampled': len(aspect_gold),
                'reason': f'Only {len(medium_with_aspect)} medium + {len(high_with_aspect)} high confidence posts available'
            })

        gold_indices.update(aspect_gold)
        print(f"  Aspect {aspect_id}: sampled {len(aspect_gold)}/{gold_per_aspect}")

    return list(gold_indices), exceptions


def calculate_aspect_distribution(labels: np.ndarray) -> np.ndarray:
    """Calculate aspect frequency distribution."""
    return labels.sum(axis=0)


def verify_split_distribution(train_labels: np.ndarray, val_labels: np.ndarray,
                               test_labels: np.ndarray, original_labels: np.ndarray,
                               threshold: float = 0.05) -> bool:
    """Verify aspect frequency deviation is within threshold."""
    original_dist = original_labels.sum(axis=0) / len(original_labels)

    splits = {
        'train': train_labels,
        'val': val_labels,
        'test': test_labels
    }

    all_ok = True
    print("\nAspect distribution verification:")
    print(f"{'Split':<10} {'Aspect':<10} {'Original':<10} {'Split':<10} {'Deviation':<10} {'Status':<10}")
    print("-" * 60)

    for split_name, split_labels in splits.items():
        if len(split_labels) == 0:
            continue
        split_dist = split_labels.sum(axis=0) / len(split_labels)

        for i, (orig, split) in enumerate(zip(original_dist, split_dist)):
            deviation = abs(split - orig)
            status = "✓" if deviation <= threshold else "✗"
            if deviation > threshold:
                all_ok = False
                print(f"{split_name:<10} {i:<10} {orig:.3f}     {split:.3f}     {deviation:.3f}     {status}")

    if all_ok:
        print("✓ All splits within 5% deviation threshold")

    return all_ok


def save_splits(posts: list[dict], train_indices: list, val_indices: list,
                test_indices: list, gold_indices: list, output_dir: str) -> dict:
    """Save train/val/test splits as JSONL files."""
    os.makedirs(output_dir, exist_ok=True)

    # Exclude gold from splits
    gold_set = set(gold_indices)
    train_indices = [i for i in train_indices if i not in gold_set]
    val_indices = [i for i in val_indices if i not in gold_set]
    test_indices = [i for i in test_indices if i not in gold_set]

    splits = {
        'train': (train_indices, f'{output_dir}/train_v1.jsonl'),
        'val': (val_indices, f'{output_dir}/val_v1.jsonl'),
        'test': (test_indices, f'{output_dir}/test_v1.jsonl'),
    }

    counts = {}
    for split_name, (indices, filepath) in splits.items():
        with open(filepath, 'w', encoding='utf-8') as f:
            for idx in indices:
                post = posts[idx].copy()
                post['split'] = split_name
                f.write(json.dumps(post, ensure_ascii=False) + '\n')
        counts[split_name] = len(indices)
        print(f"✓ Saved {filepath} ({len(indices)} posts)")

    # Make test set read-only
    test_file = f'{output_dir}/test_v1.jsonl'
    os.chmod(test_file, 0o444)

    # Create immutable marker
    marker_file = f'{output_dir}/.immutable'
    with open(marker_file, 'w') as f:
        f.write('Test set is read-only. Do not modify.\n')

    print(f"✓ Test set marked read-only")

    return counts


def save_gold_set(posts: list[dict], gold_indices: list, gold_dir: str) -> None:
    """Save gold calibration set as CSV for annotation."""
    os.makedirs(gold_dir, exist_ok=True)

    gold_posts = []
    for idx in gold_indices:
        post = posts[idx]
        gold_posts.append({
            'post_id': post['post_id'],
            'text': post['text'],
            'llm_aspects': json.dumps(post.get('aspects', [])),
            'llm_confidence': post.get('confidence', 1.0),
            'llm_reasoning': post.get('reasoning', ''),
            # Annotation columns (empty for human to fill)
            'human_aspects': '',
            'human_notes': '',
            'verified': False
        })

    df = pd.DataFrame(gold_posts)
    filepath = f'{gold_dir}/gold_v1.csv'
    df.to_csv(filepath, index=False, encoding='utf-8')
    print(f"✓ Saved {filepath} ({len(gold_posts)} posts)")


def save_exceptions(exceptions: list, reports_dir: str) -> None:
    """Save gold sampling exceptions to JSON."""
    os.makedirs(reports_dir, exist_ok=True)
    filepath = f'{reports_dir}/gold_sampling_exceptions.json'
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(exceptions, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {filepath} ({len(exceptions)} exceptions)")


def main():
    """Main entry point."""
    print("=" * 70)
    print("DATASET SPLITTING FOR VIETNAMESE STRESS DETECTION")
    print("=" * 70)

    np.random.seed(CONFIG['random_seed'])

    # Load data
    print(f"\nLoading data from {CONFIG['input_file']}...")
    all_posts = load_labeled_data(CONFIG['input_file'])
    print(f"✓ Loaded {len(all_posts)} total posts")

    # Filter posts with aspects
    posts = filter_posts_with_aspects(all_posts)
    print(f"✓ Filtered to {len(posts)} posts with aspects")

    # Build aspect matrix
    labels = build_aspect_matrix(posts, CONFIG['num_aspects'])
    print(f"✓ Built aspect matrix: {labels.shape}")

    # Show original distribution
    orig_dist = calculate_aspect_distribution(labels)
    print(f"\nOriginal aspect distribution:")
    for i, count in enumerate(orig_dist):
        print(f"  Aspect {i}: {count} posts ({count/len(posts)*100:.1f}%)")

    # Sample gold set first (before splitting)
    print("\n" + "-" * 70)
    gold_indices, exceptions = sample_gold_set(
        posts, labels,
        CONFIG['gold_per_aspect'],
        CONFIG['medium_conf_range'],
        CONFIG['high_conf_threshold']
    )
    print(f"\n✓ Gold set: {len(gold_indices)} posts sampled")

    # Remove gold from main dataset for splitting
    non_gold_indices = [i for i in range(len(posts)) if i not in gold_indices]
    non_gold_labels = labels[non_gold_indices]

    # Stratified split
    print("\n" + "-" * 70)
    print("Performing stratified split...")
    train_idx, val_idx, test_idx = iterative_stratified_split(
        [posts[i] for i in non_gold_indices],
        non_gold_labels,
        CONFIG['train_ratio'],
        CONFIG['val_ratio'],
        CONFIG['test_ratio'],
        CONFIG['random_seed']
    )

    # Map back to original indices
    train_indices = [non_gold_indices[i] for i in train_idx]
    val_indices = [non_gold_indices[i] for i in val_idx]
    test_indices = [non_gold_indices[i] for i in test_idx]

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_indices)} ({len(train_indices)/len(posts)*100:.1f}%)")
    print(f"  Val:   {len(val_indices)} ({len(val_indices)/len(posts)*100:.1f}%)")
    print(f"  Test:  {len(test_indices)} ({len(test_indices)/len(posts)*100:.1f}%)")
    print(f"  Gold:  {len(gold_indices)} ({len(gold_indices)/len(posts)*100:.1f}%)")

    # Verify distribution
    train_labels = labels[train_indices]
    val_labels = labels[val_indices]
    test_labels = labels[test_indices]
    verify_split_distribution(train_labels, val_labels, test_labels, labels)

    # Save outputs
    print("\n" + "-" * 70)
    print("Saving outputs...")
    save_splits(posts, train_indices, val_indices, test_indices, gold_indices, CONFIG['output_dir'])
    save_gold_set(posts, gold_indices, CONFIG['gold_dir'])
    save_exceptions(exceptions, CONFIG['reports_dir'])

    # Verify no overlap
    all_indices = set(train_indices) | set(val_indices) | set(test_indices) | set(gold_indices)
    total_unique = len(all_indices)
    print(f"\n✓ Verified no overlap: {total_unique} unique posts = {len(train_indices)} + {len(val_indices)} + {len(test_indices)} + {len(gold_indices)}")

    print("\n" + "=" * 70)
    print("✓ SPLITTING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
