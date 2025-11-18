"""
Data Loading and Preprocessing Utilities for Stress Detection Model

This module provides utilities for loading and preprocessing the Reddit dataset
for model training.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StressDataset:
    """Dataset loader for stress detection training"""

    def __init__(self, data_dir: str = "ml/dataset/splits", file_suffix: str = ""):
        """
        Initialize dataset loader

        Args:
            data_dir: Directory containing train/val/test splits
            file_suffix: Optional suffix for file names (e.g., "_v2" for train_v2.csv)
        """
        self.data_dir = Path(data_dir)
        self.file_suffix = file_suffix
        self.train_df = None
        self.val_df = None
        self.test_df = None

    def load_splits(self) -> Dict[str, pd.DataFrame]:
        """
        Load train/val/test splits from CSV files

        Returns:
            Dictionary with 'train', 'val', 'test' DataFrames
        """
        logger.info(f"Loading data from {self.data_dir}")

        train_path = self.data_dir / f"train{self.file_suffix}.csv"
        val_path = self.data_dir / f"val{self.file_suffix}.csv"
        test_path = self.data_dir / f"test{self.file_suffix}.csv"

        if not train_path.exists():
            raise FileNotFoundError(
                f"Training data not found at {train_path}. "
                "Please run dataset preparation first (TASK-018)."
            )

        self.train_df = pd.read_csv(train_path)
        self.val_df = pd.read_csv(val_path)
        self.test_df = pd.read_csv(test_path)

        logger.info(f"Loaded {len(self.train_df)} train, {len(self.val_df)} val, {len(self.test_df)} test samples")

        return {
            'train': self.train_df,
            'val': self.val_df,
            'test': self.test_df
        }

    def get_texts_and_labels(self, split: str = 'train') -> Tuple[List[str], List[int]]:
        """
        Get texts and labels for a specific split

        Args:
            split: One of 'train', 'val', 'test'

        Returns:
            Tuple of (texts, labels) where labels are 0/1 integers
        """
        df_map = {
            'train': self.train_df,
            'val': self.val_df,
            'test': self.test_df
        }

        df = df_map.get(split)
        if df is None:
            raise ValueError(f"Invalid split: {split}. Must be one of {list(df_map.keys())}")

        texts = df['text'].tolist()

        # Convert labels to binary (1 = STRESS, 0 = NON_STRESS)
        if 'label' in df.columns:
            labels = (df['label'] == 'STRESS').astype(int).tolist()
        else:
            raise ValueError("Dataset must have 'label' column")

        return texts, labels

    def get_dataset_stats(self) -> Dict:
        """
        Get statistics about the dataset

        Returns:
            Dictionary with dataset statistics
        """
        if self.train_df is None:
            raise ValueError("Dataset not loaded. Call load_splits() first.")

        stats = {}

        for split_name, df in [('train', self.train_df), ('val', self.val_df), ('test', self.test_df)]:
            stats[split_name] = {
                'total_samples': len(df),
                'stress_samples': (df['label'] == 'STRESS').sum(),
                'non_stress_samples': (df['label'] == 'NON_STRESS').sum(),
                'stress_ratio': (df['label'] == 'STRESS').mean(),
                'avg_text_length': df['text'].str.len().mean(),
                'max_text_length': df['text'].str.len().max(),
                'min_text_length': df['text'].str.len().min()
            }

        return stats

    def print_stats(self):
        """Print dataset statistics"""
        stats = self.get_dataset_stats()

        print("\n" + "="*60)
        print("DATASET STATISTICS")
        print("="*60)

        for split_name, split_stats in stats.items():
            print(f"\n{split_name.upper()} SET:")
            print(f"  Total samples: {split_stats['total_samples']}")
            print(f"  STRESS: {split_stats['stress_samples']} ({split_stats['stress_ratio']:.1%})")
            print(f"  NON_STRESS: {split_stats['non_stress_samples']} ({1-split_stats['stress_ratio']:.1%})")
            print(f"  Avg text length: {split_stats['avg_text_length']:.0f} chars")
            print(f"  Text length range: [{split_stats['min_text_length']}, {split_stats['max_text_length']}]")

        print("\n" + "="*60 + "\n")


def create_sample_dataset(output_dir: str = "ml/dataset/splits", num_samples: int = 1000):
    """
    Create a small sample dataset for testing the training pipeline

    This is useful when real labeled data is not yet available.

    Args:
        output_dir: Directory to save sample splits
        num_samples: Total number of samples to generate
    """
    logger.info(f"Creating sample dataset with {num_samples} samples")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Sample stress-related texts
    stress_templates = [
        "I'm feeling so overwhelmed with work and can't handle it anymore",
        "Having a really hard time coping with everything lately",
        "The anxiety is getting too much, I don't know what to do",
        "Feeling stressed out and exhausted all the time",
        "I'm worried I'm going to fail and disappoint everyone",
        "Can't sleep, can't eat, everything feels like too much",
        "This pressure is crushing me, I need help",
        "Feeling like I'm drowning in responsibilities",
        "My stress levels are through the roof lately",
        "Breaking down crying because of all this stress"
    ]

    non_stress_templates = [
        "Just finished reading a great book, highly recommend it",
        "Looking for advice on which laptop to buy for college",
        "What are your favorite pizza toppings?",
        "Does anyone know how to fix a leaky faucet?",
        "Planning a trip to Europe next summer, any tips?",
        "Trying to decide between two job offers, what would you do?",
        "What's the best way to learn Python programming?",
        "Just adopted a puppy, he's so cute!",
        "Recommendations for a good coffee maker?",
        "What TV shows are you watching these days?"
    ]

    # Generate samples
    data = []
    for i in range(num_samples):
        if i % 2 == 0:  # 50/50 split
            text = np.random.choice(stress_templates)
            label = "STRESS"
        else:
            text = np.random.choice(non_stress_templates)
            label = "NON_STRESS"

        # Add some variation
        text = text + f" (sample {i})"

        data.append({
            'post_id': f'sample_{i}',
            'text': text,
            'label': label,
            'subreddit': 'sample',
            'created_utc': 1700000000 + i
        })

    # Create DataFrame
    df = pd.DataFrame(data)

    # Split into train/val/test (70/15/15)
    train_size = int(0.7 * len(df))
    val_size = int(0.15 * len(df))

    train_df = df[:train_size]
    val_df = df[train_size:train_size + val_size]
    test_df = df[train_size + val_size:]

    # Save splits
    train_df.to_csv(output_path / "train.csv", index=False)
    val_df.to_csv(output_path / "val.csv", index=False)
    test_df.to_csv(output_path / "test.csv", index=False)

    logger.info(f"Created sample dataset:")
    logger.info(f"  Train: {len(train_df)} samples")
    logger.info(f"  Val: {len(val_df)} samples")
    logger.info(f"  Test: {len(test_df)} samples")
    logger.info(f"  Saved to: {output_path}")

    return train_df, val_df, test_df


if __name__ == "__main__":
    # Test the data loader
    print("Testing StressDataset loader...")

    # Create sample dataset if needed
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--create-sample":
        create_sample_dataset(num_samples=1000)
        print("\nSample dataset created successfully!")

    # Load and display stats
    try:
        dataset = StressDataset()
        dataset.load_splits()
        dataset.print_stats()

        # Test getting texts and labels
        texts, labels = dataset.get_texts_and_labels('train')
        print(f"Sample text: {texts[0]}")
        print(f"Sample label: {labels[0]}")

    except FileNotFoundError as e:
        print(f"\n{e}")
        print("\nRun with --create-sample to create a sample dataset for testing:")
        print("  python ml/models/data_loader.py --create-sample")
