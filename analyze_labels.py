import json

# Analyze saved labels
with open('data/voz_labeled_low_confidence.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"{'='*70}")
print(f"LABEL ANALYSIS")
print(f"{'='*70}")
print(f"Total posts: {len(data):,}")

# Stress classification
stress = [p for p in data if p.get('stress_label') == 'stress']
print(f"\nStress posts: {len(stress):,} ({len(stress)/len(data)*100:.1f}%)")
print(f"Non-stress: {len(data)-len(stress):,} ({(len(data)-len(stress))/len(data)*100:.1f}%)")

# Confidence distribution
high = [p for p in data if p.get('confidence_score', 0) >= 0.7]
low = [p for p in data if p.get('confidence_score', 0) < 0.7]
print(f"\nConfidence split:")
print(f"  High (≥0.7): {len(high):,} ({len(high)/len(data)*100:.1f}%)")
print(f"  Low (<0.7): {len(low):,} ({len(low)/len(data)*100:.1f}%)")

# Aspect distribution
from collections import Counter
all_aspects = []
for p in stress:
    all_aspects.extend(p.get('aspect_labels', []))
aspect_counts = Counter(all_aspects)

print(f"\nAspect distribution (in stress posts):")
for aspect, count in aspect_counts.most_common():
    pct = count / len(stress) * 100 if stress else 0
    print(f"  {aspect:20s}: {count:4d} ({pct:5.1f}%)")

# Sample posts
print(f"\n{'='*70}")
print(f"SAMPLE POSTS")
print(f"{'='*70}")

if stress:
    print(f"\n✅ STRESS POST:")
    s = stress[0]
    print(f"  ID: {s['post_id']}")
    print(f"  Text: {s['clean_text'][:150]}...")
    print(f"  Label: {s['stress_label']}")
    print(f"  Aspects: {s['aspect_labels']}")
    print(f"  Confidence: {s['confidence_score']}")

non_stress = [p for p in data if p.get('stress_label') == 'non_stress']
if non_stress:
    print(f"\n❌ NON-STRESS POST:")
    ns = non_stress[0]
    print(f"  ID: {ns['post_id']}")
    print(f"  Text: {ns['clean_text'][:150]}...")
    print(f"  Label: {ns['stress_label']}")
    print(f"  Confidence: {ns['confidence_score']}")

print(f"\n{'='*70}")
print(f"RECOMMENDATION")
print(f"{'='*70}")
print(f"✅ All 4,969 posts have been labeled!")
print(f"🔄 Need to split into high/low confidence files")
print(f"\nRun: python scripts/split_confidence.py")
