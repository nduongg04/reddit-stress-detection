import json

# Check saved progress
try:
    with open('data/voz_labeled_high_confidence.json', 'r', encoding='utf-8') as f:
        high = json.load(f)
    print(f"High-confidence: {len(high):,} posts")
    if high:
        print(f"  Sample: {high[0]['post_id']}")
        has_labels = len([p for p in high if p.get('stress_label')])
        print(f"  With labels: {has_labels}")
except Exception as e:
    print(f"High-confidence: ERROR - {e}")
    high = []

try:
    with open('data/voz_labeled_low_confidence.json', 'r', encoding='utf-8') as f:
        low = json.load(f)
    print(f"\nLow-confidence: {len(low):,} posts")
    if low:
        print(f"  Sample: {low[0]['post_id']}")
        has_labels = len([p for p in low if p.get('stress_label')])
        print(f"  With labels: {has_labels}")
except Exception as e:
    print(f"\nLow-confidence: ERROR - {e}")
    low = []

total_saved = len(high) + len(low)
print(f"\n{'='*70}")
print(f"Total saved: {total_saved:,} posts")
print(f"Expected: 4,969 posts")
print(f"Progress: {total_saved/4969*100:.1f}%")

if total_saved < 4969:
    print(f"\n⚠️  WARNING: {4969-total_saved:,} posts NOT saved!")
    print(f"Script was interrupted before saving!")
