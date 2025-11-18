#!/usr/bin/env python3
"""
Check GPU availability for PyTorch training
"""

import torch
import sys

print("=" * 60)
print("GPU AVAILABILITY CHECK")
print("=" * 60)
print()

# Check PyTorch version
print(f"PyTorch Version: {torch.__version__}")
print()

# Check CUDA (NVIDIA GPU)
print("CUDA (NVIDIA GPU):")
print(f"  Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  Device Count: {torch.cuda.device_count()}")
    print(f"  Current Device: {torch.cuda.current_device()}")
    print(f"  Device Name: {torch.cuda.get_device_name(0)}")
print()

# Check MPS (Apple Silicon GPU)
print("MPS (Apple Silicon GPU):")
if hasattr(torch.backends, 'mps'):
    print(f"  Available: {torch.backends.mps.is_available()}")
    print(f"  Built: {torch.backends.mps.is_built()}")

    if torch.backends.mps.is_available():
        print()
        print("  ✓ MPS is available! You can use Apple Silicon GPU for training.")
        print()

        # Test MPS device
        try:
            device = torch.device("mps")
            x = torch.ones(1, device=device)
            print(f"  Test tensor on MPS: {x}")
            print("  ✓ MPS device test successful!")
        except Exception as e:
            print(f"  ✗ MPS device test failed: {e}")
    else:
        print()
        print("  ✗ MPS is not available on this system.")
        if sys.platform == "darwin":
            print("  Note: MPS requires macOS 12.3+ and PyTorch 1.12+")
else:
    print("  Not supported in this PyTorch version")
    print("  (MPS support requires PyTorch 1.12 or later)")
print()

# Recommended device
print("=" * 60)
print("RECOMMENDED DEVICE FOR TRAINING:")
if torch.cuda.is_available():
    print("  → CUDA (NVIDIA GPU)")
    recommended_device = "cuda"
elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print("  → MPS (Apple Silicon GPU)")
    recommended_device = "mps"
else:
    print("  → CPU")
    recommended_device = "cpu"
print("=" * 60)
print()

# Performance estimate
if recommended_device == "mps":
    print("Expected Training Speed:")
    print("  - MPS: ~3-5x faster than CPU")
    print("  - Training 5 epochs: ~15-30 minutes (estimated)")
elif recommended_device == "cuda":
    print("Expected Training Speed:")
    print("  - CUDA: ~5-10x faster than CPU")
    print("  - Training 5 epochs: ~10-20 minutes (estimated)")
else:
    print("Expected Training Speed:")
    print("  - CPU: Baseline")
    print("  - Training 5 epochs: ~60-120 minutes (estimated)")
print()
