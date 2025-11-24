#!/usr/bin/env python3
"""
Train PhoBERT Multi-Label ABSA Model for Vietnamese Mental Health
Trains on 10 Vietnamese aspects from labeled vozforums data
"""

import os
import json
import pandas as pd
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
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, hamming_loss, accuracy_score
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configuration
CONFIG = {
    'model_name': 'vinai/phobert-base-v2',
    'max_length': 256,
    'batch_size': 32,  # Increased batch size
    'learning_rate': 3e-5,  # Higher learning rate
    'weight_decay': 0.01,  # Add weight decay for regularization
    'num_epochs': 15,  # More epochs
    'num_aspects': 10,
    'num_classes': 3,  # -1 (negative), 0 (neutral), 1 (positive)
    'warmup_steps': 200,  # More warmup
    'dropout': 0.5,  # Higher dropout to prevent overfitting to majority class
    'use_class_weights': True,  # Use weighted loss for imbalanced classes
    'focal_loss_gamma': 2.0,  # Focal loss to focus on hard examples
    'output_dir': 'ml/models/vietnamese_absa_sentiment_phobert_v1',
    'data_file': 'ml/dataset/labeled/vozforums_absa_sentiment.csv'
}

class MultiLabelABSADataset(Dataset):
    """Dataset for multi-label ABSA classification"""

    def __init__(self, texts, labels, tokenizer, max_length=256):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        labels = self.labels[idx]

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
            'labels': torch.LongTensor(labels)  # Long for CrossEntropyLoss
        }

class PhoBERTMultiLabelClassifier(nn.Module):
    """PhoBERT with multi-aspect sentiment classification (10 aspects × 3 classes)"""

    def __init__(self, model_name, num_aspects, num_classes, dropout=0.3):
        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.num_aspects = num_aspects
        self.num_classes = num_classes
        # Output: 10 aspects × 3 classes = 30 logits
        self.classifier = nn.Linear(self.phobert.config.hidden_size, num_aspects * num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        # Use [CLS] token representation
        pooled_output = outputs.last_hidden_state[:, 0, :]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)

        # Reshape to (batch_size, num_aspects, num_classes)
        batch_size = logits.size(0)
        logits = logits.view(batch_size, self.num_aspects, self.num_classes)

        return logits

def load_data(data_file):
    """Load labeled data from CSV"""
    print(f"\nLoading data from {data_file}...")
    df = pd.read_csv(data_file)

    print(f"✓ Loaded {len(df)} labeled posts")

    # Extract texts
    texts = df['text'].tolist()

    # Extract sentiment vectors (columns sentiment_0 to sentiment_9)
    # Sentiment values: -1 (negative), 0 (neutral/not-present), 1 (positive)
    sentiment_columns = [f'sentiment_{i}_' + col for i, col in enumerate([
        'công_việc', 'giấc_ngủ_thuốc', 'giao_tiếp', 'thiếu_năng_lượng',
        'căng_thẳng_tài_chính', 'tình_yêu', 'tự_suy_ngẫm', 'trầm_cảm',
        'gia_đình', 'tìm_kiếm_giúp_đỡ'
    ])]

    # Check if sentiment columns exist
    if not all(col in df.columns for col in sentiment_columns):
        raise ValueError(f"Missing sentiment columns in {data_file}. Expected columns like 'sentiment_0_công_việc'")

    # Get sentiment labels (-1, 0, 1)
    sentiments = df[sentiment_columns].values.astype(np.int32)

    # Convert to class indices: -1 -> 0, 0 -> 1, 1 -> 2
    labels = sentiments + 1

    print(f"✓ Extracted {len(sentiment_columns)} sentiment dimensions")
    print(f"✓ Sentiment mapping: -1->class_0 (negative), 0->class_1 (neutral), 1->class_2 (positive)")
    print(f"✓ Label shape: {labels.shape}")

    # Calculate class weights for imbalanced dataset
    from sklearn.utils.class_weight import compute_class_weight
    all_labels_flat = labels.flatten()
    class_weights = compute_class_weight('balanced', classes=np.array([0, 1, 2]), y=all_labels_flat)
    print(f"\n✓ Class weights (to handle imbalance):")
    print(f"  Class 0 (negative): {class_weights[0]:.3f}")
    print(f"  Class 1 (neutral):  {class_weights[1]:.3f}")
    print(f"  Class 2 (positive): {class_weights[2]:.3f}")

    return texts, labels, class_weights

