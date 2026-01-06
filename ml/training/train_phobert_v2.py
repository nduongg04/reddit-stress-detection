#!/usr/bin/env python3
"""
Train PhoBERT Multi-Label Stress Detection Model v2

Uses stratified JSONL splits from dataset_splitting.py.
Implements class weighting with BCEWithLogitsLoss for imbalanced aspects.

Input: data/splits/{train,val}_v1.jsonl
Output: ml/models/phobert_stress_v2/
"""

import os
import json
import time
import hashlib
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModel,
    get_linear_schedule_with_warmup
)
from torch.optim import AdamW
from sklearn.metrics import f1_score, precision_score, recall_score
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configuration matching spec requirements
CONFIG = {
    'model_name': 'vinai/phobert-base-v2',
    'max_length': 256,
    'batch_size': 16,
    'learning_rate': 2e-5,
    'weight_decay': 0.01,
    'num_epochs': 15,  # Increased for better convergence
    'num_aspects': 10,
    'warmup_ratio': 0.1,
    'dropout': 0.3,
    'hidden_dim': 256,
    'early_stopping_patience': 5,  # More patience
    'early_stopping_min_delta': 0.001,
    'random_seed': 42,
    'class_weight_clamp': (1.0, 20.0),  # Higher weights for minority classes
    'output_dir': 'ml/models/phobert_stress_v2',
    'train_file': 'data/splits/train_v1.jsonl',
    'val_file': 'data/splits/val_v1.jsonl',
    'aspects_file': 'config/aspects_v1.json',
    # Data quality filters
    'max_aspects_per_post': 5,  # Filter out noisy labels with too many aspects
    'min_label_model': None,  # Set to 'llama3.1:8b' to only use better labels
    # Loss function
    'use_focal_loss': True,  # Use Focal Loss instead of BCE for imbalanced data
    'focal_alpha': 0.25,
    'focal_gamma': 2.0,
}


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class MultiLabelStressDataset(Dataset):
    """Dataset for multi-label stress aspect classification."""

    def __init__(self, posts: list[dict], tokenizer, max_length: int, num_aspects: int):
        self.posts = posts
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.num_aspects = num_aspects

    def __len__(self):
        return len(self.posts)

    def __getitem__(self, idx):
        post = self.posts[idx]
        text = str(post['text'])

        # Convert aspect list to binary vector
        labels = np.zeros(self.num_aspects, dtype=np.float32)
        for aspect_id in post.get('aspects', []):
            if 0 <= aspect_id < self.num_aspects:
                labels[aspect_id] = 1.0

        # Tokenize
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.FloatTensor(labels)
        }


class FocalLoss(nn.Module):
    """
    Focal Loss for multi-label classification.
    Focuses on hard examples by down-weighting easy ones.
    FL(p) = -alpha * (1-p)^gamma * log(p)
    """
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, pos_weight: torch.Tensor = None):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.pos_weight = pos_weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)

        # Focal weight: (1 - p_t)^gamma
        p_t = probs * targets + (1 - probs) * (1 - targets)
        focal_weight = (1 - p_t) ** self.gamma

        # BCE loss
        bce = nn.functional.binary_cross_entropy_with_logits(
            logits, targets, reduction='none', pos_weight=self.pos_weight
        )

        # Apply focal weight and alpha
        loss = self.alpha * focal_weight * bce

        return loss.mean()


class PhoBERTMultiLabelClassifier(nn.Module):
    """
    PhoBERT with multi-label classification head for stress aspects.
    Architecture: Linear(768→256) → ReLU → Dropout(0.3) → Linear(256→10) → Sigmoid
    """

    def __init__(self, model_name: str, num_aspects: int, hidden_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        self.hidden_size = self.phobert.config.hidden_size  # 768

        # Classification head per spec
        self.classifier = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_aspects)
        )
        # Note: Sigmoid is applied during inference; BCEWithLogitsLoss handles it during training

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        # Use [CLS] token representation
        pooled_output = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(pooled_output)

        return logits


def load_jsonl(filepath: str, max_aspects: int = None, min_model: str = None) -> list[dict]:
    """Load posts from JSONL file with optional quality filtering."""
    posts = []
    filtered_count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            post = json.loads(line.strip())
            
            # Filter by max aspects (remove noisy over-labeled posts)
            if max_aspects is not None and len(post.get('aspects', [])) > max_aspects:
                filtered_count += 1
                continue
            
            # Filter by labeling model quality
            if min_model is not None and post.get('model') != min_model:
                filtered_count += 1
                continue
            
            posts.append(post)
    
    if filtered_count > 0:
        print(f"  Filtered out {filtered_count} noisy samples")
    
    return posts


