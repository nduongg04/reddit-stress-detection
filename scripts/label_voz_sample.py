#!/usr/bin/env python3
"""
Quick labeling of FIRST 500 posts only
Then train model to auto-label the rest
"""
import json
from pathlib import Path

# Load first 500 posts
with open('data/voz_preprocessed.json', 'r', encoding='utf-8') as f:
    all_posts = json.load(f)

sample_posts = all_posts[:500]

# Save sample for labeling
output = Path('data/voz_sample_500.json')
with open(output, 'w', encoding='utf-8') as f:
    json.dump(sample_posts, f, ensure_ascii=False, indent=2)

print(f"✓ Created sample: {output}")
print(f"Total: {len(sample_posts)} posts")
print(f"\nNext: Run labeling on sample only:")
print(f"  python scripts\\label_voz_weak_supervision.py --input data/voz_sample_500.json")
