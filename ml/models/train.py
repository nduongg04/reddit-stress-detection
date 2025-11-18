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
import torch.nn as nn
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
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import Dataset

from data_loader import StressDataset
from augmentation import TextAugmenter, oversample_minority_class
from focal_loss import WeightedFocalLoss

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeightedTrainer(Trainer):
    """Custom Trainer with class weights and optional focal loss for imbalanced data"""

    def __init__(self, *args, class_weights=None, use_focal_loss=False, focal_gamma=2.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights
        self.use_focal_loss = use_focal_loss
        self.focal_gamma = focal_gamma

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        # Choose loss function
        if self.use_focal_loss:
            # Use focal loss for hard examples
            loss_fct = WeightedFocalLoss(
                class_weights=self.class_weights.to(logits.device) if self.class_weights is not None else None,
                gamma=self.focal_gamma
            )
        else:
            # Use standard cross entropy with class weights
            if self.class_weights is not None:
                loss_fct = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
            else:
                loss_fct = nn.CrossEntropyLoss()

        loss = loss_fct(logits, labels)

        return (loss, outputs) if return_outputs else loss


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


# Augmentation functions are now in augmentation.py


def compute_metrics(pred):
    """
    Compute evaluation metrics (optimized for imbalanced classification)

    Args:
        pred: Predictions from the model

    Returns:
        Dictionary of metrics
    """
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)

    # Binary metrics
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average='binary'
    )
    acc = accuracy_score(labels, preds)

    # Per-class metrics for better understanding
    precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(
        labels, preds, average=None, labels=[0, 1]
    )

    return {
        'accuracy': acc,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'precision_class_0': precision_per_class[0],
        'recall_class_0': recall_per_class[0],
        'f1_class_0': f1_per_class[0],
        'precision_class_1': precision_per_class[1],
        'recall_class_1': recall_per_class[1],
        'f1_class_1': f1_per_class[1]
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
    use_gpu: bool = True,
    file_suffix: str = "",
    balance_data: bool = True,
    balance_ratio: float = 0.4,
    use_focal_loss: bool = True,
    focal_gamma: float = 2.0
):
    """
    Train the stress detection model with advanced techniques for imbalanced data

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
        file_suffix: Optional suffix for data files (e.g., "_v2" for train_v2.csv)
        balance_data: Whether to balance dataset with augmentation
        balance_ratio: Target ratio for minority class (0.4 = 40% minority, 60% majority)
        use_focal_loss: Whether to use focal loss instead of standard CE loss
        focal_gamma: Focusing parameter for focal loss (higher = more focus on hard examples)
    """
    logger.info("="*60)
    logger.info("REDDIT STRESS DETECTION - MODEL TRAINING")
    logger.info("="*60)

    # Create output directories
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model_save_path = Path("ml/models") / save_name
    model_save_path.mkdir(parents=True, exist_ok=True)

    # Check device - support CUDA, MPS (Mac GPU), and CPU
    if use_gpu:
        if torch.cuda.is_available():
            device = torch.device("cuda")
            logger.info(f"Using device: CUDA GPU")
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
            logger.info(f"Using device: MPS (Apple Silicon GPU)")
        else:
            device = torch.device("cpu")
            logger.info(f"Using device: CPU (no GPU available)")
    else:
        device = torch.device("cpu")
        logger.info(f"Using device: CPU (forced)")

    # Load dataset
    logger.info("\nLoading dataset...")
    dataset = StressDataset(data_dir, file_suffix=file_suffix)
    dataset.load_splits()
    dataset.print_stats()

    # Get texts and labels
    train_texts, train_labels = dataset.get_texts_and_labels('train')
    val_texts, val_labels = dataset.get_texts_and_labels('val')
    test_texts, test_labels = dataset.get_texts_and_labels('test')

    # Balance training data if requested
    if balance_data:
        logger.info("\n" + "="*60)
        logger.info("BALANCING TRAINING DATA WITH ADVANCED AUGMENTATION")
        logger.info("="*60)
        augmenter = TextAugmenter(random_state=42)
        train_texts, train_labels = oversample_minority_class(
            train_texts, train_labels,
            target_ratio=balance_ratio,
            augmenter=augmenter
        )
        logger.info("="*60)

    # Compute class weights for imbalanced dataset
    logger.info("\nComputing class weights for imbalanced data...")
    class_weights = compute_class_weight(
        class_weight='balanced',
        classes=np.unique(train_labels),
        y=train_labels
    )
    class_weights = torch.tensor(class_weights, dtype=torch.float)
    logger.info(f"Class weights: {class_weights.numpy()}")
    logger.info(f"  Class 0 (non-stress): {class_weights[0]:.4f}")
    logger.info(f"  Class 1 (stress): {class_weights[1]:.4f}")

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
    # Determine if we should use fp16 (only on CUDA, not MPS)
    use_fp16 = torch.cuda.is_available() and use_gpu

    # For newer transformers (5.0+), MPS is automatically used if available
    # We just need to set no_cuda=True if we're not using CUDA
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
        seed=42,
        fp16=use_fp16  # Only use fp16 on CUDA, not MPS
        # MPS is automatically detected and used in transformers 5.0+
        # no_cuda is not needed as it's the default when CUDA is not available
    )

    # Initialize trainer with class weights and focal loss
    logger.info("\nTrainer configuration:")
    logger.info(f"  Loss function: {'Focal Loss' if use_focal_loss else 'Cross Entropy'}")
    if use_focal_loss:
        logger.info(f"  Focal gamma: {focal_gamma}")
    logger.info(f"  Class weights: {class_weights.numpy()}")

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
        class_weights=class_weights,
        use_focal_loss=use_focal_loss,
        focal_gamma=focal_gamma
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
    parser.add_argument("--epochs", type=int, default=5, help="Number of epochs (default: 5)")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--learning-rate", type=float, default=3e-5, help="Learning rate (default: 3e-5)")
    parser.add_argument("--max-length", type=int, default=512, help="Max sequence length")
    parser.add_argument("--save-name", default="reddit_stress_v1", help="Model save name")
    parser.add_argument("--cpu", action="store_true", help="Force CPU usage")
    parser.add_argument("--create-sample-data", action="store_true", help="Create sample dataset first")
    parser.add_argument("--file-suffix", default="", help="Suffix for data files (e.g., '_v2')")
    parser.add_argument("--balance-data", action="store_true", default=True, help="Balance dataset with augmentation")
    parser.add_argument("--no-balance", dest="balance_data", action="store_false", help="Disable data balancing")
    parser.add_argument("--balance-ratio", type=float, default=0.5, help="Target ratio for minority class (default: 0.5 = fully balanced)")
    parser.add_argument("--focal-loss", action="store_true", default=True, help="Use focal loss for imbalanced data")
    parser.add_argument("--no-focal", dest="focal_loss", action="store_false", help="Disable focal loss")
    parser.add_argument("--focal-gamma", type=float, default=2.5, help="Focal loss gamma parameter (default: 2.5)")

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
        use_gpu=not args.cpu,
        file_suffix=args.file_suffix,
        balance_data=args.balance_data,
        balance_ratio=args.balance_ratio,
        use_focal_loss=args.focal_loss,
        focal_gamma=args.focal_gamma
    )


if __name__ == "__main__":
    main()