def create_data_loaders(texts, labels, tokenizer, config):
    """Create train/val/test data loaders"""

    # Split: 80% train, 10% val, 10% test
    X_train, X_temp, y_train, y_temp = train_test_split(
        texts, labels, test_size=0.2, random_state=42
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42
    )

    print(f"\nData split:")
    print(f"  Train: {len(X_train)} posts")
    print(f"  Val:   {len(X_val)} posts")
    print(f"  Test:  {len(X_test)} posts")

    # Create datasets
    train_dataset = MultiLabelABSADataset(X_train, y_train, tokenizer, config['max_length'])
    val_dataset = MultiLabelABSADataset(X_val, y_val, tokenizer, config['max_length'])
    test_dataset = MultiLabelABSADataset(X_test, y_test, tokenizer, config['max_length'])

    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'])
    test_loader = DataLoader(test_dataset, batch_size=config['batch_size'])

    return train_loader, val_loader, test_loader, (X_test, y_test)

def train_epoch(model, data_loader, optimizer, scheduler, device, class_weights=None):
    """Train for one epoch"""
    model.train()
    total_loss = 0

    for batch in tqdm(data_loader, desc="Training"):
        optimizer.zero_grad()

        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        # Forward pass
        logits = model(input_ids, attention_mask)  # (batch_size, num_aspects, num_classes)

        # Weighted cross-entropy loss for each aspect (handles class imbalance)
        if class_weights is not None:
            loss_fn = nn.CrossEntropyLoss(weight=class_weights)
        else:
            loss_fn = nn.CrossEntropyLoss()

        loss = 0
        for i in range(logits.size(1)):  # For each aspect
            loss += loss_fn(logits[:, i, :], labels[:, i])

        # Backward pass
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(data_loader)

def evaluate(model, data_loader, device):
    """Evaluate model"""
    model.eval()
    all_preds = []
    all_labels = []
    total_loss = 0

    with torch.no_grad():
        for batch in tqdm(data_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            logits = model(input_ids, attention_mask)  # (batch_size, num_aspects, num_classes)

            # Calculate loss
            loss_fn = nn.CrossEntropyLoss()
            loss = 0
            for i in range(logits.size(1)):
                loss += loss_fn(logits[:, i, :], labels[:, i])
            total_loss += loss.item()

            # Get predictions (argmax for each aspect)
            preds = torch.argmax(logits, dim=2)  # (batch_size, num_aspects)

            all_preds.append(preds.cpu().numpy())
            all_labels.append(labels.cpu().numpy())

    # Concatenate all batches
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)

    # Calculate metrics
    # Flatten for overall metrics
    all_preds_flat = all_preds.flatten()
    all_labels_flat = all_labels.flatten()

    # Overall accuracy
    accuracy = accuracy_score(all_labels_flat, all_preds_flat)

    # F1 scores (weighted average across all aspect-sentiment pairs)
    f1_macro = f1_score(all_labels_flat, all_preds_flat, average='macro', zero_division=0)
    f1_weighted = f1_score(all_labels_flat, all_preds_flat, average='weighted', zero_division=0)

    # Per-aspect accuracy
    aspect_accuracies = []
    for i in range(all_labels.shape[1]):
        aspect_acc = accuracy_score(all_labels[:, i], all_preds[:, i])
        aspect_accuracies.append(aspect_acc)

    avg_loss = total_loss / len(data_loader)

    return {
        'loss': avg_loss,
        'accuracy': accuracy,
        'f1_macro': f1_macro,
        'f1_weighted': f1_weighted,
        'aspect_accuracies': aspect_accuracies
    }

