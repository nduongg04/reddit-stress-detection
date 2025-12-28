import json
from datetime import datetime

# Load checkpoint
with open('data/checkpoint_labeled.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("="*70)
print("CHECKPOINT STATUS")
print("="*70)
print(f"Total posts saved: {len(data):,}")
print(f"File size: 5.17 MB")
print(f"Last updated: 12/27/2025 12:13 PM")

# Analyze
high = [p for p in data if p.get('confidence_score', 0) >= 0.7]
low = [p for p in data if p.get('confidence_score', 0) < 0.7]
stress = [p for p in data if p.get('stress_label') == 'stress']

print(f"\n📊 STATISTICS:")
print(f"  Stress posts: {len(stress):,} ({len(stress)/len(data)*100:.1f}%)")
print(f"  High-confidence (≥0.7): {len(high):,} ({len(high)/len(data)*100:.1f}%)")
print(f"  Low-confidence (<0.7): {len(low):,} ({len(low)/len(data)*100:.1f}%)")

# Progress
total_needed = 4969
progress = len(data) / total_needed * 100
remaining = total_needed - len(data)

print(f"\n📈 PROGRESS:")
print(f"  Completed: {len(data):,} / {total_needed:,} ({progress:.1f}%)")
print(f"  Remaining: {remaining:,} posts")
print(f"  Days needed: ~{remaining // 700 + 1} days (700 posts/day)")

print(f"\n✅ DATA SAVED SUCCESSFULLY!")
print(f"Resume tomorrow with: python scripts/label_groq_checkpoint.py")
