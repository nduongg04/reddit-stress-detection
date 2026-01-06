#!/usr/bin/env python3
"""
Sprint 7: Model Evaluation & Error Analysis

Evaluates trained PhoBERT model on test set and generates:
- Global metrics (Micro-F1, Macro-F1, Hamming Loss, Exact Match)
- Per-aspect metrics (Precision, Recall, F1, Support, FNR)
- Co-occurrence confusion matrix (10x10)
- Error examples (5 FP + 5 FN per aspect)
- Platt scaling calibration
"""

import json
import os
import sys
import pickle
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics import (
    f1_score, precision_score, recall_score,
    hamming_loss, accuracy_score
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Any
from tqdm import tqdm


# Configuration
CONFIG = {
    'model_dir': 'ml/models/phobert_stress_v2',
    'test_file': 'data/splits/test_v1.jsonl',
    'val_file': 'data/splits/val_v1.jsonl',
    'aspects_file': 'config/aspects_v1.json',
    'output_dir': 'reports',
    'batch_size': 16,
    'max_length': 256,
    'device': 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu',
    'high_risk_aspects': {4: 0.20, 6: 0.25, 8: 0.20},  # Health, Existential, Life_Events
}


class PhoBERTMultiLabelClassifier(nn.Module):
    """PhoBERT with multi-label classification head."""

    def __init__(self, model_name: str, num_aspects: int, hidden_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        self.hidden_size = self.phobert.config.hidden_size

        self.classifier = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_aspects)
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(pooled_output)
        return logits


class EvalDataset(Dataset):
    """Dataset for evaluation."""

    def __init__(self, data: List[Dict], tokenizer, max_length: int, num_aspects: int = 10):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.num_aspects = num_aspects

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        text = item['text']

        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        # Create multi-hot label vector
        labels = torch.zeros(self.num_aspects, dtype=torch.float)
        for aspect_id in item.get('aspects', []):
            if 0 <= aspect_id < self.num_aspects:
                labels[aspect_id] = 1.0

        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': labels,
            'post_id': item.get('post_id', str(idx)),
            'text': text
        }


def load_jsonl(filepath: str) -> List[Dict]:
    """Load JSONL file."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_aspects(filepath: str) -> Dict:
    """Load aspect definitions."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_model(model_dir: str, device: str) -> Tuple[PhoBERTMultiLabelClassifier, AutoTokenizer, Dict]:
    """Load trained model and tokenizer."""
    config_path = os.path.join(model_dir, 'config.json')
    model_path = os.path.join(model_dir, 'model.pt')

    with open(config_path, 'r') as f:
        config = json.load(f)

    tokenizer = AutoTokenizer.from_pretrained(model_dir)

    model = PhoBERTMultiLabelClassifier(
        model_name=config['model_name'],
        num_aspects=config['num_aspects'],
        hidden_dim=config['hidden_dim'],
        dropout=config['dropout']
    )

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    # Handle both formats: direct state_dict or wrapped in dict
    if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    return model, tokenizer, config


def get_predictions(model, dataloader, device) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], List[str]]:
    """Get model predictions on dataset."""
    all_labels = []
    all_logits = []
    all_probs = []
    all_post_ids = []
    all_texts = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels']

            logits = model(input_ids, attention_mask)
            probs = torch.sigmoid(logits)

            all_labels.append(labels.numpy())
            all_logits.append(logits.cpu().numpy())
            all_probs.append(probs.cpu().numpy())
            all_post_ids.extend(batch['post_id'])
            all_texts.extend(batch['text'])

    return (
        np.vstack(all_labels),
        np.vstack(all_logits),
        np.vstack(all_probs),
        all_post_ids,
        all_texts
    )


