#!/usr/bin/env python3
"""Export trained PhoBERT model to ONNX format."""

import argparse
from pathlib import Path

import numpy as np
import torch
import yaml

from model import PhoBERTStressClassifier
from transformers import AutoTokenizer


def export_to_onnx(model_dir: str, output_path: str, opset_version: int = 14):
    """Export model to ONNX format."""
    model_path = Path(model_dir)

    # Load config
    with open(model_path / "config.yaml") as f:
        config = yaml.safe_load(f)

    # Load model
    print("Loading model...")
    model = PhoBERTStressClassifier.load(
        str(model_path / "best_model.pt"),
        model_name=config["model"]["name"],
        device="cpu"
    )
    model.eval()

    # Load tokenizer for dummy input
    tokenizer = AutoTokenizer.from_pretrained(str(model_path / "tokenizer"))

    # Create dummy input
    dummy_text = "Đây là một bài viết mẫu để xuất mô hình"
    dummy_input = tokenizer(
        dummy_text,
        max_length=config["model"]["max_length"],
        padding="max_length",
        truncation=True,
        return_tensors="pt"
    )

    input_ids = dummy_input["input_ids"]
    attention_mask = dummy_input["attention_mask"]

    # Export to ONNX
    print(f"Exporting to ONNX (opset {opset_version})...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (input_ids, attention_mask),
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size"},
            "attention_mask": {0: "batch_size"},
            "logits": {0: "batch_size"}
        }
    )

    print(f"ONNX model saved to: {output_path}")

    # Verify export
    print("\nVerifying ONNX export...")
    import onnxruntime as ort

    session = ort.InferenceSession(output_path)

    # PyTorch inference
    with torch.no_grad():
        pt_output = model(input_ids, attention_mask).numpy()

    # ONNX inference
    onnx_output = session.run(
        None,
        {
            "input_ids": input_ids.numpy(),
            "attention_mask": attention_mask.numpy()
        }
    )[0]

    # Compare
    diff = np.abs(pt_output - onnx_output).max()
    print(f"Max difference between PyTorch and ONNX: {diff:.6f}")

    if diff < 1e-4:
        print("✓ ONNX export verified successfully!")
    else:
        print("⚠ Warning: Outputs differ more than expected")

    # Save label mapping
    label_mapping = {
        "aspects": [
            {"id": 0, "name": "occupational", "vi": "Công việc"},
            {"id": 1, "name": "self_image", "vi": "Hình ảnh bản thân"},
            {"id": 2, "name": "health", "vi": "Sức khỏe"},
            {"id": 3, "name": "academic", "vi": "Học tập"},
            {"id": 4, "name": "romantic", "vi": "Tình cảm"},
            {"id": 5, "name": "familial", "vi": "Gia đình"},
            {"id": 6, "name": "financial", "vi": "Tài chính"},
            {"id": 7, "name": "life_events", "vi": "Sự kiện"},
            {"id": 8, "name": "existential", "vi": "Hiện sinh"},
        ],
        "threshold": 0.5,
        "max_length": config["model"]["max_length"]
    }

    import json
    label_path = Path(output_path).parent / "label_encoder.json"
    with open(label_path, "w", encoding="utf-8") as f:
        json.dump(label_mapping, f, ensure_ascii=False, indent=2)
    print(f"Label mapping saved to: {label_path}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export model to ONNX")
    parser.add_argument("--model", "-m", default="ml/checkpoints/phobert_stress_v1")
    parser.add_argument("--output", "-o", default="ml/exports/phobert_stress.onnx")
    parser.add_argument("--opset", type=int, default=14)
    args = parser.parse_args()

    export_to_onnx(args.model, args.output, args.opset)
