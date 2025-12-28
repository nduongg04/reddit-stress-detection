#!/usr/bin/env python3
"""
Task 2.3: Groq Labeling with INCREMENTAL SAVE (checkpoint every 100 posts)
Fixed: Save progress to avoid losing data on rate limit
"""
import json
import os
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

from groq import Groq

# Copy all functions from label_with_groq.py
ASPECTS = {
    'work_pressure': 'Stress vì deadline / áp lực công việc',
    'relationship': 'Stress vì chuyện tình cảm / mối quan hệ cá nhân',
    'financial': 'Stress vì thất nghiệp / khó khăn tài chính',
    'study': 'Stress vì học tập / thi cử',
    'family_social': 'Stress vì xung đột gia đình / xã hội',
    'health': 'Stress vì sức khỏe / bệnh tật'
}
ASPECT_IDS = list(ASPECTS.keys())

exec(open('scripts/label_with_groq.py', encoding='utf-8').read().split('def main')[0])

def save_checkpoint(labeled_posts, checkpoint_file='data/checkpoint_labeled.json'):
    """Save current progress"""
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(labeled_posts, f, ensure_ascii=False, indent=2)

def load_checkpoint(checkpoint_file='data/checkpoint_labeled.json'):
    """Load previous progress"""
    if Path(checkpoint_file).exists():
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def main_with_checkpoints():
    print("="*70)
    print("TASK 2.3: GROQ LABELING WITH CHECKPOINTS")
    print("="*70)
    
    api_key = os.getenv('GROQ_API_KEY', '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')
    print(f"✓ API Key: {api_key[:20]}...")
    
    # Load data
    with open('data/voz_preprocessed.json', 'r', encoding='utf-8') as f:
        all_posts = json.load(f)
    
    # Check checkpoint
    checkpoint_file = 'data/checkpoint_labeled.json'
    existing_labels = load_checkpoint(checkpoint_file)
    start_idx = len(existing_labels)
    
    if start_idx > 0:
        print(f"\n🔄 RESUMING from checkpoint: {start_idx:,} posts already labeled")
    else:
        print(f"\n🆕 Starting fresh labeling")
    
    remaining_posts = all_posts[start_idx:]
    print(f"📂 Will label: {len(remaining_posts):,} posts")
    print(f"💾 Checkpoint every: 100 posts")
    print(f"\n⏳ Starting...")
    
    labeled_posts = existing_labels.copy()
    
    for i, post in enumerate(tqdm(remaining_posts, desc="🏷️ Labeling", unit="post")):
        try:
            labeled = label_post_with_groq(post, api_key)
            labeled_posts.append(labeled)
            
            # Save checkpoint every 100 posts
            if (i + 1) % 100 == 0:
                save_checkpoint(labeled_posts, checkpoint_file)
                tqdm.write(f"💾 Checkpoint saved: {len(labeled_posts):,} posts")
                
        except Exception as e:
            if '429' in str(e) or 'rate_limit' in str(e).lower():
                print(f"\n\n⚠️ RATE LIMIT HIT at post {start_idx + i}")
                print(f"💾 Saving checkpoint: {len(labeled_posts):,} posts")
                save_checkpoint(labeled_posts, checkpoint_file)
                print(f"\n✅ Progress saved! Resume later with:")
                print(f"   python scripts/label_groq_checkpoint.py")
                return 1
            else:
                print(f"\n❌ Error at post {i}: {e}")
                # Continue with default label
                labeled_posts.append({
                    **post,
                    'stress_label': 'non_stress',
                    'aspect_labels': [],
                    'confidence_score': 0.0,
                    'label_source': 'groq_error',
                    'labeled_at': datetime.now().isoformat()
                })
    
    # Final save
    save_checkpoint(labeled_posts, checkpoint_file)
    
    # Split high/low
    high = [p for p in labeled_posts if p['confidence_score'] >= 0.7]
    low = [p for p in labeled_posts if p['confidence_score'] < 0.7]
    
    with open('data/voz_labeled_high_confidence.json', 'w', encoding='utf-8') as f:
        json.dump(high, f, ensure_ascii=False, indent=2)
    
    with open('data/voz_labeled_low_confidence.json', 'w', encoding='utf-8') as f:
        json.dump(low, f, ensure_ascii=False, indent=2)
    
    # Stats
    stress = [p for p in labeled_posts if p['stress_label'] == 'stress']
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE")
    print(f"{'='*70}")
    print(f"Total: {len(labeled_posts):,}")
    print(f"Stress: {len(stress):,} ({len(stress)/len(labeled_posts)*100:.1f}%)")
    print(f"High-conf: {len(high):,} ({len(high)/len(labeled_posts)*100:.1f}%)")
    print(f"Low-conf: {len(low):,}")
    
    return 0

if __name__ == '__main__':
    exit(main_with_checkpoints())
