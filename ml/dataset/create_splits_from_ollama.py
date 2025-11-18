"""
Create train/val/test splits from Ollama-labeled data for Reddit Stress Detection
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split

def create_splits(
    input_file: str = "ml/dataset/labeled/reddit_crawl_ollama_labeled.csv",
    output_dir: str = "ml/dataset/splits",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    filter_confidence: str = "HIGH",
    exclude_unknown: bool = True,
    random_state: int = 42
):
    """
    Create train/val/test splits from Ollama-labeled data

    Args:
        input_file: Path to Ollama-labeled CSV
        output_dir: Directory to save splits
        train_ratio: Ratio for training set
        val_ratio: Ratio for validation set
        test_ratio: Ratio for test set
        filter_confidence: Only use rows with this confidence level (HIGH/MEDIUM/LOW/ALL)
        exclude_unknown: Exclude UNKNOWN labels
        random_state: Random seed for reproducibility
    """
    print("="*70)
    print("CREATING TRAIN/VAL/TEST SPLITS FROM OLLAMA-LABELED DATA")
    print("="*70)

    # Load data
    print(f"\n📂 Loading data from: {input_file}")
    df = pd.read_csv(input_file)
    print(f"   Total rows loaded: {len(df):,}")

    # Show label distribution
    print(f"\n📊 Original label distribution:")
    print(df['label'].value_counts())
    print(f"\n📊 Confidence distribution:")
    print(df['confidence'].value_counts())

    # Filter by confidence
    if filter_confidence != "ALL":
        print(f"\n🔍 Filtering for {filter_confidence} confidence...")
        df = df[df['confidence'] == filter_confidence].copy()
        print(f"   Rows after confidence filter: {len(df):,}")

    # Exclude UNKNOWN labels
    if exclude_unknown:
        print(f"\n🔍 Excluding UNKNOWN labels...")
        df = df[df['label'] != 'UNKNOWN'].copy()
        print(f"   Rows after UNKNOWN filter: {len(df):,}")

    # Show filtered label distribution
    print(f"\n📊 Filtered label distribution:")
    label_counts = df['label'].value_counts()
    print(label_counts)

    # Check class balance
    stress_pct = (label_counts.get('STRESS', 0) / len(df)) * 100 if len(df) > 0 else 0
    non_stress_pct = (label_counts.get('NON_STRESS', 0) / len(df)) * 100 if len(df) > 0 else 0
    print(f"\n   STRESS: {stress_pct:.1f}%")
    print(f"   NON_STRESS: {non_stress_pct:.1f}%")

    if len(df) == 0:
        print("\n❌ No data left after filtering!")
        return

    # Create binary labels (STRESS=1, NON_STRESS=0)
    df['binary_label'] = (df['label'] == 'STRESS').astype(int)

    # Combine title and body for text input
    df['text'] = df['title'].fillna('') + ' ' + df['body'].fillna('')
    df['text'] = df['text'].str.strip()

    # Remove empty texts
    df = df[df['text'].str.len() > 0].copy()
    print(f"\n   Rows after removing empty texts: {len(df):,}")

    # Split data
    print(f"\n✂️  Splitting data...")
    print(f"   Train: {train_ratio*100:.0f}%, Val: {val_ratio*100:.0f}%, Test: {test_ratio*100:.0f}%")

    # First split: train + (val+test)
    train_df, temp_df = train_test_split(
        df,
        test_size=(val_ratio + test_ratio),
        random_state=random_state,
        stratify=df['binary_label']  # Maintain class distribution
    )

    # Second split: val + test
    val_ratio_adjusted = val_ratio / (val_ratio + test_ratio)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=(1 - val_ratio_adjusted),
        random_state=random_state,
        stratify=temp_df['binary_label']
    )

    print(f"\n✓ Split complete:")
    print(f"   Training set:   {len(train_df):,} samples")
    print(f"   Validation set: {len(val_df):,} samples")
    print(f"   Test set:       {len(test_df):,} samples")

    # Show label distribution in each split
    print(f"\n📊 Label distribution in splits:")
    for name, split_df in [('Train', train_df), ('Val', val_df), ('Test', test_df)]:
        stress_count = (split_df['binary_label'] == 1).sum()
        non_stress_count = (split_df['binary_label'] == 0).sum()
        stress_pct = (stress_count / len(split_df)) * 100
        print(f"\n   {name}:")
        print(f"     STRESS:     {stress_count:,} ({stress_pct:.1f}%)")
        print(f"     NON_STRESS: {non_stress_count:,} ({100-stress_pct:.1f}%)")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Select columns to save
    columns_to_save = ['text', 'binary_label', 'label', 'post_id', 'subreddit', 'confidence']

    # Save splits
    print(f"\n💾 Saving splits to {output_dir}...")

    train_file = output_path / "train_v2.csv"
    val_file = output_path / "val_v2.csv"
    test_file = output_path / "test_v2.csv"

    train_df[columns_to_save].to_csv(train_file, index=False)
    val_df[columns_to_save].to_csv(val_file, index=False)
    test_df[columns_to_save].to_csv(test_file, index=False)

    print(f"   ✓ {train_file}")
    print(f"   ✓ {val_file}")
    print(f"   ✓ {test_file}")

    # Save dataset info
    info = {
        'source_file': input_file,
        'total_samples': len(df),
        'train_samples': len(train_df),
        'val_samples': len(val_df),
        'test_samples': len(test_df),
        'filter_confidence': filter_confidence,
        'exclude_unknown': exclude_unknown,
        'train_ratio': train_ratio,
        'val_ratio': val_ratio,
        'test_ratio': test_ratio,
        'random_state': random_state,
        'class_distribution': {
            'stress': int(label_counts.get('STRESS', 0)),
            'non_stress': int(label_counts.get('NON_STRESS', 0))
        }
    }

    info_file = output_path / "dataset_info_v2.txt"
    with open(info_file, 'w') as f:
        for key, value in info.items():
            f.write(f"{key}: {value}\n")
    print(f"   ✓ {info_file}")

    print("\n" + "="*70)
    print("✓ SPLITS CREATED SUCCESSFULLY!")
    print("="*70)

    return train_df, val_df, test_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create train/val/test splits from Ollama-labeled data")
    parser.add_argument("--input", default="ml/dataset/labeled/reddit_crawl_ollama_labeled.csv",
                        help="Input CSV file")
    parser.add_argument("--output-dir", default="ml/dataset/splits",
                        help="Output directory for splits")
    parser.add_argument("--train-ratio", type=float, default=0.7,
                        help="Training set ratio")
    parser.add_argument("--val-ratio", type=float, default=0.15,
                        help="Validation set ratio")
    parser.add_argument("--test-ratio", type=float, default=0.15,
                        help="Test set ratio")
    parser.add_argument("--confidence", default="HIGH",
                        choices=["HIGH", "MEDIUM", "LOW", "ALL"],
                        help="Filter by confidence level")
    parser.add_argument("--include-unknown", action="store_true",
                        help="Include UNKNOWN labels")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")

    args = parser.parse_args()

    create_splits(
        input_file=args.input,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        filter_confidence=args.confidence,
        exclude_unknown=not args.include_unknown,
        random_state=args.seed
    )
