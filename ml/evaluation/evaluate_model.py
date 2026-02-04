#!/usr/bin/env python3
"""Evaluate trained PhoBERT model on test set."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from sklearn.metrics import (classification_report, f1_score,
                             precision_recall_fscore_support)

sys.path.append(str(Path(__file__).parent.parent / "training"))
from dataset import StressDataset
from model import PhoBERTStressClassifier

ASPECT_NAMES = [
    "occupational", "self_image", "health", "academic", "romantic",
    "familial", "financial", "life_events", "existential"
]


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def evaluate_model(model_dir: str, test_path: str, output_path: str, threshold: float = 0.5):
    """Full evaluation on test set."""
    device = get_device()
    print(f"Using device: {device}")

    # Load config
    model_path = Path(model_dir)
    with open(model_path / "config.yaml") as f:
        config = yaml.safe_load(f)

    # Load model
    print("Loading model...")
    model = PhoBERTStressClassifier.load(
        str(model_path / "best_model.pt"),
        model_name=config["model"]["name"],
        device=str(device)
    ).to(device)
    model.eval()

    # Load test data
    print("Loading test data...")
    test_dataset = StressDataset(
        test_path,
        config["model"]["name"],
        config["model"]["max_length"]
    )
    test_loader = torch.utils.data.DataLoader(
        test_dataset, batch_size=16, shuffle=False
    )

    # Collect predictions
    all_preds = []
    all_labels = []
    all_probs = []

    print("Running inference...")
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"]

            logits = model(input_ids, attention_mask)
            probs = torch.sigmoid(logits).cpu().numpy()
            preds = (probs > threshold).astype(int)

            all_probs.extend(probs)
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)

    # Calculate metrics
    print("\nCalculating metrics...")

    # Overall metrics
    f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    f1_micro = f1_score(all_labels, all_preds, average="micro", zero_division=0)

    precision, recall, f1, support = precision_recall_fscore_support(
        all_labels, all_preds, average=None, zero_division=0
    )

    # Per-aspect metrics
    per_aspect = {}
    for i, name in enumerate(ASPECT_NAMES):
        per_aspect[name] = {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i])
        }

    # Build report
    report = {
        "overall": {
            "f1_macro": float(f1_macro),
            "f1_micro": float(f1_micro),
            "precision_macro": float(np.mean(precision)),
            "recall_macro": float(np.mean(recall)),
            "total_samples": len(all_labels),
            "threshold": threshold
        },
        "per_aspect": per_aspect,
        "classification_report": classification_report(
            all_labels, all_preds,
            target_names=ASPECT_NAMES,
            zero_division=0,
            output_dict=True
        )
    }

    # Print summary
    print("\n" + "="*50)
    print("EVALUATION RESULTS")
    print("="*50)
    print(f"F1 Macro: {f1_macro:.4f}")
    print(f"F1 Micro: {f1_micro:.4f}")
    print(f"Precision: {np.mean(precision):.4f}")
    print(f"Recall: {np.mean(recall):.4f}")
    print("\nPer-aspect F1:")
    for name in ASPECT_NAMES:
        print(f"  {name:15}: {per_aspect[name]['f1']:.4f} (support: {per_aspect[name]['support']})")

    # Save report
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {output_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate PhoBERT model")
    parser.add_argument("--model", "-m", default="ml/checkpoints/phobert_stress_v1")
    parser.add_argument("--test", "-t", default="data/splits/test.jsonl")
    parser.add_argument("--output", "-o", default="reports/evaluation_v1.json")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    evaluate_model(args.model, args.test, args.output, args.threshold)
