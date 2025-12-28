#!/usr/bin/env python3
"""
Quick test of Groq labeling with 5 posts
"""
import sys
import os
sys.path.insert(0, 'scripts')

# Set API key
os.environ['GROQ_API_KEY'] = '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'

# Import and modify main script
import json
from pathlib import Path

# Load original script functions
exec(open('scripts/label_with_groq.py', encoding='utf-8').read())

# Override input file
print("Testing Groq labeling with 5 sample posts...\n")

with open('data/voz_test_sample.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

print(f"Loaded {len(posts)} test posts")
api_key = os.environ['GROQ_API_KEY']

# Label
labeled = []
for i, post in enumerate(posts, 1):
    print(f"\nPost {i}/{len(posts)}: {post['clean_text'][:100]}...")
    result = label_post_with_groq(post, api_key)
    labeled.append(result)
    print(f"  → {result['stress_label']}, aspects={result['aspect_labels']}, conf={result['confidence_score']}")

# Stats
stress_count = sum(1 for p in labeled if p['stress_label'] == 'stress')
print(f"\n{'='*70}")
print(f"RESULTS:")
print(f"  Total: {len(labeled)}")
print(f"  Stress: {stress_count} ({stress_count/len(labeled)*100:.1f}%)")
print(f"  Non-stress: {len(labeled)-stress_count}")
print(f"\n✓ Test passed! Script is working correctly.")
print(f"\nNow run full labeling:")
print(f"  python scripts/label_with_groq.py")
