"""PhoBERT-based multi-label stress classifier."""

import torch
import torch.nn as nn
from transformers import AutoModel


class PhoBERTStressClassifier(nn.Module):
    """PhoBERT with classification head for multi-label stress detection."""

    def __init__(self, model_name: str = "vinai/phobert-base",
                 num_aspects: int = 9, dropout: float = 0.3,
                 gradient_checkpointing: bool = False):
        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        # Enable gradient checkpointing to reduce memory usage
        if gradient_checkpointing:
            self.phobert.gradient_checkpointing_enable()
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.phobert.config.hidden_size, num_aspects)
        self.num_aspects = num_aspects

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
        # Use [CLS] token representation
        pooled = outputs.last_hidden_state[:, 0, :]
        pooled = self.dropout(pooled)
        logits = self.classifier(pooled)
        return logits

    def predict(self, input_ids, attention_mask, threshold: float = 0.5):
        """Get binary predictions."""
        logits = self.forward(input_ids, attention_mask)
        probs = torch.sigmoid(logits)
        return (probs > threshold).int(), probs

    def save(self, path: str):
        """Save model checkpoint."""
        torch.save({
            "model_state_dict": self.state_dict(),
            "num_aspects": self.num_aspects,
        }, path)

    @classmethod
    def load(cls, path: str, model_name: str = "vinai/phobert-base", device: str = "cpu"):
        """Load model from checkpoint."""
        checkpoint = torch.load(path, map_location=device)
        model = cls(model_name=model_name, num_aspects=checkpoint["num_aspects"])
        model.load_state_dict(checkpoint["model_state_dict"])
        return model
