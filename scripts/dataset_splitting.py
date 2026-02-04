#!/usr/bin/env python3
"""Split dataset into train/val/test with stratified sampling."""

import json
import argparse
from pathlib import Path
from collections import Counter, defaultdict
import random

NUM_ASPECTS = 9

def load_all_data(input_dir: str) -> list:
    """Load data from all JSONL files in directory."""
    all_data = []
    input_path = Path(input_dir)

    # Load from labeled (original Qwen labels)
    labeled_file = input_path.parent / "labeled" / "qwen_labels.jsonl"
    if labeled_file.exists():
        with open(labeled_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record["source"] = "original"
                    all_data.append(record)
                except json.JSONDecodeError:
                    continue
        print(f"Loaded {len(all_data)} original posts")

    # Load augmented
    aug_file = input_path / "augmented.jsonl"
    if aug_file.exists():
        aug_count = 0
        with open(aug_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record["source"] = "augmented"
                    all_data.append(record)
                    aug_count += 1
                except json.JSONDecodeError:
                    continue
        print(f"Loaded {aug_count} augmented posts")

    # Load synthetic
    syn_file = input_path / "synthetic.jsonl"
    if syn_file.exists():
        syn_count = 0
        with open(syn_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record["source"] = "synthetic"
                    all_data.append(record)
                    syn_count += 1
                except json.JSONDecodeError:
                    continue
        print(f"Loaded {syn_count} synthetic posts")

    return all_data

def convert_to_training_format(record: dict) -> dict:
    """Convert record to multi-label training format."""
    aspects = record.get("aspects", [])
    labels = [0] * NUM_ASPECTS
    for a in aspects:
        if 0 <= a < NUM_ASPECTS:
            labels[a] = 1

    return {
        "text": record["text"],
        "labels": labels,
        "source": record.get("source", "original"),
        "post_id": record.get("post_id", "")
    }

def stratified_split(data: list, train_ratio: float = 0.8,
                     val_ratio: float = 0.1, test_ratio: float = 0.1,
                     seed: int = 42) -> tuple:
    """Split data with stratification by primary aspect."""
    random.seed(seed)

    # Group by primary aspect (first aspect or -1 for none)
    aspect_groups = defaultdict(list)
    for record in data:
        aspects = record.get("aspects", [])
        primary = aspects[0] if aspects else -1
        aspect_groups[primary].append(record)

    train, val, test = [], [], []

    for aspect, records in aspect_groups.items():
        random.shuffle(records)
        n = len(records)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train.extend(records[:n_train])
        val.extend(records[n_train:n_train + n_val])
        test.extend(records[n_train + n_val:])

    # Shuffle final sets
    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    return train, val, test

def analyze_split(name: str, data: list):
    """Print distribution analysis for a split."""
    aspect_counts = Counter()
    source_counts = Counter()

    for record in data:
        for a in record.get("aspects", []):
            aspect_counts[a] += 1
        source_counts[record.get("source", "unknown")] += 1

    print(f"\n{name}: {len(data)} samples")
    print(f"  Sources: {dict(source_counts)}")
    print(f"  Aspects: ", end="")
    for i in range(NUM_ASPECTS):
        print(f"{i}:{aspect_counts.get(i, 0)} ", end="")
    print()

def split_dataset(input_dir: str, output_dir: str,
                  train_ratio: float = 0.8, val_ratio: float = 0.1,
                  test_ratio: float = 0.1, seed: int = 42):
    """Split dataset and save to files."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Load all data
    all_data = load_all_data(input_dir)
    print(f"\nTotal samples: {len(all_data)}")

    # Split
    train, val, test = stratified_split(all_data, train_ratio, val_ratio, test_ratio, seed)

    # Analyze
    analyze_split("Train", train)
    analyze_split("Val", val)
    analyze_split("Test", test)

    # Save
    for name, split_data in [("train", train), ("val", val), ("test", test)]:
        output_path = Path(output_dir) / f"{name}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for record in split_data:
                formatted = convert_to_training_format(record)
                f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
        print(f"\nSaved {output_path}: {len(split_data)} samples")

    # Save split stats
    stats = {
        "total": len(all_data),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "ratios": {
            "train": train_ratio,
            "val": val_ratio,
            "test": test_ratio
        },
        "seed": seed
    }
    with open(Path(output_dir) / "split_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split dataset into train/val/test")
    parser.add_argument("--input", "-i", default="data/balanced")
    parser.add_argument("--output", "-o", default="data/splits")
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--val", type=float, default=0.1)
    parser.add_argument("--test", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    split_dataset(args.input, args.output, args.train, args.val, args.test, args.seed)