def compute_global_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute global evaluation metrics."""
    metrics = {}

    # Micro-F1 (global TP/FP/FN)
    metrics['micro_f1'] = f1_score(y_true, y_pred, average='micro', zero_division=0)

    # Macro-F1 (avg of per-aspect F1)
    metrics['macro_f1'] = f1_score(y_true, y_pred, average='macro', zero_division=0)

    # Hamming Loss (fraction of wrong labels)
    metrics['hamming_loss'] = hamming_loss(y_true, y_pred)

    # Exact Match Ratio (all 10 correct)
    metrics['exact_match'] = accuracy_score(y_true, y_pred)

    return metrics


def compute_per_aspect_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    aspects: List[Dict]
) -> List[Dict]:
    """Compute per-aspect metrics including FNR."""
    per_aspect = []

    for i, aspect in enumerate(aspects):
        y_true_i = y_true[:, i]
        y_pred_i = y_pred[:, i]

        tp = np.sum((y_true_i == 1) & (y_pred_i == 1))
        fp = np.sum((y_true_i == 0) & (y_pred_i == 1))
        fn = np.sum((y_true_i == 1) & (y_pred_i == 0))
        tn = np.sum((y_true_i == 0) & (y_pred_i == 0))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        support = int(np.sum(y_true_i))
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0  # False Negative Rate

        per_aspect.append({
            'aspect_id': i,
            'aspect_name': aspect['name_en'],
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
            'support': support,
            'fnr': round(fnr, 4),
            'tp': int(tp),
            'fp': int(fp),
            'fn': int(fn),
            'tn': int(tn)
        })

    return per_aspect


def compute_cooccurrence_matrix(y_pred: np.ndarray) -> np.ndarray:
    """Compute 10x10 co-occurrence confusion matrix."""
    n_aspects = y_pred.shape[1]
    matrix = np.zeros((n_aspects, n_aspects), dtype=int)

    for sample in y_pred:
        active = np.where(sample == 1)[0]
        for i in active:
            for j in active:
                matrix[i, j] += 1

    return matrix


def extract_error_examples(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_probs: np.ndarray,
    post_ids: List[str],
    texts: List[str],
    aspects: List[Dict],
    n_examples: int = 5
) -> List[Dict]:
    """Extract FP and FN examples for each aspect."""
    errors = []

    for aspect_idx, aspect in enumerate(aspects):
        y_true_i = y_true[:, aspect_idx]
        y_pred_i = y_pred[:, aspect_idx]

        # False Positives: predicted 1, actual 0
        fp_indices = np.where((y_pred_i == 1) & (y_true_i == 0))[0]
        fp_scores = y_probs[fp_indices, aspect_idx] if len(fp_indices) > 0 else []
        fp_sorted = fp_indices[np.argsort(-fp_scores)][:n_examples] if len(fp_indices) > 0 else []

        for idx in fp_sorted:
            errors.append({
                'aspect_id': aspect_idx,
                'aspect_name': aspect['name_en'],
                'post_id': post_ids[idx],
                'text': texts[idx][:500],  # Truncate long texts
                'true_labels': y_true[idx].tolist(),
                'pred_labels': y_pred[idx].tolist(),
                'pred_scores': [round(float(s), 4) for s in y_probs[idx]],
                'error_type': 'FP'
            })

        # False Negatives: predicted 0, actual 1
        fn_indices = np.where((y_pred_i == 0) & (y_true_i == 1))[0]
        fn_scores = y_probs[fn_indices, aspect_idx] if len(fn_indices) > 0 else []
        fn_sorted = fn_indices[np.argsort(fn_scores)][:n_examples] if len(fn_indices) > 0 else []

        for idx in fn_sorted:
            errors.append({
                'aspect_id': aspect_idx,
                'aspect_name': aspect['name_en'],
                'post_id': post_ids[idx],
                'text': texts[idx][:500],
                'true_labels': y_true[idx].tolist(),
                'pred_labels': y_pred[idx].tolist(),
                'pred_scores': [round(float(s), 4) for s in y_probs[idx]],
                'error_type': 'FN'
            })

    return errors


class PlattScaler:
    """Platt scaling calibrator for multi-label classification."""

    def __init__(self, n_aspects: int):
        self.n_aspects = n_aspects
        self.calibrators = [LogisticRegression(solver='lbfgs', max_iter=1000) for _ in range(n_aspects)]

    def fit(self, logits: np.ndarray, y_true: np.ndarray):
        """Fit calibrators on validation set."""
        for i in range(self.n_aspects):
            X = logits[:, i].reshape(-1, 1)
            y = y_true[:, i]
            if len(np.unique(y)) > 1:
                self.calibrators[i].fit(X, y)
            else:
                # Handle single-class case
                self.calibrators[i] = None

    def predict_proba(self, logits: np.ndarray) -> np.ndarray:
        """Get calibrated probabilities."""
        calibrated = np.zeros_like(logits)
        for i in range(self.n_aspects):
            X = logits[:, i].reshape(-1, 1)
            if self.calibrators[i] is not None:
                calibrated[:, i] = self.calibrators[i].predict_proba(X)[:, 1]
            else:
                calibrated[:, i] = 1 / (1 + np.exp(-logits[:, i]))  # Fallback to sigmoid
        return calibrated


def create_calibration_plot(y_true: np.ndarray, y_probs: np.ndarray, output_path: str):
    """Create reliability diagram (calibration plot)."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Flatten for overall calibration
    y_true_flat = y_true.flatten()
    y_probs_flat = y_probs.flatten()

    # Compute calibration curve
    n_bins = 10
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_means = []
    bin_true = []

    for i in range(n_bins):
        mask = (y_probs_flat >= bin_edges[i]) & (y_probs_flat < bin_edges[i + 1])
        if np.sum(mask) > 0:
            bin_means.append(np.mean(y_probs_flat[mask]))
            bin_true.append(np.mean(y_true_flat[mask]))

    # Plot
    ax.plot([0, 1], [0, 1], 'k--', label='Perfectly calibrated')
    ax.plot(bin_means, bin_true, 'o-', label='Model calibration', markersize=8)
    ax.set_xlabel('Mean predicted probability', fontsize=12)
    ax.set_ylabel('Fraction of positives', fontsize=12)
    ax.set_title('Calibration Plot (Reliability Diagram)', fontsize=14)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved calibration plot: {output_path}")


