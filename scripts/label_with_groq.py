#!/usr/bin/env python3
"""
Task 2.3: Initial Weak Labeling with Groq Cloud API
PIPELINE.md Section 2.3 - Weak Labeling Model

Purpose: 
- Replace Ollama local LLM (too slow: 66s/post = 86 hours)
- Use Groq Cloud API (fast: ~0.5s/post = 40 minutes)
- Label 4,969 VOZ posts with stress + 6 ABSA aspects
- Output: high-confidence set (≥0.7) và low-confidence set (<0.7)

Model: Llama-3.1-8B-Instant (FREE, 14,400 requests/day)
API: https://console.groq.com/keys

Author: Task 2.3 pipeline
Date: 2025-12-20
"""
import json
import os
import re
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

try:
    from groq import Groq
except ImportError:
    print("❌ Groq SDK not found. Installing...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'groq'])
    from groq import Groq

# 6 ABSA Aspects (PIPELINE.md Section 3.2.2)
ASPECTS = {
    'work_pressure': 'Stress vì deadline / áp lực công việc',
    'relationship': 'Stress vì chuyện tình cảm / mối quan hệ cá nhân',
    'financial': 'Stress vì thất nghiệp / khó khăn tài chính',
    'study': 'Stress vì học tập / thi cử',
    'family_social': 'Stress vì xung đột gia đình / xã hội',
    'health': 'Stress vì sức khỏe / bệnh tật'
}
ASPECT_IDS = list(ASPECTS.keys())

def create_stress_prompt(text):
    """
    Create Vietnamese prompt for stress + ABSA labeling
    According to PIPELINE.md Section 2.3
    """
    aspect_list = '\n'.join([
        f"  {i}. {aspect_id}: {desc}"
        for i, (aspect_id, desc) in enumerate(ASPECTS.items())
    ])
    
    return f"""Bạn là chuyên gia phân tích sức khỏe tâm thần.

📝 BÀI VIẾT CẦN PHÂN TÍCH:
"{text[:600]}"

🎯 NHIỆM VỤ:
1. Xác định bài viết có liên quan đến STRESS không?
   - stress: Người viết thể hiện căng thẳng, lo âu, áp lực tâm lý
   - non_stress: Bài viết thông thường, không liên quan stress

2. Nếu là STRESS, xác định các khía cạnh gây stress (có thể nhiều):
{aspect_list}

3. Đánh giá độ tin cậy (confidence: 0.0-1.0):
   - 0.9-1.0: Rất rõ ràng về stress
   - 0.7-0.9: Khá chắc chắn
   - 0.5-0.7: Không chắc lắm
   - <0.5: Rất mơ hồ

📋 TRẢ VỀ JSON (chỉ JSON, không giải thích):
{{"stress_label": "stress"/"non_stress", "aspects": [0,1,2,...], "confidence": 0.85}}

Ví dụ: {{"stress_label": "stress", "aspects": [0,3], "confidence": 0.85}}
Ví dụ: {{"stress_label": "non_stress", "aspects": [], "confidence": 0.9}}
"""


def call_groq_api(prompt, api_key, model="llama-3.1-8b-instant", max_retries=2):
    """
    Call Groq Cloud API with retry logic
    Returns parsed result dict
    """
    client = Groq(api_key=api_key)
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "system",
                    "content": "You are a Vietnamese mental health expert. Always respond in valid JSON format."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.3,
                max_tokens=200,
                timeout=30
            )
            
            output = response.choices[0].message.content.strip()
            
            # Parse JSON (with regex fallback)
            json_match = re.search(r'\{[^}]*"stress_label"[^}]*\}', output, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate & normalize
                stress_label = result.get('stress_label', 'non_stress')
                if stress_label not in ['stress', 'non_stress']:
                    stress_label = 'non_stress'
                
                # Convert aspect indices to IDs
                aspect_indices = result.get('aspects', [])
                aspects = []
                for idx in aspect_indices:
                    if isinstance(idx, int) and 0 <= idx < len(ASPECT_IDS):
                        aspects.append(ASPECT_IDS[idx])
                
                confidence = float(result.get('confidence', 0.5))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                
                return {
                    'stress_label': stress_label,
                    'aspect_labels': aspects,
                    'confidence_score': round(confidence, 3)
                }
            else:
                # JSON parse failed
                if attempt < max_retries:
                    continue
                else:
                    return default_label()
                    
        except Exception as e:
            if attempt < max_retries:
                print(f"  ⚠️ Retry {attempt+1}/{max_retries}: {e}")
                continue
            else:
                print(f"  ❌ Failed after {max_retries} retries: {e}")
                return default_label()
    
    return default_label()


def default_label():
    """Default label when API fails"""
    return {
        'stress_label': 'non_stress',
        'aspect_labels': [],
        'confidence_score': 0.0
    }


def label_post_with_groq(post, api_key):
    """
    Label a single post according to PIPELINE.md Section 6.2 Dataset Structure
    
    Output fields:
    - post_id, forum_id, timestamp, raw_text, clean_text (from preprocessing)
    - stress_label (stress/non_stress)
    - aspect_labels (list of aspect IDs)
    - confidence_score (0.0-1.0)
    - label_source (groq)
    - gender, age_group, occupation (from preprocessing)
    - labeled_at (timestamp)
    """
    text = post.get('clean_text', '')
    
    # Call Groq API
    prompt = create_stress_prompt(text)
    result = call_groq_api(prompt, api_key)
    
    # Build output according to PIPELINE.md Section 6.2
    labeled = {
        # Original fields from preprocessing (Task 2.2)
        'post_id': post.get('post_id'),
        'forum': post.get('forum'),  # Note: PIPELINE uses forum_id but data has forum
        'timestamp': post.get('timestamp'),
        'raw_text': post.get('raw_text'),
        'clean_text': post.get('clean_text'),
        'url': post.get('url'),
        'author': post.get('author'),
        
        # Labeling results (Task 2.3)
        'stress_label': result['stress_label'],
        'aspect_labels': result['aspect_labels'],
        'confidence_score': result['confidence_score'],
        'label_source': 'groq',
        
        # Metadata from preprocessing
        'gender': post.get('gender', 'unknown'),
        'age_group': post.get('age_group', 'unknown'),
        'occupation': post.get('occupation', 'unknown'),
        
        # Timestamps
        'collected_at': post.get('collected_at'),
        'labeled_at': datetime.now().isoformat()
    }
    
    return labeled

def main():
    """
    Main labeling pipeline for Task 2.3
    """
    print("="*70)
    print("TASK 2.3: INITIAL WEAK LABELING WITH GROQ CLOUD")
    print("="*70)
    
    # Check API key
    api_key = os.getenv('GROQ_API_KEY', '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')
    if not api_key or api_key.startswith('your-'):
        print("\n⚠️  GROQ_API_KEY not configured!")
        print("\n1. Get FREE API key: https://console.groq.com/keys")
        print("2. Set environment variable:")
        print("   PowerShell: $env:GROQ_API_KEY='gsk_...'")
        print("   Bash:       export GROQ_API_KEY='gsk_...'")
        print("3. Run script again")
        return 1
    
    print(f"✓ API Key configured: {api_key[:20]}...")
    
    # Load preprocessed data
    input_file = Path('data/voz_preprocessed.json')
    if not input_file.exists():
        print(f"\n❌ Input file not found: {input_file}")
        print("   Please run Task 2.2 (preprocessing) first!")
        return 1
    
    print(f"\n📂 Loading: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    print(f"✓ Loaded {len(posts):,} posts")
    
    # Model info
    print("\n🤖 MODEL: Groq Llama-3.1-8B-Instant")
    print(f"   Speed: ~500 tokens/s (~0.5s per post)")
    print(f"   Free tier: 14,400 requests/day")
    print(f"   Estimated time: ~{len(posts) * 0.5 / 60:.1f} minutes")
    
    # Confirm
    print(f"\n🎯 Will label {len(posts):,} posts with:")
    print(f"   - Stress classification (stress/non_stress)")
    print(f"   - 6 ABSA aspects: {', '.join(ASPECT_IDS)}")
    print(f"   - Confidence score (0.0-1.0)")
    
    print(f"\n⏳ Starting labeling process...")
    
    # Label all posts
    print(f"\n{'='*70}")
    print("LABELING IN PROGRESS")
    print(f"{'='*70}\n")
    
    labeled_posts = []
    for post in tqdm(posts, desc="🏷️  Labeling", unit="post"):
        labeled = label_post_with_groq(post, api_key)
        labeled_posts.append(labeled)
    
    # Split by confidence (PIPELINE.md Section 2.3)
    high_conf = [p for p in labeled_posts if p['confidence_score'] >= 0.7]
    low_conf = [p for p in labeled_posts if p['confidence_score'] < 0.7]
    
    # Count stress posts
    stress_posts = [p for p in labeled_posts if p['stress_label'] == 'stress']
    
    # Count aspects
    aspect_counts = {aspect: 0 for aspect in ASPECT_IDS}
    for post in stress_posts:
        for aspect in post['aspect_labels']:
            aspect_counts[aspect] += 1
    
    # Save output (PIPELINE.md Section 2.3)
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
    
    high_conf_file = output_dir / 'voz_labeled_high_confidence.json'
    low_conf_file = output_dir / 'voz_labeled_low_confidence.json'
    
    with open(high_conf_file, 'w', encoding='utf-8') as f:
        json.dump(high_conf, f, ensure_ascii=False, indent=2)
    
    with open(low_conf_file, 'w', encoding='utf-8') as f:
        json.dump(low_conf, f, ensure_ascii=False, indent=2)
    
    # Print results
    print(f"\n{'='*70}")
    print("✅ LABELING COMPLETE")
    print(f"{'='*70}")
    
    print(f"\n📊 STATISTICS:")
    print(f"   Total posts:      {len(labeled_posts):,}")
    print(f"   Stress posts:     {len(stress_posts):,} ({len(stress_posts)/len(labeled_posts)*100:.1f}%)")
    print(f"   Non-stress:       {len(labeled_posts)-len(stress_posts):,} ({(len(labeled_posts)-len(stress_posts))/len(labeled_posts)*100:.1f}%)")
    
    print(f"\n🎯 ASPECT DISTRIBUTION (stress posts only):")
    for aspect, count in aspect_counts.items():
        pct = count / len(stress_posts) * 100 if stress_posts else 0
        print(f"   {aspect:20s}: {count:4d} ({pct:5.1f}%)")
    
    print(f"\n📈 CONFIDENCE SPLIT (PIPELINE.md Section 2.3):")
    print(f"   High-confidence (≥0.7): {len(high_conf):,} ({len(high_conf)/len(labeled_posts)*100:.1f}%)")
    print(f"   Low-confidence  (<0.7): {len(low_conf):,} ({len(low_conf)/len(labeled_posts)*100:.1f}%)")
    
    print(f"\n💾 OUTPUT FILES:")
    print(f"   {high_conf_file}")
    print(f"   {low_conf_file}")
    
    print(f"\n🎉 NEXT STEP: Task 2.4 - Train Student Model")
    print(f"   Use high-confidence set ({len(high_conf):,} posts) for training")
    print(f"   Low-confidence set will be relabeled in Task 2.5 (Teacher-Student Consensus)")
    
    return 0


if __name__ == '__main__':
    exit(main())
