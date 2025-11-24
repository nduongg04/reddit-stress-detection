#!/usr/bin/env python3
"""
Prepare Training Dataset from r/vozforums Collection

Selects:
- 200 stress posts from new 1k r/vozforums collection
- 200 non-stress posts from existing old data (before vozforums collection)

Total: 400 balanced posts for multi-label classification training
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import random

# Input files
VOZFORUMS_POSTS = "ml/dataset/raw/vozforums_stress_posts.csv"
OLD_POSTS = "ml/dataset/raw/vietnamese_posts.csv"  # Old data before vozforums

# Output
OUTPUT_DIR = "ml/dataset/splits"
TRAIN_FILE = Path(OUTPUT_DIR) / "train_multilabel.csv"
VAL_FILE = Path(OUTPUT_DIR) / "val_multilabel.csv"
TEST_FILE = Path(OUTPUT_DIR) / "test_multilabel.csv"

def load_data():
    """Load vozforums and old datasets."""
    print("Loading datasets...")

    vozforums_df = pd.read_csv(VOZFORUMS_POSTS)
    print(f"  Vozforums posts: {len(vozforums_df)}")

    old_df = pd.read_csv(OLD_POSTS)
    print(f"  Old posts: {len(old_df)}")

    return vozforums_df, old_df

def select_stress_posts(vozforums_df, n=200):
    """Select 200 random stress posts from vozforums."""
    if len(vozforums_df) < n:
        print(f"Warning: Only {len(vozforums_df)} vozforums posts available (requested {n})")
        return vozforums_df

    # Random sample
    selected = vozforums_df.sample(n=n, random_state=42)
    selected['label'] = 1  # STRESS

    print(f"  Selected {len(selected)} stress posts from vozforums")
    return selected

def select_non_stress_posts(old_df, n=200):
    """Select 200 non-stress posts from old data."""
    # Filter for likely non-stress posts (avoid stress keywords)
    stress_keywords = ['stress', 'trầm cảm', 'lo âu', 'căng thẳng', 'thất bại', 'mệt mỏi']

    def is_non_stress(text):
        text_lower = str(text).lower()
        return not any(kw in text_lower for kw in stress_keywords)

    non_stress_df = old_df[old_df.apply(
        lambda row: is_non_stress(str(row.get('title', '')) + ' ' + str(row.get('body', ''))),
        axis=1
    )]

    print(f"  Found {len(non_stress_df)} potential non-stress posts in old data")

    if len(non_stress_df) < n:
        print(f"Warning: Only {len(non_stress_df)} non-stress posts available (requested {n})")
        selected = non_stress_df
    else:
        selected = non_stress_df.sample(n=n, random_state=42)

    selected['label'] = 0  # NON_STRESS

    print(f"  Selected {len(selected)} non-stress posts from old data")
    return selected

def create_splits(stress_df, non_stress_df):
    """Create train/val/test splits (70/15/15)."""
    # Combine
    combined_df = pd.concat([stress_df, non_stress_df], ignore_index=True)

    # Shuffle
    combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\nCombined dataset: {len(combined_df)} posts")
    print(f"  Stress: {len(stress_df)}")
    print(f"  Non-stress: {len(non_stress_df)}")

    # Split indices
    n = len(combined_df)
    train_end = int(0.7 * n)
    val_end = int(0.85 * n)

    train_df = combined_df.iloc[:train_end]
    val_df = combined_df.iloc[train_end:val_end]
    test_df = combined_df.iloc[val_end:]

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_df)} ({len(train_df[train_df.label == 1])} stress)")
    print(f"  Val:   {len(val_df)} ({len(val_df[val_df.label == 1])} stress)")
    print(f"  Test:  {len(test_df)} ({len(test_df[test_df.label == 1])} stress)")

    return train_df, val_df, test_df

def save_splits(train_df, val_df, test_df):
    """Save train/val/test CSVs."""
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Select relevant columns
    columns = ['text', 'label']

    # Create 'text' column from title + body
    for df in [train_df, val_df, test_df]:
        df['text'] = df['title'].fillna('') + ' ' + df['body'].fillna('')

    train_df[columns].to_csv(TRAIN_FILE, index=False)
    val_df[columns].to_csv(VAL_FILE, index=False)
    test_df[columns].to_csv(TEST_FILE, index=False)

    print(f"\n✓ Datasets saved:")
    print(f"  {TRAIN_FILE}")
    print(f"  {VAL_FILE}")
    print(f"  {TEST_FILE}")

def main():
    print("="*70)
    print("Preparing Training Dataset (200 stress + 200 non-stress)")
    print("="*70)
    print()

    # Load data
    vozforums_df, old_df = load_data()
    print()

    # Select samples
    stress_df = select_stress_posts(vozforums_df, n=200)
    non_stress_df = select_non_stress_posts(old_df, n=200)

    # Create splits
    train_df, val_df, test_df = create_splits(stress_df, non_stress_df)

    # Save
    save_splits(train_df, val_df, test_df)

    print("\n" + "="*70)
    print("Dataset preparation complete!")
    print("="*70)
    print("\nNext step:")
    print("  Train multi-label model: python ml/models/train.py --multi-label ...")

if __name__ == '__main__':
    main()
