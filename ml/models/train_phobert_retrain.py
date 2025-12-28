"""
PhoBERT Fine-tuning Script for ABSA Retrain
Optimized for dedicated training service (not Airflow scheduler)

Supports:
- Fine-tuning from existing PhoBERT checkpoint
- Gradient accumulation for large batch size with limited RAM
- Mixed precision (FP16) to reduce memory
- Checkpoint saving during training
- Incremental learning from validated data

Model: vinai/phobert-base-v2 (135M parameters)
Task: Multi-label ABSA (10 aspects × 3 sentiments)
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup
)
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, hamming_loss, classification_report
import json
import os
from datetime import datetime
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configuration
DEFAULT_CONFIG = {
    'model_name': 'vinai/phobert-base-v2',
    'checkpoint_dir': None,  # If provided, load from checkpoint
    'max_length': 256,
    'batch_size': 8,  # Small batch for memory efficiency
    'gradient_accumulation_steps': 4,  # Effective batch = 8 × 4 = 32
    'learning_rate': 2e-5,
    'weight_decay': 0.01,
    'num_epochs': 5,
    'warmup_ratio': 0.1,
    'num_aspects': 10,
    'num_classes': 3,
    'dropout': 0.1,
    'mixed_precision': True,  # FP16 training
    'save_steps': 500,
    'eval_steps': 100,
    'output_dir': '/workspace/ml/models/vietnamese_absa_phobert_retrained',
    'data_file': None,  # Will be provided by API
}


class PhoBERTForABSA(nn.Module):
    """
    PhoBERT wrapper for multi-label ABSA
    
    Architecture:
    PhoBERT encoder → [CLS] token → Classifier → [10 aspects × 3 classes]
    """
    def __init__(self, model_name, num_aspects=10, num_classes=3, dropout=0.1):
        super().__init__()
        
        # Load base PhoBERT (or from checkpoint)
        self.encoder = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=num_aspects * num_classes,
            problem_type="multi_label_classification"
        )
        
        self.num_aspects = num_aspects
        self.num_classes = num_classes
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, input_ids, attention_mask, labels=None):
        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=None  # We'll compute loss manually
        )
        
        logits = outputs.logits  # [batch, num_aspects * num_classes]
        
        # Reshape to [batch, num_aspects, num_classes]
        batch_size = logits.size(0)
        logits = logits.view(batch_size, self.num_aspects, self.num_classes)
        
        loss = None
        if labels is not None:
            # Compute cross-entropy loss for each aspect
            criterion = nn.CrossEntropyLoss()
            loss = 0
            for aspect_idx in range(self.num_aspects):
                aspect_logits = logits[:, aspect_idx, :]  # [batch, 3]
                aspect_labels = labels[:, aspect_idx]      # [batch]
                loss += criterion(aspect_logits, aspect_labels)
            loss = loss / self.num_aspects
        
        return {'loss': loss, 'logits': logits}


class ABSADataset(Dataset):
    """Dataset for ABSA labeled data"""
    def __init__(self, texts, labels, tokenizer, max_length=256):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        item = {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': torch.tensor(self.labels[idx], dtype=torch.long)
        }
        return item


def load_data(data_file):
    """Load ABSA labeled data"""
    logger.info(f"Loading data from {data_file}...")
    df = pd.read_csv(data_file)
    logger.info(f"✓ Loaded {len(df)} labeled posts")
    
    # Extract texts
    texts = df['text'].tolist()
    
    # Extract multi-label sentiments
    aspect_cols = [col for col in df.columns if col.startswith('sentiment_')]
    logger.info(f"✓ Found {len(aspect_cols)} sentiment columns")
    
    labels = []
    for _, row in df.iterrows():
        label_vector = []
        for col in aspect_cols:
            sentiment = row[col]
            # Map: -1 (negative) -> 0, 0 (neutral) -> 1, 1 (positive) -> 2
            class_idx = int(sentiment) + 1
            label_vector.append(class_idx)
        labels.append(label_vector)
    
    labels = np.array(labels)
    logger.info(f"✓ Label shape: {labels.shape}")
    
    return texts, labels


def train_epoch(model, dataloader, optimizer, scheduler, device, config, scaler=None):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    accumulation_steps = config['gradient_accumulation_steps']
    
    optimizer.zero_grad()
    
    progress_bar = tqdm(dataloader, desc="Training")
    for i, batch in enumerate(progress_bar):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)
        
        # Mixed precision training
        if config['mixed_precision'] and scaler:
            with torch.cuda.amp.autocast():
                outputs = model(input_ids, attention_mask, labels)
                loss = outputs['loss'] / accumulation_steps
            
            scaler.scale(loss).backward()
            
            if (i + 1) % accumulation_steps == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                scheduler.step()
        else:
            outputs = model(input_ids, attention_mask, labels)
            loss = outputs['loss'] / accumulation_steps
            loss.backward()
            
            if (i + 1) % accumulation_steps == 0:
                optimizer.step()
                optimizer.zero_grad()
                scheduler.step()
        
        total_loss += loss.item() * accumulation_steps
        progress_bar.set_postfix({'loss': f'{loss.item() * accumulation_steps:.4f}'})
    
    return total_loss / len(dataloader)


def evaluate(model, dataloader, device):
    """Evaluate model"""
    model.eval()
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].cpu().numpy()
            
            outputs = model(input_ids, attention_mask)
            logits = outputs['logits']
            preds = torch.argmax(logits, dim=2).cpu().numpy()  # [batch, 10]
            
            all_preds.append(preds)
            all_labels.append(labels)
    
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)
    
    # Calculate metrics
    f1_micro = f1_score(all_labels, all_preds, average='micro')
    f1_macro = f1_score(all_labels, all_preds, average='macro')
    h_loss = hamming_loss(all_labels, all_preds)
    
    return {
        'f1_micro': f1_micro,
        'f1_macro': f1_macro,
        'hamming_loss': h_loss,
        'predictions': all_preds,
        'labels': all_labels
    }


def train_phobert(config, job_id=None, data_file=None):
    """
    Main training function
    
    Args:
        config: Training configuration dict
        job_id: Job ID for logging (optional)
        data_file: Path to training data CSV
    """
    # Merge with default config
    cfg = {**DEFAULT_CONFIG, **config}
    if data_file:
        cfg['data_file'] = data_file
    
    logger.info("=" * 80)
    logger.info(f"PHOBERT ABSA RETRAINING - Job {job_id}")
    logger.info("=" * 80)
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Device: {device}")
    
    if device.type == 'cuda':
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    # Load data
    if not cfg['data_file']:
        raise ValueError("data_file is required")
    
    texts, labels = load_data(cfg['data_file'])
    
    # Split data
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        texts, labels, test_size=0.3, random_state=42
    )
    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts, temp_labels, test_size=0.5, random_state=42
    )
    
    logger.info(f"\nData split:")
    logger.info(f"  Train: {len(train_texts)} posts")
    logger.info(f"  Val:   {len(val_texts)} posts")
    logger.info(f"  Test:  {len(test_texts)} posts")
    
    # Load tokenizer and model
    logger.info(f"\nLoading PhoBERT: {cfg['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(cfg['model_name'])
    
    # Load from checkpoint or pretrained
    if cfg.get('checkpoint_dir') and os.path.exists(cfg['checkpoint_dir']):
        logger.info(f"Loading from checkpoint: {cfg['checkpoint_dir']}")
        model = PhoBERTForABSA(cfg['checkpoint_dir'], cfg['num_aspects'], cfg['num_classes'], cfg['dropout'])
    else:
        logger.info("Loading pretrained PhoBERT")
        model = PhoBERTForABSA(cfg['model_name'], cfg['num_aspects'], cfg['num_classes'], cfg['dropout'])
    
    model = model.to(device)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"✓ Model has {total_params:,} parameters ({total_params/1e6:.1f}M)")
    logger.info(f"  Trainable: {trainable_params:,} ({trainable_params/1e6:.1f}M)")
    
    # Create datasets
    train_dataset = ABSADataset(train_texts, train_labels, tokenizer, cfg['max_length'])
    val_dataset = ABSADataset(val_texts, val_labels, tokenizer, cfg['max_length'])
    test_dataset = ABSADataset(test_texts, test_labels, tokenizer, cfg['max_length'])
    
    # Create dataloaders
    train_loader = DataLoader(train_dataset, batch_size=cfg['batch_size'], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=cfg['batch_size'])
    test_loader = DataLoader(test_dataset, batch_size=cfg['batch_size'])
    
    # Optimizer and scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg['learning_rate'],
        weight_decay=cfg['weight_decay']
    )
    
    total_steps = len(train_loader) * cfg['num_epochs'] // cfg['gradient_accumulation_steps']
    warmup_steps = int(total_steps * cfg['warmup_ratio'])
    
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )
    
    # Mixed precision scaler
    scaler = torch.cuda.amp.GradScaler() if cfg['mixed_precision'] and device.type == 'cuda' else None
    
    # Training loop
    logger.info(f"\n{'='*80}")
    logger.info("TRAINING")
    logger.info(f"{'='*80}")
    logger.info(f"Epochs: {cfg['num_epochs']}")
    logger.info(f"Batch size: {cfg['batch_size']}")
    logger.info(f"Gradient accumulation: {cfg['gradient_accumulation_steps']}")
    logger.info(f"Effective batch size: {cfg['batch_size'] * cfg['gradient_accumulation_steps']}")
    logger.info(f"Total steps: {total_steps}")
    logger.info(f"Warmup steps: {warmup_steps}")
    
    best_val_f1 = 0
    for epoch in range(cfg['num_epochs']):
        logger.info(f"\nEpoch {epoch+1}/{cfg['num_epochs']}")
        logger.info("-" * 80)
        
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device, cfg, scaler)
        val_metrics = evaluate(model, val_loader, device)
        
        logger.info(f"Train Loss: {train_loss:.4f}")
        logger.info(f"Val F1 (micro): {val_metrics['f1_micro']:.4f}")
        logger.info(f"Val F1 (macro): {val_metrics['f1_macro']:.4f}")
        logger.info(f"Val Hamming Loss: {val_metrics['hamming_loss']:.4f}")
        
        # Save best model
        if val_metrics['f1_micro'] > best_val_f1:
            best_val_f1 = val_metrics['f1_micro']
            logger.info(f"✓ New best F1: {best_val_f1:.4f} - Saving checkpoint")
            
            checkpoint_dir = f"{cfg['output_dir']}_checkpoint"
            os.makedirs(checkpoint_dir, exist_ok=True)
            model.encoder.save_pretrained(checkpoint_dir)
            tokenizer.save_pretrained(checkpoint_dir)
    
    # Test evaluation
    logger.info(f"\n{'='*80}")
    logger.info("TEST EVALUATION")
    logger.info(f"{'='*80}")
    test_metrics = evaluate(model, test_loader, device)
    logger.info(f"Test F1 (micro): {test_metrics['f1_micro']:.4f}")
    logger.info(f"Test F1 (macro): {test_metrics['f1_macro']:.4f}")
    logger.info(f"Test Hamming Loss: {test_metrics['hamming_loss']:.4f}")
    
    # Save final model
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f"{cfg['output_dir']}_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"\nSaving model to {output_dir}...")
    
    # Save model and tokenizer
    model.encoder.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    logger.info(f"✓ Saved model and tokenizer")
    
    # Save config
    with open(f'{output_dir}/config.json', 'w') as f:
        json.dump(cfg, f, indent=2)
    logger.info(f"✓ Saved config")
    
    # Save test metrics
    test_metrics_clean = {
        'f1_micro': float(test_metrics['f1_micro']),
        'f1_macro': float(test_metrics['f1_macro']),
        'hamming_loss': float(test_metrics['hamming_loss'])
    }
    with open(f'{output_dir}/test_metrics.json', 'w') as f:
        json.dump(test_metrics_clean, f, indent=2)
    logger.info(f"✓ Saved test metrics")
    
    # Save metadata
    metadata = {
        'version': timestamp,
        'trained_at': datetime.now().isoformat(),
        'job_id': job_id,
        'model_name': cfg['model_name'],
        'total_samples': len(texts),
        'train_samples': len(train_texts),
        'val_samples': len(val_texts),
        'test_samples': len(test_texts),
        'best_val_f1': float(best_val_f1),
        'test_f1_micro': float(test_metrics['f1_micro']),
        'test_f1_macro': float(test_metrics['f1_macro']),
        'parameters': total_params,
        'device': str(device)
    }
    with open(f'{output_dir}/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"✓ Saved metadata")
    
    logger.info(f"\n{'='*80}")
    logger.info("TRAINING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Model saved to: {output_dir}")
    logger.info(f"Best Val F1: {best_val_f1:.4f}")
    logger.info(f"Test F1 (micro): {test_metrics['f1_micro']:.4f}")
    logger.info(f"Test F1 (macro): {test_metrics['f1_macro']:.4f}")
    
    return output_dir


if __name__ == '__main__':
    # Test training
    test_config = {
        'data_file': '/workspace/ml/dataset/labeled/vozforums_absa_labeled.csv',
        'num_epochs': 3,
        'batch_size': 4,
        'output_dir': '/workspace/ml/models/test_phobert_retrain'
    }
    
    train_phobert(test_config)
