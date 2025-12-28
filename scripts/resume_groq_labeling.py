#!/usr/bin/env python3
"""
Resume Groq labeling from checkpoint after rate limit

Usage:
1. Check current progress:
   python scripts/resume_groq_labeling.py --check

2. Resume from last position:
   python scripts/resume_groq_labeling.py --resume
"""
import json
import sys
import argparse
from pathlib import Path

def check_progress():
    """Check current labeling progress"""
    input_file = Path('data/voz_preprocessed.json')
    high_conf_file = Path('data/voz_labeled_high_confidence.json')
    low_conf_file = Path('data/voz_labeled_low_confidence.json')
    
    # Load original
    with open(input_file, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)
    
    print(f"📊 PROGRESS CHECK")
    print(f"="*70)
    print(f"Total posts: {len(all_posts):,}")
    
    # Check labeled posts
    labeled_count = 0
    if high_conf_file.exists():
        with open(high_conf_file, 'r', encoding='utf-8') as f:
            high_conf = json.load(f)
            labeled_count += len(high_conf)
            print(f"High-confidence: {len(high_conf):,} posts")
    
    if low_conf_file.exists():
        with open(low_conf_file, 'r', encoding='utf-8') as f:
            low_conf = json.load(f)
            labeled_count += len(low_conf)
            print(f"Low-confidence: {len(low_conf):,} posts")
    
    remaining = len(all_posts) - labeled_count
    progress = labeled_count / len(all_posts) * 100
    
    print(f"\n✅ Labeled: {labeled_count:,} ({progress:.1f}%)")
    print(f"❌ Remaining: {remaining:,} ({100-progress:.1f}%)")
    
    if remaining > 0:
        print(f"\n💡 To resume:")
        print(f"   python scripts/resume_groq_labeling.py --resume --start={labeled_count}")
    else:
        print(f"\n🎉 All posts labeled!")
    
    return labeled_count, remaining

def resume_labeling(start_idx):
    """Resume labeling from specific index"""
    print(f"\n🔄 RESUME LABELING FROM POST {start_idx:,}")
    print(f"="*70)
    
    # Import main labeling functions
    import os
    os.environ['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY', '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')
    
    from label_with_groq import (
        label_post_with_groq, 
        ASPECT_IDS
    )
    from tqdm import tqdm
    from datetime import datetime
    
    # Load data
    input_file = Path('data/voz_preprocessed.json')
    with open(input_file, 'r', encoding='utf-8') as f:
        all_posts = json.load(f)
    
    # Get remaining posts
    remaining_posts = all_posts[start_idx:]
    print(f"📂 Loaded {len(remaining_posts):,} remaining posts")
    
    api_key = os.getenv('GROQ_API_KEY')
    print(f"✓ API Key: {api_key[:20]}...")
    print(f"\n⏳ Starting labeling...")
    
    # Label remaining
    labeled_posts = []
    for post in tqdm(remaining_posts, desc="🏷️  Resuming", unit="post"):
        labeled = label_post_with_groq(post, api_key)
        labeled_posts.append(labeled)
    
    # Load existing results
    high_conf_file = Path('data/voz_labeled_high_confidence.json')
    low_conf_file = Path('data/voz_labeled_low_confidence.json')
    
    existing_high = []
    existing_low = []
    
    if high_conf_file.exists():
        with open(high_conf_file, 'r', encoding='utf-8') as f:
            existing_high = json.load(f)
    
    if low_conf_file.exists():
        with open(low_conf_file, 'r', encoding='utf-8') as f:
            existing_low = json.load(f)
    
    # Merge with new results
    new_high = [p for p in labeled_posts if p['confidence_score'] >= 0.7]
    new_low = [p for p in labeled_posts if p['confidence_score'] < 0.7]
    
    all_high = existing_high + new_high
    all_low = existing_low + new_low
    
    # Save merged results
    with open(high_conf_file, 'w', encoding='utf-8') as f:
        json.dump(all_high, f, ensure_ascii=False, indent=2)
    
    with open(low_conf_file, 'w', encoding='utf-8') as f:
        json.dump(all_low, f, ensure_ascii=False, indent=2)
    
    # Print stats
    total_labeled = len(all_high) + len(all_low)
    stress_posts = [p for p in all_high + all_low if p['stress_label'] == 'stress']
    
    print(f"\n{'='*70}")
    print(f"✅ LABELING COMPLETE")
    print(f"{'='*70}")
    print(f"Total labeled: {total_labeled:,}")
    print(f"Stress posts: {len(stress_posts):,} ({len(stress_posts)/total_labeled*100:.1f}%)")
    print(f"High-confidence: {len(all_high):,} ({len(all_high)/total_labeled*100:.1f}%)")
    print(f"Low-confidence: {len(all_low):,}")
    
    print(f"\n💾 Saved to:")
    print(f"   {high_conf_file}")
    print(f"   {low_conf_file}")

def main():
    parser = argparse.ArgumentParser(description='Resume Groq labeling')
    parser.add_argument('--check', action='store_true', help='Check progress')
    parser.add_argument('--resume', action='store_true', help='Resume labeling')
    parser.add_argument('--start', type=int, help='Start index (auto-detect if not provided)')
    
    args = parser.parse_args()
    
    if args.check or (not args.resume):
        labeled, remaining = check_progress()
        return
    
    if args.resume:
        if args.start is None:
            # Auto-detect start position
            labeled, remaining = check_progress()
            if remaining == 0:
                print("\n✅ All posts already labeled!")
                return
            start_idx = labeled
        else:
            start_idx = args.start
        
        print(f"\n⚠️  WARNING: Make sure Groq API rate limit has reset!")
        print(f"   Check: https://console.groq.com/settings/limits")
        input("\nPress ENTER to continue...")
        
        resume_labeling(start_idx)

if __name__ == '__main__':
    main()
