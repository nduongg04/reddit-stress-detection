"""
Lightweight ABSA Model Training Script
Uses BiLSTM instead of PhoBERT to avoid OOM issues during retraining
~2-5M parameters vs PhoBERT's 135M parameters

NOTE: This is for DEMO/WORKFLOW purposes only
Production model remains: vietnamese_absa_sentiment_phobert_v1
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, hamming_loss
import json
import os
from datetime import datetime
from tqdm import tqdm

# Lightweight Configuration
CONFIG = {
    'tokenizer_name': 'vinai/phobert-base-v2',  # Use tokenizer only, not model
    'vocab_size': 64000,
    'embedding_dim': 128,  # Reduced from 768 (PhoBERT hidden size)
    'hidden_dim': 128,     # LSTM hidden size
    'num_layers': 2,       # LSTM layers
    'max_length': 128,     # Reduced from 256
    'batch_size': 8,       # Small batch
    'learning_rate': 1e-3,
    'weight_decay': 0.01,
    'num_epochs': 3,       # Quick training
    'num_aspects': 10,
    'num_classes': 3,
    'dropout': 0.3,
    'output_dir': 'ml/models/vietnamese_absa_simple_v1',
    'data_file': 'ml/dataset/labeled/vozforums_absa_sentiment.csv',
}


class SimpleBiLSTMABSA(nn.Module):
    """
    Lightweight BiLSTM model for ABSA
    ~2-5M parameters (vs PhoBERT 135M)
    """
    def __init__(self, vocab_size, embedding_dim, hidden_dim, num_layers, 
                 num_aspects, num_classes, dropout=0.3):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=1)
        self.lstm = nn.LSTM(
            embedding_dim, 
            hidden_dim, 
            num_layers=num_layers,
            bidirectional=True,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        self.dropout = nn.Dropout(dropout)
        # BiLSTM outputs hidden_dim * 2
        self.classifier = nn.Linear(hidden_dim * 2, num_aspects * num_classes)
        self.num_aspects = num_aspects
        self.num_classes = num_classes
        
    def forward(self, input_ids, attention_mask):
        # Embedding
        embedded = self.embedding(input_ids)  # [batch, seq_len, emb_dim]
        
        # Pack padded sequence for efficiency
        lengths = attention_mask.sum(dim=1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded, lengths, batch_first=True, enforce_sorted=False
        )
        
        # BiLSTM
        lstm_out, (hidden, cell) = self.lstm(packed)
        
        # Use last hidden state from both directions
        # hidden: [num_layers * 2, batch, hidden_dim]
        # Take last layer, concatenate forward and backward
        forward_hidden = hidden[-2, :, :]   # [batch, hidden_dim]
        backward_hidden = hidden[-1, :, :]  # [batch, hidden_dim]
        pooled = torch.cat([forward_hidden, backward_hidden], dim=1)  # [batch, hidden_dim*2]
        
        pooled = self.dropout(pooled)
        logits = self.classifier(pooled)  # [batch, num_aspects * num_classes]
        
        # Reshape to [batch, num_aspects, num_classes]
        batch_size = logits.size(0)
        logits = logits.view(batch_size, self.num_aspects, self.num_classes)
        
        return logits


class ABSADataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=128):
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
    """Load and process ABSA labeled data"""
    print(f"\nLoading data from {data_file}...")
    df = pd.read_csv(data_file)
    print(f"✓ Loaded {len(df)} labeled posts")
    
    # Extract texts
    texts = df['text'].tolist()
    
    # Extract multi-label sentiments (10 aspects × 3 classes)
    aspect_cols = [col for col in df.columns if col.startswith('sentiment_')]
    print(f"✓ Extracted {len(aspect_cols)} sentiment dimensions")
    
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
    print(f"✓ Label shape: {labels.shape}")
    
    return texts, labels


def train_epoch(model, data_loader, optimizer, device):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    criterion = nn.CrossEntropyLoss()
    
    for batch in tqdm(data_loader, desc="Training"):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)  # [batch, 10]
        
        optimizer.zero_grad()
        
        # Forward
        logits = model(input_ids, attention_mask)  # [batch, 10, 3]
        
        # Compute loss for each aspect
        loss = 0
        for aspect_idx in range(10):
            aspect_logits = logits[:, aspect_idx, :]  # [batch, 3]
            aspect_labels = labels[:, aspect_idx]      # [batch]
            loss += criterion(aspect_logits, aspect_labels)
        loss = loss / 10  # Average over aspects
        
        # Backward
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    return total_loss / len(data_loader)


def evaluate(model, data_loader, device):
    """Evaluate model"""
    model.eval()
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch in tqdm(data_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].cpu().numpy()
            
            logits = model(input_ids, attention_mask)
            preds = torch.argmax(logits, dim=2).cpu().numpy()  # [batch, 10]
            
            all_preds.append(preds)
            all_labels.append(labels)
    
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)
    
    # Calculate metrics
    f1_micro = f1_score(all_labels.flatten(), all_preds.flatten(), average='micro')
    f1_macro = f1_score(all_labels.flatten(), all_preds.flatten(), average='macro')
    h_loss = hamming_loss(all_labels, all_preds)
    
    return {
        'f1_micro': f1_micro,
        'f1_macro': f1_macro,
        'hamming_loss': h_loss
    }


def train(config):
    """Main training function"""
    print("=" * 80)
    print("LIGHTWEIGHT BILSTM ABSA TRAINING")
    print("=" * 80)
    
    device = torch.device('cpu')  # Force CPU to avoid GPU memory issues
    print(f"\nDevice: CPU (lightweight model, fast enough)")
    
    # Load data
    texts, labels = load_data(config['data_file'])
    
    # Split data
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        texts, labels, test_size=0.3, random_state=42
    )
    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts, temp_labels, test_size=0.5, random_state=42
    )
    
    print(f"\nData split:")
    print(f"  Train: {len(train_texts)} posts")
    print(f"  Val:   {len(val_texts)} posts")
    print(f"  Test:  {len(test_texts)} posts")
    
    # Load tokenizer (only tokenizer, not model!)
    print(f"\nLoading tokenizer: {config['tokenizer_name']}")
    tokenizer = AutoTokenizer.from_pretrained(config['tokenizer_name'])
    
    # Create datasets
    train_dataset = ABSADataset(train_texts, train_labels, tokenizer, config['max_length'])
    val_dataset = ABSADataset(val_texts, val_labels, tokenizer, config['max_length'])
    test_dataset = ABSADataset(test_texts, test_labels, tokenizer, config['max_length'])
    
    # Create dataloaders
    train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=config['batch_size'])
    test_loader = DataLoader(test_dataset, batch_size=config['batch_size'])
    
    # Initialize model
    print(f"\nInitializing BiLSTM model...")
    model = SimpleBiLSTMABSA(
        vocab_size=tokenizer.vocab_size,
        embedding_dim=config['embedding_dim'],
        hidden_dim=config['hidden_dim'],
        num_layers=config['num_layers'],
        num_aspects=config['num_aspects'],
        num_classes=config['num_classes'],
        dropout=config['dropout']
    )
    model = model.to(device)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"✓ Model has {total_params:,} parameters (~{total_params/1e6:.1f}M)")
    print(f"  vs PhoBERT: 135M parameters (you save ~{135 - total_params/1e6:.0f}M!)")
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(), 
        lr=config['learning_rate'],
        weight_decay=config['weight_decay']
    )
    
    # Training loop
    print(f"\n{'='*80}")
    print("TRAINING")
    print(f"{'='*80}")
    
    best_val_f1 = 0
    for epoch in range(config['num_epochs']):
        print(f"\nEpoch {epoch+1}/{config['num_epochs']}")
        print("-" * 80)
        
        train_loss = train_epoch(model, train_loader, optimizer, device)
        val_metrics = evaluate(model, val_loader, device)
        
        print(f"Train Loss: {train_loss:.4f}")
        print(f"Val F1 (micro): {val_metrics['f1_micro']:.4f}")
        print(f"Val F1 (macro): {val_metrics['f1_macro']:.4f}")
        print(f"Val Hamming Loss: {val_metrics['hamming_loss']:.4f}")
        
        # Save best model
        if val_metrics['f1_micro'] > best_val_f1:
            best_val_f1 = val_metrics['f1_micro']
            print(f"✓ New best F1: {best_val_f1:.4f}")
    
    # Test evaluation
    print(f"\n{'='*80}")
    print("TEST EVALUATION")
    print(f"{'='*80}")
    test_metrics = evaluate(model, test_loader, device)
    print(f"Test F1 (micro): {test_metrics['f1_micro']:.4f}")
    print(f"Test F1 (macro): {test_metrics['f1_macro']:.4f}")
    print(f"Test Hamming Loss: {test_metrics['hamming_loss']:.4f}")
    
    # Save model
    output_dir = config['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nSaving model to {output_dir}...")
    
    # Save model weights
    torch.save(model.state_dict(), f'{output_dir}/model.pt')
    print(f"✓ Saved model weights")
    
    # Save tokenizer
    tokenizer.save_pretrained(output_dir)
    print(f"✓ Saved tokenizer")
    
    # Save config
    with open(f'{output_dir}/config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✓ Saved config")
    
    # Save test metrics
    with open(f'{output_dir}/test_metrics.json', 'w') as f:
        json.dump(test_metrics, f, indent=2)
    print(f"✓ Saved test metrics")
    
    print(f"\n{'='*80}")
    print("TRAINING COMPLETE")
    print(f"{'='*80}")
    print(f"Model saved to: {output_dir}")
    print(f"Parameters: {total_params:,} (~{total_params/1e6:.1f}M)")
    print(f"Test F1 (micro): {test_metrics['f1_micro']:.4f}")
    print(f"Test F1 (macro): {test_metrics['f1_macro']:.4f}")
    
    return output_dir


if __name__ == '__main__':
    train(CONFIG)