def compute_class_weights(train_posts: list[dict], num_aspects: int, clamp_range: tuple) -> torch.Tensor:
    """
    Compute per-aspect pos_weight for BCEWithLogitsLoss.
    Formula: weight_k = total_samples / (10 * positive_samples_k)
    Clamped to clamp_range to prevent extreme values.
    """
    total = len(train_posts)
    positive_counts = np.zeros(num_aspects)

    for post in train_posts:
        for aspect_id in post.get('aspects', []):
            if 0 <= aspect_id < num_aspects:
                positive_counts[aspect_id] += 1

    # Compute weights
    weights = np.zeros(num_aspects)
    for k in range(num_aspects):
        if positive_counts[k] > 0:
            weights[k] = total / (num_aspects * positive_counts[k])
        else:
            weights[k] = 1.0  # Default weight if no positive samples

    # Clamp weights
    weights = np.clip(weights, clamp_range[0], clamp_range[1])

    print("\nClass weights (pos_weight for BCEWithLogitsLoss):")
    for k in range(num_aspects):
        print(f"  Aspect {k}: {weights[k]:.3f} (positive samples: {int(positive_counts[k])})")

    return torch.FloatTensor(weights)


def create_data_loaders(train_posts: list[dict], val_posts: list[dict],
                        tokenizer, config: dict) -> tuple:
    """Create train and validation data loaders."""
    train_dataset = MultiLabelStressDataset(
        train_posts, tokenizer, config['max_length'], config['num_aspects']
    )
    val_dataset = MultiLabelStressDataset(
        val_posts, tokenizer, config['max_length'], config['num_aspects']
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config['batch_size'],
        shuffle=True,
        num_workers=0
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config['batch_size'],
        shuffle=False,
        num_workers=0
    )

    return train_loader, val_loader


def train_epoch(model, data_loader, optimizer, scheduler, loss_fn, device) -> float:
    """Train for one epoch."""
    model.train()
    total_loss = 0

    for batch in tqdm(data_loader, desc="Training"):
        optimizer.zero_grad()

        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        logits = model(input_ids, attention_mask)
        loss = loss_fn(logits, labels)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(data_loader)


def evaluate(model, data_loader, loss_fn, device, threshold: float = 0.5) -> dict:
    """Evaluate model and return metrics."""
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in tqdm(data_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            logits = model(input_ids, attention_mask)
            loss = loss_fn(logits, labels)
            total_loss += loss.item()

            # Apply sigmoid and threshold
            probs = torch.sigmoid(logits)
            preds = (probs > threshold).float()

            all_preds.append(preds.cpu().numpy())
            all_labels.append(labels.cpu().numpy())

    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)

    # Calculate metrics
    avg_loss = total_loss / len(data_loader)

    # Per-aspect metrics
    aspect_f1s = []
    for k in range(all_labels.shape[1]):
        f1 = f1_score(all_labels[:, k], all_preds[:, k], zero_division=0)
        aspect_f1s.append(f1)

    # Micro and macro F1
    f1_micro = f1_score(all_labels.flatten(), all_preds.flatten(), average='micro', zero_division=0)
    f1_macro = f1_score(all_labels.flatten(), all_preds.flatten(), average='macro', zero_division=0)

    # Exact match (all aspects correct)
    exact_match = np.mean(np.all(all_preds == all_labels, axis=1))

    return {
        'loss': avg_loss,
        'f1_micro': f1_micro,
        'f1_macro': f1_macro,
        'exact_match': exact_match,
        'aspect_f1s': aspect_f1s
    }


def save_checkpoint(model, optimizer, epoch, val_loss, output_dir: str, filename: str):
    """Save training checkpoint."""
    checkpoint_dir = os.path.join(output_dir, 'checkpoints')
    os.makedirs(checkpoint_dir, exist_ok=True)

    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'val_loss': val_loss
    }, os.path.join(checkpoint_dir, filename))