def train(config):
    """Main training function"""

    print("="*70)
    print("PHOBERT MULTI-LABEL ABSA TRAINING")
    print("="*70)

    # Device (support CUDA, MPS (Mac), or CPU)
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"\nDevice: CUDA GPU ({torch.cuda.get_device_name(0)})")
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
        print(f"\nDevice: Apple MPS (Metal Performance Shaders)")
    else:
        device = torch.device('cpu')
        print(f"\nDevice: CPU (Warning: Training will be slow)")

    # Load data
    texts, labels, class_weights = load_data(config['data_file'])

    # Convert class weights to tensor
    class_weights_tensor = torch.FloatTensor(class_weights).to(device) if config.get('use_class_weights', False) else None

    # Load tokenizer
    print(f"\nLoading tokenizer: {config['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config['model_name'])

    # Create data loaders
    train_loader, val_loader, test_loader, test_data = create_data_loaders(
        texts, labels, tokenizer, config
    )

    # Create model with configurable dropout
    print(f"\nInitializing model: {config['model_name']}")
    dropout = config.get('dropout', 0.3)
    model = PhoBERTMultiLabelClassifier(config['model_name'], config['num_aspects'], config['num_classes'], dropout=dropout)
    model.to(device)

    print(f"✓ Model has {sum(p.numel() for p in model.parameters()):,} parameters")
    print(f"✓ Dropout: {dropout}")

    # Optimizer with weight decay
    weight_decay = config.get('weight_decay', 0.0)
    optimizer = AdamW(model.parameters(), lr=config['learning_rate'], weight_decay=weight_decay)
    print(f"✓ Learning rate: {config['learning_rate']}, Weight decay: {weight_decay}")
    total_steps = len(train_loader) * config['num_epochs']
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=config['warmup_steps'],
        num_training_steps=total_steps
    )

    # Training loop
    print(f"\n" + "="*70)
    print("TRAINING")
    print("="*70)

    best_f1 = 0

    for epoch in range(config['num_epochs']):
        print(f"\nEpoch {epoch + 1}/{config['num_epochs']}")
        print("-" * 70)

        # Train
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device)
        print(f"Train Loss: {train_loss:.4f}")

        # Validate
        val_metrics = evaluate(model, val_loader, device)
        print(f"Val Loss:     {val_metrics['loss']:.4f}")
        print(f"Val Accuracy: {val_metrics['accuracy']:.4f}")
        print(f"Val F1 (macro): {val_metrics['f1_macro']:.4f}")
        print(f"Val F1 (weighted): {val_metrics['f1_weighted']:.4f}")

        # Save best model (based on accuracy)
        if val_metrics['accuracy'] > best_f1:
            best_f1 = val_metrics['accuracy']
            os.makedirs(config['output_dir'], exist_ok=True)

            # Save model
            torch.save(model.state_dict(), f"{config['output_dir']}/model.pt")
            tokenizer.save_pretrained(config['output_dir'])

            # Save config
            with open(f"{config['output_dir']}/config.json", 'w') as f:
                json.dump(config, f, indent=2)

            print(f"✓ Saved best model (Accuracy: {best_f1:.4f})")

    # Test on best model
    print(f"\n" + "="*70)
    print("TESTING ON BEST MODEL")
    print("="*70)

    model.load_state_dict(torch.load(f"{config['output_dir']}/model.pt"))
    test_metrics = evaluate(model, test_loader, device)

    print(f"\nTest Results:")
    print(f"  Loss:         {test_metrics['loss']:.4f}")
    print(f"  Accuracy:     {test_metrics['accuracy']:.4f}")
    print(f"  F1 (macro):   {test_metrics['f1_macro']:.4f}")
    print(f"  F1 (weighted): {test_metrics['f1_weighted']:.4f}")

    # Save test metrics
    with open(f"{config['output_dir']}/test_metrics.json", 'w') as f:
        json.dump(test_metrics, f, indent=2)

    print(f"\n" + "="*70)
    print("✓ TRAINING COMPLETE")
    print("="*70)
    print(f"\nModel saved to: {config['output_dir']}")
    print(f"Best validation accuracy: {best_f1:.4f}")
    print(f"Test accuracy: {test_metrics['accuracy']:.4f}")

if __name__ == "__main__":
    train(CONFIG)