def evaluate(config: Dict):
    """Main evaluation function."""
    print("=" * 60)
    print("Sprint 7: Model Evaluation & Error Analysis")
    print("=" * 60)

    # Create output directory
    os.makedirs(config['output_dir'], exist_ok=True)

    # Load model
    print(f"\nLoading model from {config['model_dir']}...")
    model, tokenizer, model_config = load_model(config['model_dir'], config['device'])
    print(f"Device: {config['device']}")

    # Load test data
    print(f"\nLoading test data from {config['test_file']}...")
    test_data = load_jsonl(config['test_file'])
    print(f"Test samples: {len(test_data)}")

    # Load validation data for calibration
    print(f"Loading validation data from {config['val_file']}...")
    val_data = load_jsonl(config['val_file'])
    print(f"Validation samples: {len(val_data)}")

    # Load aspects
    aspects_data = load_aspects(config['aspects_file'])
    aspects = aspects_data['aspects']

    # Create dataloaders
    test_dataset = EvalDataset(test_data, tokenizer, config['max_length'])
    val_dataset = EvalDataset(val_data, tokenizer, config['max_length'])

    test_loader = DataLoader(test_dataset, batch_size=config['batch_size'], shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'], shuffle=False)

    # Get predictions
    print("\n" + "=" * 40)
    print("Evaluating on test set...")
    y_true, y_logits, y_probs, post_ids, texts = get_predictions(model, test_loader, config['device'])
    y_pred = (y_probs >= 0.5).astype(int)

    # Get validation predictions for calibration
    print("\nEvaluating on validation set for calibration...")
    val_true, val_logits, val_probs, _, _ = get_predictions(model, val_loader, config['device'])

    # Compute metrics
    print("\n" + "=" * 40)
    print("Computing metrics...")

    # 7.1 & 7.2: Global metrics
    global_metrics = compute_global_metrics(y_true, y_pred)

    print(f"\nGlobal Metrics:")
    print(f"  Micro-F1:      {global_metrics['micro_f1']:.4f} (target: ≥0.75)")
    print(f"  Macro-F1:      {global_metrics['macro_f1']:.4f} (target: ≥0.70)")
    print(f"  Hamming Loss:  {global_metrics['hamming_loss']:.4f}")
    print(f"  Exact Match:   {global_metrics['exact_match']:.4f} (target: ≥0.50)")

    # 7.3 & 7.4: Per-aspect metrics
    per_aspect_metrics = compute_per_aspect_metrics(y_true, y_pred, aspects)

    print(f"\nPer-Aspect Metrics:")
    print(f"{'Aspect':<15} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Supp':>6} {'FNR':>6}")
    print("-" * 50)
    for m in per_aspect_metrics:
        is_high_risk = m['aspect_id'] in config['high_risk_aspects']
        marker = " *" if is_high_risk else ""
        print(f"{m['aspect_name']:<15} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} {m['support']:>6} {m['fnr']:>6.3f}{marker}")

    # Check high-risk FNR thresholds
    print("\nHigh-Risk Aspect FNR Check:")
    for aspect_id, threshold in config['high_risk_aspects'].items():
        fnr = per_aspect_metrics[aspect_id]['fnr']
        name = per_aspect_metrics[aspect_id]['aspect_name']
        status = "✓ PASS" if fnr <= threshold else "✗ FAIL"
        print(f"  {name}: FNR={fnr:.3f} (threshold: ≤{threshold}) {status}")

    # 7.5: Co-occurrence matrix
    print("\nComputing co-occurrence matrix...")
    cooccurrence = compute_cooccurrence_matrix(y_pred)

    # 7.6: Error examples
    print("\nExtracting error examples...")
    error_examples = extract_error_examples(
        y_true, y_pred, y_probs, post_ids, texts, aspects, n_examples=5
    )
    print(f"Total error examples: {len(error_examples)}")

    # 7.7: Platt scaling calibration
    print("\nApplying Platt scaling calibration...")
    calibrator = PlattScaler(n_aspects=10)
    calibrator.fit(val_logits, val_true)

    # Get calibrated probabilities
    calibrated_probs = calibrator.predict_proba(y_logits)

    # Save outputs
    print("\n" + "=" * 40)
    print("Saving outputs...")

    # Evaluation report
    evaluation_report = {
        'test_samples': len(test_data),
        'global_metrics': global_metrics,
        'per_aspect_metrics': per_aspect_metrics,
        'targets': {
            'micro_f1': 0.75,
            'macro_f1': 0.70,
            'exact_match': 0.50
        },
        'high_risk_fnr_thresholds': {
            aspects[k]['name_en']: v for k, v in config['high_risk_aspects'].items()
        }
    }

    eval_path = os.path.join(config['output_dir'], 'evaluation_v1.json')
    with open(eval_path, 'w', encoding='utf-8') as f:
        json.dump(evaluation_report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {eval_path}")

    # Error analysis
    error_path = os.path.join(config['output_dir'], 'error_analysis_v1.json')
    with open(error_path, 'w', encoding='utf-8') as f:
        json.dump(error_examples, f, indent=2, ensure_ascii=False)
    print(f"Saved: {error_path}")

    # Confusion patterns
    confusion_report = {
        'matrix': cooccurrence.tolist(),
        'aspect_names': [a['name_en'] for a in aspects],
        'description': 'Co-occurrence matrix showing how often aspects are predicted together'
    }
    confusion_path = os.path.join(config['output_dir'], 'confusion_patterns_v1.json')
    with open(confusion_path, 'w', encoding='utf-8') as f:
        json.dump(confusion_report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {confusion_path}")

    # Calibrator
    calibrator_path = os.path.join(config['model_dir'], 'calibrator.pkl')
    with open(calibrator_path, 'wb') as f:
        pickle.dump(calibrator, f)
    print(f"Saved: {calibrator_path}")

    # Calibration plot
    plot_path = os.path.join(config['output_dir'], 'calibration_plot.png')
    create_calibration_plot(y_true, calibrated_probs, plot_path)

    # Summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Test samples:   {len(test_data)}")
    print(f"Micro-F1:       {global_metrics['micro_f1']:.4f}")
    print(f"Macro-F1:       {global_metrics['macro_f1']:.4f}")
    print(f"Exact Match:    {global_metrics['exact_match']:.4f}")
    print(f"Hamming Loss:   {global_metrics['hamming_loss']:.4f}")

    # Check target metrics
    print("\nTarget Check:")
    targets_met = 0
    if global_metrics['micro_f1'] >= 0.75:
        print("  ✓ Micro-F1 ≥ 0.75")
        targets_met += 1
    else:
        print(f"  ✗ Micro-F1 < 0.75 ({global_metrics['micro_f1']:.4f})")

    if global_metrics['macro_f1'] >= 0.70:
        print("  ✓ Macro-F1 ≥ 0.70")
        targets_met += 1
    else:
        print(f"  ✗ Macro-F1 < 0.70 ({global_metrics['macro_f1']:.4f})")

    if global_metrics['exact_match'] >= 0.50:
        print("  ✓ Exact Match ≥ 0.50")
        targets_met += 1
    else:
        print(f"  ✗ Exact Match < 0.50 ({global_metrics['exact_match']:.4f})")

    print(f"\nTargets met: {targets_met}/3")

    print("\nDeliverables:")
    print(f"  - {eval_path}")
    print(f"  - {error_path}")
    print(f"  - {confusion_path}")
    print(f"  - {calibrator_path}")
    print(f"  - {plot_path}")

    return evaluation_report


if __name__ == '__main__':
    evaluate(CONFIG)
