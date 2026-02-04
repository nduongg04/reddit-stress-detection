"""PyTorch Dataset for Vietnamese stress classification."""

import json
import torch
from torch.utils.data import Dataset
from transformers import AutoTokenizer


class StressDataset(Dataset):
    """Dataset for multi-label stress classification."""

    def __init__(self, file_path: str, tokenizer_name: str = "vinai/phobert-base",
                 max_length: int = 256):
        self.samples = []
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.max_length = max_length

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                self.samples.append({
                    "text": data["text"],
                    "labels": data["labels"],
                    "post_id": data.get("post_id", "")
                })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]

        encoding = self.tokenizer(
            sample["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(sample["labels"], dtype=torch.float32),
            "post_id": sample["post_id"]
        }


def create_dataloader(file_path: str, tokenizer_name: str, max_length: int,
                      batch_size: int, shuffle: bool = True):
    """Create DataLoader from JSONL file."""
    dataset = StressDataset(file_path, tokenizer_name, max_length)
    return torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=True
    )
