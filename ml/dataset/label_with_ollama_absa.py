#!/usr/bin/env python3
"""
Label 1095 Cassandra Posts with 10 ABSA Aspects using Ollama
Fully automated multi-label classification
"""

import json
import csv
from pathlib import Path
from cassandra.cluster import Cluster
import subprocess
import re
from tqdm import tqdm

# Load ABSA aspects
def load_absa_aspects():
    """Load Vietnamese ABSA aspects"""
    with open('ml/lda/absa_mental_health_aspects.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['aspects']

def fetch_posts_from_cassandra():
    """Fetch all 1095 vozforums posts"""
    print("Connecting to Cassandra...")
    cluster = Cluster(['localhost'], port=9042)
    session = cluster.connect('reddit_rt')

    query = "SELECT post_id, title, body FROM raw_posts_by_day WHERE subreddit='vozforums' ALLOW FILTERING;"
    rows = session.execute(query)

    posts = []
    for row in rows:
        text = ''
        if row.title:
            text += row.title + ' '
        if row.body:
            text += row.body

        if text.strip():
            posts.append({
                'post_id': row.post_id,
                'text': text.strip()
            })

    cluster.shutdown()
    print(f"✓ Fetched {len(posts)} posts from Cassandra")
    return posts

def create_ollama_prompt(text, aspects):
    """Create Vietnamese ABSA labeling prompt for Ollama"""

    # Build aspect list
    aspect_list = []
    for asp in aspects:
        aspect_list.append(
            f"{asp['id']}. {asp['aspect_name']} - {asp['mental_health_relevance']}"
        )

    prompt = f"""Bạn là chuyên gia phân tích sức khỏe tâm thần. Phân tích bài viết Reddit sau và xác định TẤT CẢ các khía cạnh sức khỏe tâm thần có trong bài.

BÀI VIẾT:
\"\"\"{text[:500]}\"\"\"

CÁC KHÍA CẠNH SỨC KHỎE TÂM THẦN (chọn tất cả phù hợp):
{chr(10).join(aspect_list)}

HƯỚNG DẪN:
- Một bài viết có thể có NHIỀU khía cạnh (multi-label)
- Chỉ chọn khía cạnh NẾU bài viết đề cập rõ ràng
- Trả về danh sách số (ví dụ: [0,2,7] nếu có công việc, giao tiếp, trầm cảm)

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON:
{{"aspects": [list các số], "confidence": 0.0-1.0}}

Chỉ trả về JSON, không giải thích thêm."""

    return prompt

def call_ollama(prompt, model="llama3.1:8b"):
    """Call Ollama API for labeling"""
    try:
        result = subprocess.run(
            ['ollama', 'run', model],
            input=prompt.encode('utf-8'),
            capture_output=True,
            timeout=30
        )

        output = result.stdout.decode('utf-8').strip()

        # Try to extract JSON from response
        # Look for JSON pattern (most lenient match)
        json_match = re.search(r'\{[^}]*"aspects"[^}]*\}', output, re.DOTALL)
        if json_match:
            response = json.loads(json_match.group())
            return response

        # Fallback: try to parse entire output
        try:
            return json.loads(output)
        except:
            pass

        # Last resort: extract array pattern [0,1,2]
        array_match = re.search(r'\[[\d,\s]+\]', output)
        if array_match:
            aspects = json.loads(array_match.group())
            return {"aspects": aspects, "confidence": 0.5}

        # Give up - return empty
        return {"aspects": [], "confidence": 0.0}

    except subprocess.TimeoutExpired:
        return {"aspects": [], "confidence": 0.0}
    except json.JSONDecodeError:
        return {"aspects": [], "confidence": 0.0}
    except Exception as e:
        return {"aspects": [], "confidence": 0.0}

def label_posts(posts, aspects):
    """Label all posts using Ollama"""
    labeled_data = []

    print(f"\nLabeling {len(posts)} posts with Ollama...")
    print("This may take 30-60 minutes...\n")

    for post in tqdm(posts, desc="Labeling posts"):
        # Create prompt
        prompt = create_ollama_prompt(post['text'], aspects)

        # Get Ollama prediction
        prediction = call_ollama(prompt)

        # Create label vector (10-dimensional binary vector)
        label_vector = [0] * 10
        for raw_aspect_id in prediction.get('aspects', []):
            try:
                # Convert to int (Ollama sometimes returns strings)
                aspect_id = int(raw_aspect_id)
                if 0 <= aspect_id < 10:
                    label_vector[aspect_id] = 1
            except (ValueError, TypeError):
                # Skip invalid aspect IDs
                continue

        labeled_data.append({
            'post_id': post['post_id'],
            'text': post['text'],
            'label_vector': label_vector,
            'aspects_detected': prediction.get('aspects', []),
            'confidence': prediction.get('confidence', 0.5)
        })

    return labeled_data

def save_labeled_data(labeled_data, output_file='ml/dataset/labeled/vozforums_absa_labeled.csv'):
    """Save labeled data to CSV"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'post_id',
            'text',
            'label_0_công_việc',
            'label_1_giấc_ngủ_thuốc',
            'label_2_giao_tiếp',
            'label_3_thiếu_năng_lượng',
            'label_4_căng_thẳng_tài_chính',
            'label_5_tình_yêu',
            'label_6_tự_suy_ngẫm',
            'label_7_trầm_cảm',
            'label_8_gia_đình',
            'label_9_tìm_kiếm_giúp_đỡ',
            'aspects_detected',
            'confidence'
        ])

        # Data rows
        for item in labeled_data:
            writer.writerow([
                item['post_id'],
                item['text'],
                *item['label_vector'],
                ','.join(map(str, item['aspects_detected'])),
                item['confidence']
            ])

    print(f"\n✓ Saved labeled data to {output_file}")
    return output_path

def print_statistics(labeled_data, aspects):
    """Print labeling statistics"""
    print("\n" + "="*70)
    print("LABELING STATISTICS")
    print("="*70)

    total_posts = len(labeled_data)
    print(f"\nTotal posts labeled: {total_posts}")

    # Count per aspect
    print("\nAspect Distribution:")
    for i, aspect in enumerate(aspects):
        count = sum(1 for item in labeled_data if item['label_vector'][i] == 1)
        percentage = (count / total_posts) * 100
        print(f"  {i}. {aspect['aspect_name']:<25} {count:>4} posts ({percentage:>5.1f}%)")

    # Multi-label stats
    labels_per_post = [sum(item['label_vector']) for item in labeled_data]
    avg_labels = sum(labels_per_post) / len(labels_per_post)
    print(f"\nAverage aspects per post: {avg_labels:.2f}")

    # Confidence stats
    confidences = [item['confidence'] for item in labeled_data]
    avg_confidence = sum(confidences) / len(confidences)
    print(f"Average confidence: {avg_confidence:.2f}")

    # Low confidence posts (need validation)
    low_conf_threshold = 0.7
    low_conf_count = sum(1 for c in confidences if c < low_conf_threshold)
    print(f"Low confidence posts (<{low_conf_threshold}): {low_conf_count} ({(low_conf_count/total_posts)*100:.1f}%)")

def main():
    print("="*70)
    print("ABSA LABELING WITH OLLAMA")
    print("="*70)
    print("\nPhase 2: Labeling 1095 vozforums posts with 10 ABSA aspects")
    print("Model: Ollama llama3.1:8b")
    print()

    # Load aspects
    print("Loading ABSA aspects...")
    aspects = load_absa_aspects()
    print(f"✓ Loaded {len(aspects)} ABSA aspects")

    # Fetch posts
    posts = fetch_posts_from_cassandra()

    # Label posts
    labeled_data = label_posts(posts, aspects)

    # Save results
    output_file = save_labeled_data(labeled_data)

    # Print statistics
    print_statistics(labeled_data, aspects)

    print("\n" + "="*70)
    print("✓ LABELING COMPLETE")
    print("="*70)
    print(f"\nOutput: {output_file}")
    print("\nNext steps:")
    print("  1. Review labeled data (especially low-confidence posts)")
    print("  2. Train PhoBERT: python ml/models/train_absa_phobert.py")
    print("  3. Set up Airflow retraining pipeline")

if __name__ == "__main__":
    main()
