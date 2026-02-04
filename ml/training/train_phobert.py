#!/usr/bin/env python3
"""Train PhoBERT for Vietnamese stress classification."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import yaml
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from tqdm import tqdm
from transformers import AutoTokenizer

from dataset import StressDataset
from model import PhoBERTStressClassifier


def get_device():
    """Get best available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def evaluate(model, dataloader, device, threshold=0.5):
    """Evaluate model on dataloader."""
    model.eval()
    all_preds = []
    all_labels = []
    total_loss = 0
    criterion = nn.BCEWithLogitsLoss()

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)
            total_loss += loss.item()

            probs = torch.sigmoid(logits)
            preds = (probs > threshold).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    f1_micro = f1_score(all_labels, all_preds, average="micro", zero_division=0)
    precision = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="macro", zero_division=0)

    # Per-aspect F1
    per_aspect_f1 = f1_score(all_labels, all_preds, average=None, zero_division=0)

    return {
        "loss": avg_loss,
        "f1_macro": f1_macro,
        "f1_micro": f1_micro,
        "precision": precision,
        "recall": recall,
        "per_aspect_f1": per_aspect_f1.tolist()
    }


def train(config_path: str, train_path: str, val_path: str, output_dir: str):
    """Main training function."""
    # Load config
    with open(config_path) as f:
        config = yaml.safe_load(f)

    device = get_device()
    print(f"Using device: {device}")

    # Memory optimization for CPU training
    if device.type == "cpu":
        torch.set_num_threads(2)  # Limit threads to prevent memory explosion
        print("CPU mode: enabled memory optimizations")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load tokenizer and create dataloaders
    print("Loading data...")
    tokenizer_name = config["model"]["name"]
    max_length = config["model"]["max_length"]
    batch_size = config["training"]["batch_size"]

    train_dataset = StressDataset(train_path, tokenizer_name, max_length)
    val_dataset = StressDataset(val_path, tokenizer_name, max_length)

    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True
    )

    print(f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")

    # Initialize model with gradient checkpointing on CPU
    print("Initializing model...")
    use_gradient_checkpointing = device.type == "cpu"
    if use_gradient_checkpointing:
        print("Enabling gradient checkpointing to reduce memory usage")
    model = PhoBERTStressClassifier(
        model_name=tokenizer_name,
        num_aspects=config["model"]["num_aspects"],
        dropout=config["model"]["dropout"],
        gradient_checkpointing=use_gradient_checkpointing
    ).to(device)

    # Loss, optimizer, scheduler
    criterion = nn.BCEWithLogitsLoss()
    optimizer = AdamW(
        model.parameters(),
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"]["weight_decay"]
    )

    # Gradient accumulation
    gradient_accumulation_steps = config["training"].get("gradient_accumulation", 1)

    num_training_steps = (len(train_loader) // gradient_accumulation_steps) * config["training"]["epochs"]
    # Ensure at least 1 step
    num_training_steps = max(1, num_training_steps)

    scheduler = OneCycleLR(
        optimizer,
        max_lr=config["training"]["learning_rate"],
        total_steps=num_training_steps,
        pct_start=config["training"]["warmup_ratio"]
    )

    # Training loop
    best_f1 = 0
    patience_counter = 0
    training_history = []

    print(f"Starting training... (gradient accumulation: {gradient_accumulation_steps})")
    for epoch in range(config["training"]["epochs"]):
        model.train()
        train_loss = 0
        optimizer.zero_grad()
        progress = tqdm(train_loader, desc=f"Epoch {epoch+1}/{config['training']['epochs']}")

        for batch_idx, batch in enumerate(progress):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)
            loss = loss / gradient_accumulation_steps
            loss.backward()

            train_loss += loss.item() * gradient_accumulation_steps

            # Update weights every gradient_accumulation_steps
            if (batch_idx + 1) % gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            progress.set_postfix({"loss": f"{loss.item() * gradient_accumulation_steps:.4f}"})

        avg_train_loss = train_loss / len(train_loader)

        # Validation
        val_metrics = evaluate(model, val_loader, device)

        epoch_stats = {
            "epoch": epoch + 1,
            "train_loss": avg_train_loss,
            "val_loss": val_metrics["loss"],
            "val_f1_macro": val_metrics["f1_macro"],
            "val_f1_micro": val_metrics["f1_micro"],
            "val_precision": val_metrics["precision"],
            "val_recall": val_metrics["recall"],
            "per_aspect_f1": val_metrics["per_aspect_f1"],
            "lr": scheduler.get_last_lr()[0]
        }
        training_history.append(epoch_stats)

        print(f"\nEpoch {epoch+1}: train_loss={avg_train_loss:.4f}, "
              f"val_loss={val_metrics['loss']:.4f}, "
              f"val_f1_macro={val_metrics['f1_macro']:.4f}, "
              f"val_f1_micro={val_metrics['f1_micro']:.4f}")

        # Early stopping check
        if val_metrics["f1_macro"] > best_f1 + config["early_stopping"]["min_delta"]:
            best_f1 = val_metrics["f1_macro"]
            patience_counter = 0

            # Save best model
            model.save(str(output_path / "best_model.pt"))
            print(f"  New best model saved! F1={best_f1:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= config["early_stopping"]["patience"]:
                print(f"\nEarly stopping at epoch {epoch+1}")
                break

    # Save training history
    with open(output_path / "training_history.json", "w") as f:
        json.dump(training_history, f, indent=2)

    # Save tokenizer
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    tokenizer.save_pretrained(str(output_path / "tokenizer"))

    # Save config
    with open(output_path / "config.yaml", "w") as f:
        yaml.dump(config, f)

    print(f"\nTraining complete! Best F1: {best_f1:.4f}")
    print(f"Model saved to: {output_path}")

    return best_f1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PhoBERT stress classifier")
    parser.add_argument("--config", "-c", default="ml/training/config.yaml")
    parser.add_argument("--train", "-t", default="data/splits/train.jsonl")
    parser.add_argument("--val", "-v", default="data/splits/val.jsonl")
    parser.add_argument("--output", "-o", default="ml/checkpoints/phobert_stress_v1")
    args = parser.parse_args()

    train(args.config, args.train, args.val, args.output)
