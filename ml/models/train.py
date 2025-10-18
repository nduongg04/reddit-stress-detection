"""
Model Training Script for Reddit Stress Detection

This script trains a DistilBERT model for binary classification of stress-related content.
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
import logging

import torch
import numpy as np
import pandas as pd
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback
)
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)
from torch.utils.data import Dataset

from data_loader import StressDataset

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedditStressDataset(Dataset):
    """PyTorch Dataset for Reddit stress detection"""

    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


def compute_metrics(pred):
    """
    Compute evaluation metrics

    Args:
        pred: Predictions from the model

    Returns:
        Dictionary of metrics
    """
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average='binary'
    )
    acc = accuracy_score(labels, preds)

    return {
        'accuracy': acc,
        'precision': precision,
        'recall': recall,
        'f1': f1
    }


def train_model(
    data_dir: str = "ml/dataset/splits",
    output_dir: str = "ml/models/checkpoints",
    model_name: str = "distilbert-base-uncased",
    num_epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    max_length: int = 512,
    save_name: str = "reddit_stress_v1",
    use_gpu: bool = True
):
    """
    Train the stress detection model

    Args:
        data_dir: Directory containing train/val/test splits
        output_dir: Directory to save model checkpoints
        model_name: Pretrained model to use
        num_epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate
        max_length: Maximum sequence length
        save_name: Name for the saved model
        use_gpu: Whether to use GPU if available
    """
    logger.info("="*60)
    logger.info("REDDIT STRESS DETECTION - MODEL TRAINING")
    logger.info("="*60)

    # Create output directories
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model_save_path = Path("ml/models") / save_name
    model_save_path.mkdir(parents=True, exist_ok=True)

    # Check device
    device = torch.device("cuda" if torch.cuda.is_available() and use_gpu else "cpu")
    logger.info(f"Using device: {device}")

    # Load dataset
    logger.info("\nLoading dataset...")
    dataset = StressDataset(data_dir)
    dataset.load_splits()
    dataset.print_stats()

    # Get texts and labels
    train_texts, train_labels = dataset.get_texts_and_labels('train')
    val_texts, val_labels = dataset.get_texts_and_labels('val')
    test_texts, test_labels = dataset.get_texts_and_labels('test')

    # Initialize tokenizer and model
    logger.info(f"\nLoading model: {model_name}")
    tokenizer = DistilBertTokenizer.from_pretrained(model_name)
    model = DistilBertForSequenceClassification.from_pretrained(
        model_name,
        num_labels=2  # Binary classification
    )

    logger.info(f"Model loaded with {sum(p.numel() for p in model.parameters()):,} parameters")

    # Create PyTorch datasets
    logger.info("\nTokenizing datasets...")
    train_dataset = RedditStressDataset(train_texts, train_labels, tokenizer, max_length)
    val_dataset = RedditStressDataset(val_texts, val_labels, tokenizer, max_length)
    test_dataset = RedditStressDataset(test_texts, test_labels, tokenizer, max_length)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(output_path),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",  # Changed from evaluation_strategy in newer transformers
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=str(Path("ml/models/logs")),
        logging_steps=10,
        warmup_steps=100,
        save_total_limit=2,
        report_to="none",  # Changed from ["none"] for compatibility
        seed=42
    )

    # Initialize trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )

    # Train
    logger.info("\nStarting training...")
    logger.info(f"  Epochs: {num_epochs}")
    logger.info(f"  Batch size: {batch_size}")
    logger.info(f"  Learning rate: {learning_rate}")
    logger.info(f"  Max sequence length: {max_length}")

    train_result = trainer.train()

    logger.info("\nTraining completed!")
    logger.info(f"  Training loss: {train_result.training_loss:.4f}")

    # Evaluate on validation set
    logger.info("\nEvaluating on validation set...")
    val_results = trainer.evaluate(eval_dataset=val_dataset)

    logger.info("Validation Results:")
    for key, value in val_results.items():
        logger.info(f"  {key}: {value:.4f}")

    # Evaluate on test set
    logger.info("\nEvaluating on test set...")
    test_results = trainer.evaluate(eval_dataset=test_dataset)

    logger.info("Test Results:")
    for key, value in test_results.items():
        logger.info(f"  {key}: {value:.4f}")

    # Generate detailed classification report
    predictions = trainer.predict(test_dataset)
    pred_labels = predictions.predictions.argmax(-1)
    true_labels = test_labels

    logger.info("\nDetailed Classification Report:")
    print(classification_report(
        true_labels,
        pred_labels,
        target_names=['NON_STRESS', 'STRESS'],
        digits=4
    ))

    # Confusion matrix
    cm = confusion_matrix(true_labels, pred_labels)
    logger.info("\nConfusion Matrix:")
    logger.info(f"                 Predicted")
    logger.info(f"              NON  STRESS")
    logger.info(f"Actual NON    {cm[0][0]:4d}  {cm[0][1]:4d}")
    logger.info(f"       STRESS {cm[1][0]:4d}  {cm[1][1]:4d}")

    # Check if metrics meet targets
    targets_met = (
        test_results['eval_accuracy'] >= 0.80 and
        test_results['eval_precision'] >= 0.82 and
        test_results['eval_recall'] >= 0.85 and
        test_results['eval_f1'] >= 0.83
    )

    if targets_met:
        logger.info("\n✓ Model meets all target metrics!")
    else:
        logger.info("\n⚠ Model does not meet all target metrics.")
        logger.info("  Targets: Accuracy≥0.80, Precision≥0.82, Recall≥0.85, F1≥0.83")

    # Save model
    logger.info(f"\nSaving model to {model_save_path}...")
    model.save_pretrained(model_save_path)
    tokenizer.save_pretrained(model_save_path)

    # Save metadata
    metadata = {
        "version": "1.0.0",
        "model_name": model_name,
        "training_date": datetime.now().isoformat(),
        "training_samples": len(train_texts),
        "validation_samples": len(val_texts),
        "test_samples": len(test_texts),
        "hyperparameters": {
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": max_length
        },
        "metrics": {
            "train_loss": float(train_result.training_loss),
            "val_accuracy": float(test_results['eval_accuracy']),
            "val_precision": float(test_results['eval_precision']),
            "val_recall": float(test_results['eval_recall']),
            "val_f1": float(test_results['eval_f1']),
            "test_accuracy": float(test_results['eval_accuracy']),
            "test_precision": float(test_results['eval_precision']),
            "test_recall": float(test_results['eval_recall']),
            "test_f1": float(test_results['eval_f1'])
        },
        "targets_met": targets_met,
        "dataset_version": "1.0.0"
    }

    metadata_path = model_save_path / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Metadata saved to {metadata_path}")

    # Also save to registry
    registry_path = Path("ml/models/registry/v1")
    registry_path.mkdir(parents=True, exist_ok=True)
    with open(registry_path / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE!")
    logger.info("="*60)
    logger.info(f"Model saved to: {model_save_path}")
    logger.info(f"Test F1 Score: {test_results['eval_f1']:.4f}")
    logger.info("="*60)

    return model, tokenizer, metadata


def main():
    parser = argparse.ArgumentParser(description="Train Reddit stress detection model")
    parser.add_argument("--data-dir", default="ml/dataset/splits", help="Dataset directory")
    parser.add_argument("--output-dir", default="ml/models/checkpoints", help="Checkpoint directory")
    parser.add_argument("--model-name", default="distilbert-base-uncased", help="Pretrained model")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--max-length", type=int, default=512, help="Max sequence length")
    parser.add_argument("--save-name", default="reddit_stress_v1", help="Model save name")
    parser.add_argument("--cpu", action="store_true", help="Force CPU usage")
    parser.add_argument("--create-sample-data", action="store_true", help="Create sample dataset first")

    args = parser.parse_args()

    # Create sample data if requested
    if args.create_sample_data:
        logger.info("Creating sample dataset...")
        from data_loader import create_sample_dataset
        create_sample_dataset(output_dir=args.data_dir, num_samples=1000)

    # Train model
    train_model(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        model_name=args.model_name,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        save_name=args.save_name,
        use_gpu=not args.cpu
    )


if __name__ == "__main__":
    main()
