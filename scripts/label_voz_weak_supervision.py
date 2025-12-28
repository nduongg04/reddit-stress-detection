#!/usr/bin/env python3
"""
⚠️ DEPRECATED - DO NOT USE ⚠️

Task 2.3: Initial Weak Labeling with Ollama (DEPRECATED)

This script was replaced by label_with_groq.py due to performance issues:
- Ollama local: 66 seconds/post = 86 hours for 5k posts
- Groq Cloud: 0.5 seconds/post = 40 minutes for 5k posts

USE INSTEAD: scripts/label_with_groq.py

Reason for deprecation:
- Too slow for production use (86 hours vs 40 minutes)
- Memory issues with Docker WSL2 backend
- Groq Cloud API is FREE and much faster

Date deprecated: 2025-12-20
"""

# This file is kept for reference only
# DO NOT RUN THIS SCRIPT

import sys
print("="*70)
print("⚠️  ERROR: This script is DEPRECATED")
print("="*70)
print("\nOllama local LLM is too slow:")
print("  - 66 seconds per post")
print("  - 86 hours for 5,000 posts")
print("\n✅ USE INSTEAD:")
print("  python scripts/label_with_groq.py")
print("\nGroq Cloud API is:")
print("  - FREE (14,400 requests/day)")
print("  - FAST (0.5s per post = 40 minutes total)")
print("  - Same Llama-3.1-8B model")
print("="*70)
sys.exit(1)

# Original code preserved below for reference
# ============================================
"""
Labels VOZ preprocessed posts with:
- Binary stress classification (stress/non_stress)
- Multi-label aspect classification (6 aspects)
- Confidence score
"""

import json
import requests
import re
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

# 6 ABSA Aspects from PIPELINE.md
ASPECTS = {
    'work_pressure': 'Áp lực công việc, deadline, khối lượng công việc',
    'relationship': 'Vấn đề tình cảm, chia tay, tranh cãi với người yêu',
    'financial': 'Khó khăn tài chính, nợ nần, thiếu tiền',
    'study': 'Áp lực học tập, thi cử, điểm số, kỳ thi',
    'family_social': 'Xung đột gia đình, áp lực xã hội, bạn bè',
    'health': 'Vấn đề sức khỏe thể chất hoặc tâm thần'
}

ASPECT_IDS = list(ASPECTS.keys())