def compute_file_hash(filepath: str) -> str:
    """Compute MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()[:8]


def train(config: dict):
    """Main training function."""
    print("=" * 70)
    print("PHOBERT MULTI-LABEL STRESS DETECTION TRAINING v2")
    print("=" * 70)

    # Set seed
    set_seed(config['random_seed'])

    # Device
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"\nDevice: CUDA GPU ({torch.cuda.get_device_name(0)})")
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
        print(f"\nDevice: Apple MPS (Metal Performance Shaders)")
    else:
        device = torch.device('cpu')
        print(f"\nDevice: CPU (Warning: Training will be slow)")

    # Load data with quality filtering
    print(f"\nLoading training data from {config['train_file']}...")
    train_posts = load_jsonl(
        config['train_file'],
        max_aspects=config.get('max_aspects_per_post'),
        min_model=config.get('min_label_model')
    )
    print(f"✓ Loaded {len(train_posts)} training posts")

    print(f"\nLoading validation data from {config['val_file']}...")
    val_posts = load_jsonl(
        config['val_file'],
        max_aspects=config.get('max_aspects_per_post'),
        min_model=config.get('min_label_model')
    )
    print(f"✓ Loaded {len(val_posts)} validation posts")

    # Compute class weights
    class_weights = compute_class_weights(
        train_posts, config['num_aspects'], config['class_weight_clamp']
    ).to(device)

    # Load tokenizer
    print(f"\nLoading tokenizer: {config['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config['model_name'])

    # Create data loaders
    train_loader, val_loader = create_data_loaders(
        train_posts, val_posts, tokenizer, config
    )

    # Create model
    print(f"\nInitializing model: {config['model_name']}")
    model = PhoBERTMultiLabelClassifier(
        config['model_name'],
        config['num_aspects'],
        config['hidden_dim'],
        config['dropout']
    )
    model.to(device)

    num_params = sum(p.numel() for p in model.parameters())
    print(f"✓ Model has {num_params:,} parameters")

    # Loss function with class weights
    if config.get('use_focal_loss', False):
        loss_fn = FocalLoss(
            alpha=config.get('focal_alpha', 0.25),
            gamma=config.get('focal_gamma', 2.0),
            pos_weight=class_weights
        )
        print(f"✓ Using FocalLoss (alpha={config['focal_alpha']}, gamma={config['focal_gamma']}) with pos_weight")
    else:
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=class_weights)
        print(f"✓ Using BCEWithLogitsLoss with pos_weight")

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config['learning_rate'],
        weight_decay=config['weight_decay']
    )

    # Scheduler
    total_steps = len(train_loader) * config['num_epochs']
    warmup_steps = int(total_steps * config['warmup_ratio'])
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )

    print(f"✓ Optimizer: AdamW (lr={config['learning_rate']}, weight_decay={config['weight_decay']})")
    print(f"✓ Scheduler: Linear warmup ({warmup_steps} steps)")

    # Training loop with early stopping
    print(f"\n" + "=" * 70)
    print("TRAINING")
    print("=" * 70)

    best_val_loss = float('inf')
    best_epoch = 0
    patience_counter = 0
    training_start = time.time()

    os.makedirs(config['output_dir'], exist_ok=True)

    for epoch in range(config['num_epochs']):
        print(f"\nEpoch {epoch + 1}/{config['num_epochs']}")
        print("-" * 70)

        # Train
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, loss_fn, device)
        print(f"Train Loss: {train_loss:.4f}")

        # Validate
        val_metrics = evaluate(model, val_loader, loss_fn, device)
        print(f"Val Loss:       {val_metrics['loss']:.4f}")
        print(f"Val F1 (micro): {val_metrics['f1_micro']:.4f}")
        print(f"Val F1 (macro): {val_metrics['f1_macro']:.4f}")
        print(f"Val Exact Match: {val_metrics['exact_match']:.4f}")

        # Save checkpoint
        save_checkpoint(
            model, optimizer, epoch, val_metrics['loss'],
            config['output_dir'], f"checkpoint_epoch_{epoch+1}.pt"
        )

        # Early stopping check
        if val_metrics['loss'] < best_val_loss - config['early_stopping_min_delta']:
            best_val_loss = val_metrics['loss']
            best_epoch = epoch + 1
            patience_counter = 0

            # Save best model
            torch.save(model.state_dict(), os.path.join(config['output_dir'], 'model.pt'))
            tokenizer.save_pretrained(config['output_dir'])
            print(f"✓ Saved best model (val_loss: {best_val_loss:.4f})")
        else:
            patience_counter += 1
            print(f"⚠ No improvement ({patience_counter}/{config['early_stopping_patience']})")

            if patience_counter >= config['early_stopping_patience']:
                print(f"\n✗ Early stopping triggered at epoch {epoch + 1}")
                break

    training_time = time.time() - training_start

    # Save config
    with open(os.path.join(config['output_dir'], 'config.json'), 'w') as f:
        json.dump(config, f, indent=2)

    # Save metadata
    metadata = {
        'dataset_version': 'v1',
        'aspects_version': 'v1',
        'train_samples': len(train_posts),
        'val_samples': len(val_posts),
        'train_file_hash': compute_file_hash(config['train_file']),
        'val_file_hash': compute_file_hash(config['val_file']),
        'hyperparams': {
            'lr': config['learning_rate'],
            'batch_size': config['batch_size'],
            'max_len': config['max_length'],
            'epochs': config['num_epochs'],
            'patience': config['early_stopping_patience'],
            'dropout': config['dropout'],
            'hidden_dim': config['hidden_dim']
        },
        'seed': config['random_seed'],
        'best_epoch': best_epoch,
        'best_val_loss': best_val_loss,
        'training_time_seconds': training_time,
        'class_weights': class_weights.cpu().tolist(),
        'model_params': num_params
    }

    with open(os.path.join(config['output_dir'], 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n" + "=" * 70)
    print("✓ TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nModel saved to: {config['output_dir']}")
    print(f"Best epoch: {best_epoch}")
    print(f"Best val loss: {best_val_loss:.4f}")
    print(f"Training time: {training_time:.1f}s ({training_time/60:.1f}min)")


if __name__ == "__main__":
    train(CONFIG)