def load_preprocessed_data(file_path='data/voz_preprocessed.json'):
    """Load preprocessed VOZ data"""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--input':
        file_path = sys.argv[2]
    
    print(f"Loading preprocessed data from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        posts = json.load(f)
    print(f"✓ Loaded {len(posts)} posts")
    return posts

def create_stress_prompt(text):
    """Create prompt for binary stress classification"""
    
    prompt = f"""Bạn là chuyên gia phân tích sức khỏe tâm thần. Phân tích bài viết sau và xác định người viết có đang bị stress không.

BÀI VIẾT:
\"\"\"{text[:600]}\"\"\"

DẤU HIỆU STRESS:
- Cảm giác áp lực, căng thẳng, lo lắng
- Bế tắc, mệt mỏi, kiệt sức
- Khó chịu, bực bội, cáu gắt
- Mất ngủ, ăn không ngon
- Cảm giác tuyệt vọng, bất lực

HƯỚNG DẪN:
- "stress": bài viết thể hiện rõ dấu hiệu stress
- "non_stress": bài viết bình thường, không có dấu hiệu stress

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (chỉ JSON, không giải thích):
{{"stress_label": "stress" hoặc "non_stress", "confidence": 0.0-1.0}}
"""
    return prompt

def create_aspect_prompt(text):
    """Create prompt for multi-label aspect classification"""
    
    aspect_list = []
    for i, (aspect_id, description) in enumerate(ASPECTS.items()):
        aspect_list.append(f"{i}. {aspect_id}: {description}")
    
    prompt = f"""Bạn là chuyên gia phân tích sức khỏe tâm thần. Phân tích bài viết sau và xác định TẤT CẢ các khía cạnh stress có trong bài.

BÀI VIẾT:
\"\"\"{text[:600]}\"\"\"

CÁC KHÍA CẠNH STRESS (chọn tất cả phù hợp):
{chr(10).join(aspect_list)}

HƯỚNG DẪN:
- Một bài viết có thể có NHIỀU khía cạnh (multi-label)
- Chỉ chọn khía cạnh NẾU bài viết đề cập rõ ràng
- Trả về danh sách số từ 0-5 (ví dụ: [0,2] nếu có work_pressure và financial)

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (chỉ JSON, không giải thích):
{{"aspects": [list các số từ 0-5], "confidence": 0.0-1.0}}
"""
    return prompt

def call_ollama(prompt, model="llama3.2:3b", max_retries=2):
    """Call Ollama HTTP API for labeling"""
    url = "http://localhost:11434/api/generate"
    
    for attempt in range(max_retries):
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            output = result.get('response', '').strip()
            
            # Try to extract JSON from response
            # Look for JSON pattern with quotes
            json_match = re.search(r'\{[^}]*["\'](?:stress_label|aspects)["\'][^}]*\}', output, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # Try to parse entire output
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                pass
            
            # Retry on first failure
            if attempt < max_retries - 1:
                continue
                
            # Last resort: return default values
            return None
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return None
    
    return None

def create_combined_prompt(text):
    """Create single prompt for both stress and aspect classification"""
    aspect_list = []
    for i, (aspect_id, description) in enumerate(ASPECTS.items()):
        aspect_list.append(f"{i}. {aspect_id}: {description}")
    
    prompt = f"""Bạn là chuyên gia phân tích sức khỏe tâm thần. Phân tích bài viết sau:

BÀI VIẾT:
\"\"\"{text[:600]}\"\"\"

NHIỆM VỤ:
1. Xác định người viết có đang stress không (stress/non_stress)
2. NẾU stress, chọn TẤT CẢ khía cạnh liên quan:
{chr(10).join(aspect_list)}

DẤU HIỆU STRESS: áp lực, lo lắng, bế tắc, mệt mỏi, khó chịu, tuyệt vọng

TRẢ VỀ JSON (chỉ JSON, không giải thích):
{{"stress_label": "stress" hoặc "non_stress", "aspects": [list số 0-5 nếu stress, [] nếu non-stress], "confidence": 0.0-1.0}}

Ví dụ stress: {{"stress_label": "stress", "aspects": [0,3], "confidence": 0.85}}
Ví dụ non-stress: {{"stress_label": "non_stress", "aspects": [], "confidence": 0.9}}
"""
    return prompt

def label_post(post):
    """Label a single post with combined stress + aspect classification"""
    text = post['clean_text']
    
    # Single call with combined prompt
    combined_prompt = create_combined_prompt(text)
    result = call_ollama(combined_prompt)
    
    if result is None:
        # Default to non_stress if Ollama fails
        stress_label = 'non_stress'
        aspect_labels = []
        overall_confidence = 0.0
    else:
        stress_label = result.get('stress_label', 'non_stress')
        raw_aspects = result.get('aspects', [])
        overall_confidence = result.get('confidence', 0.5)
        
        # Convert to aspect IDs
        aspect_labels = []
        for aspect_idx in raw_aspects:
            try:
                idx = int(aspect_idx)
                if 0 <= idx < 6:
                    aspect_labels.append(ASPECT_IDS[idx])
            except (ValueError, TypeError):
                continue
    
    return {
        'post_id': post['post_id'],
        'forum': post['forum'],
        'clean_text': text,
        'raw_text': post.get('raw_text', ''),
        'url': post.get('url', ''),
        'author': post.get('author', ''),
        'gender': post.get('gender', 'unknown'),
        'age_group': post.get('age_group', 'unknown'),
        'occupation': post.get('occupation', 'unknown'),
        'stress_label': stress_label,
        'aspect_labels': aspect_labels,
        'confidence_score': round(overall_confidence, 3),
        'label_source': 'ollama',
        'labeled_at': datetime.now().isoformat()
    }

def label_all_posts(posts):
    """Label all posts with progress bar"""
    labeled_posts = []
    
    print(f"\n{'='*70}")
    print("WEAK LABELING WITH OLLAMA (Task 2.3)")
    print(f"{'='*70}\n")
    print(f"Total posts: {len(posts)}")
    print(f"Model: llama3.2:3b (optimized: 1 call per post)")
    print(f"Estimated time: {len(posts) * 4 / 3600:.1f} hours (~{len(posts) * 4 / 60:.0f} minutes)")
    print(f"\nStarting labeling...\n")
    
    for post in tqdm(posts, desc="Labeling posts"):
        labeled_post = label_post(post)
        labeled_posts.append(labeled_post)
    
    return labeled_posts

def split_by_confidence(labeled_posts, threshold=0.7):
    """Split posts into high-confidence and low-confidence sets"""
    high_confidence = []
    low_confidence = []
    
    for post in labeled_posts:
        if post['confidence_score'] >= threshold:
            high_confidence.append(post)
        else:
            low_confidence.append(post)
    
    return high_confidence, low_confidence

def save_labeled_data(high_conf, low_conf):
    """Save labeled data to JSON files"""
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
    
    # Save high-confidence
    high_conf_file = output_dir / 'voz_labeled_high_confidence.json'
    with open(high_conf_file, 'w', encoding='utf-8') as f:
        json.dump(high_conf, f, ensure_ascii=False, indent=2)
    
    # Save low-confidence
    low_conf_file = output_dir / 'voz_labeled_low_confidence.json'
    with open(low_conf_file, 'w', encoding='utf-8') as f:
        json.dump(low_conf, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*70}")
    print("OUTPUT FILES")
    print(f"{'='*70}")
    print(f"✓ High-confidence (≥0.7): {high_conf_file} ({len(high_conf)} posts)")
    print(f"✓ Low-confidence (<0.7): {low_conf_file} ({len(low_conf)} posts)")
    
    return high_conf_file, low_conf_file

def print_statistics(labeled_posts, high_conf, low_conf):
    """Print labeling statistics"""
    total = len(labeled_posts)
    stress_count = sum(1 for p in labeled_posts if p['stress_label'] == 'stress')
    
    # Aspect statistics
    aspect_counts = {aspect: 0 for aspect in ASPECT_IDS}
    for post in labeled_posts:
        for aspect in post['aspect_labels']:
            aspect_counts[aspect] += 1
    
    print(f"\n{'='*70}")
    print("LABELING STATISTICS")
    print(f"{'='*70}\n")
    print(f"Total posts: {total}")
    print(f"Stress posts: {stress_count} ({stress_count/total*100:.1f}%)")
    print(f"Non-stress posts: {total-stress_count} ({(total-stress_count)/total*100:.1f}%)")
    print(f"\nAspect distribution (stress posts only):")
    for aspect_id in ASPECT_IDS:
        count = aspect_counts[aspect_id]
        pct = count / stress_count * 100 if stress_count > 0 else 0
        print(f"  {aspect_id}: {count} ({pct:.1f}%)")
    
    print(f"\nConfidence split:")
    print(f"  High-confidence (≥0.7): {len(high_conf)} ({len(high_conf)/total*100:.1f}%)")
    print(f"  Low-confidence (<0.7): {len(low_conf)} ({len(low_conf)/total*100:.1f}%)")
    
    avg_confidence = sum(p['confidence_score'] for p in labeled_posts) / total
    print(f"\nAverage confidence: {avg_confidence:.3f}")

def main():
    """Main execution"""
    # Load preprocessed data
    posts = load_preprocessed_data()
    
    # Label all posts
    labeled_posts = label_all_posts(posts)
    
    # Split by confidence
    high_conf, low_conf = split_by_confidence(labeled_posts)
    
    # Save labeled data
    save_labeled_data(high_conf, low_conf)
    
    # Print statistics
    print_statistics(labeled_posts, high_conf, low_conf)
    
    print(f"\n{'='*70}")
    print("✓ TASK 2.3 COMPLETE: Initial Weak Labeling")
    print(f"{'='*70}\n")
    print("Next step: Task 2.4 - Train Student Model on high-confidence set")

if __name__ == '__main__':
    main()
