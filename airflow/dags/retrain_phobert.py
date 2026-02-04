"""
Airflow DAG: Retrain PhoBERT with Low-Confidence Posts

Queries low-confidence predictions from Cassandra, relabels them using
Qwen3:14B for higher accuracy, and incrementally retrains PhoBERT.

Schedule: Daily at 2 AM
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import json
import os
import requests

# Configuration
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'cassandra')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'host.docker.internal:11434')
CONFIDENCE_THRESHOLD = 0.5
POST_LIMIT = 10  # Demo: reduced from 100

ASPECT_NAMES = [
    "work_stress", "financial_anxiety", "relationship_issues",
    "academic_pressure", "exhaustion", "depression",
    "loneliness", "health_concerns", "family_conflict", "future_uncertainty"
]

default_args = {
    'owner': 'stress-detection',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def query_low_confidence_posts(**context):
    """Query posts with confidence < 0.5 from Cassandra."""
    from cassandra.cluster import Cluster

    cluster = Cluster([CASSANDRA_HOST])
    session = cluster.connect('reddit_rt')

    # First, get all available hour_buckets
    buckets_query = "SELECT DISTINCT hour_bucket FROM voz_classified_posts"
    bucket_rows = session.execute(buckets_query)
    hour_buckets = [row.hour_bucket for row in bucket_rows]
    print(f"Found {len(hour_buckets)} hour buckets: {hour_buckets}")

    posts = []
    for bucket in hour_buckets:
        if len(posts) >= POST_LIMIT * 2:  # Get extra for filtering
            break

        query = """
            SELECT post_id, text, aspects, aspect_probs, confidence, stress_label, classified_at
            FROM voz_classified_posts
            WHERE hour_bucket = %s
        """
        rows = session.execute(query, [bucket])

        for row in rows:
            conf = row.confidence if row.confidence else 0
            # Include posts with low confidence OR zero confidence (failed inference)
            if conf < CONFIDENCE_THRESHOLD:
                posts.append({
                    'post_id': row.post_id,
                    'text': row.text,
                    'original_aspects': list(row.aspects) if row.aspects else [],
                    'original_confidence': float(conf),
                    'original_stress_label': row.stress_label,
                    'classified_at': row.classified_at.isoformat() if row.classified_at else None
                })

    # Sort by confidence (lowest first) and take top N
    posts.sort(key=lambda x: x['original_confidence'])
    posts = posts[:POST_LIMIT]

    output_path = '/tmp/low_confidence_posts.jsonl'
    with open(output_path, 'w', encoding='utf-8') as f:
        for post in posts:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    cluster.shutdown()
    print(f"Exported {len(posts)} low-confidence posts to {output_path}")
    return len(posts)


def relabel_with_qwen(**context):
    """Relabel posts using Qwen3:14B for higher accuracy."""

    prompt_template = '''Analyze this Vietnamese social media post for stress indicators.

Post: "{text}"

Classify into these 10 stress aspects (output 1 if present, 0 if not):
0. work_stress - Job pressure, deadlines, workplace conflict
1. financial_anxiety - Money problems, debt, expenses
2. relationship_issues - Dating problems, breakups, partner conflict
3. academic_pressure - Exams, grades, school stress
4. exhaustion - Tiredness, burnout, overwhelmed
5. depression - Sadness, hopelessness, lack of motivation
6. loneliness - Isolation, no friends, feeling alone
7. health_concerns - Physical/mental health worries
8. family_conflict - Family arguments, pressure from parents
9. future_uncertainty - Career anxiety, life direction

Return ONLY valid JSON:
{{"aspects": [0,0,0,0,0,0,0,0,0,0], "stress_label": true/false, "confidence": 0.0-1.0}}

Rules:
- aspects array must have exactly 10 integers (0 or 1)
- stress_label is true if ANY aspect is 1
- confidence is your certainty (0.0 to 1.0)
- Only mark aspects with CLEAR evidence in the text
'''

    input_path = '/tmp/low_confidence_posts.jsonl'
    output_path = '/tmp/relabeled_posts.jsonl'

    with open(input_path, 'r', encoding='utf-8') as f:
        posts = [json.loads(line) for line in f]

    if not posts:
        print("No posts to relabel")
        return 0

    results = []
    success_count = 0

    for i, post in enumerate(posts):
        print(f"Relabeling {i+1}/{len(posts)}: {post['post_id']}")

        prompt = prompt_template.format(text=post['text'][:800])

        try:
            response = requests.post(
                f"http://{OLLAMA_HOST}/api/generate",
                json={
                    "model": "qwen3:14b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512}
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json().get("response", "")

                # Handle Qwen3 thinking tags
                if "</think>" in result:
                    result = result.split("</think>")[-1]

                # Parse JSON
                start = result.rfind("{")
                end = result.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(result[start:end])

                    aspects = data.get("aspects", [0]*10)
                    if len(aspects) != 10:
                        aspects = [0]*10

                    post['new_aspects'] = [i for i, v in enumerate(aspects) if v == 1]
                    post['new_stress_label'] = data.get("stress_label", len(post['new_aspects']) > 0)
                    post['new_confidence'] = min(max(data.get("confidence", 0.8), 0.0), 1.0)
                    post['relabel_model'] = 'qwen3:14b'

                    results.append(post)
                    success_count += 1
                    print(f"  -> Aspects: {post['new_aspects']}, Confidence: {post['new_confidence']:.2f}")
                    continue

        except Exception as e:
            print(f"  -> Error: {e}")

        # Fallback: keep original
        post['new_aspects'] = post['original_aspects']
        post['new_stress_label'] = post['original_stress_label']
        post['new_confidence'] = post['original_confidence']
        post['relabel_model'] = 'fallback'
        results.append(post)

    with open(output_path, 'w', encoding='utf-8') as f:
        for post in results:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    print(f"Successfully relabeled {success_count}/{len(results)} posts with Qwen3:14B")
    return success_count


def validate_labels(**context):
    """Validate relabeled data and convert to training format."""

    input_path = '/tmp/relabeled_posts.jsonl'
    output_path = '/tmp/validated_training_data.jsonl'

    with open(input_path, 'r', encoding='utf-8') as f:
        posts = [json.loads(line) for line in f]

    valid_posts = []
    for post in posts:
        # Skip if relabeling failed
        if post.get('relabel_model') == 'fallback':
            continue

        # Validate aspects
        aspects = post.get('new_aspects', [])
        if not isinstance(aspects, list):
            continue

        # Convert to training format
        training_sample = {
            'post_id': post['post_id'],
            'text': post['text'],
            'aspects': aspects,
            'stress_label': post.get('new_stress_label', len(aspects) > 0),
            'confidence': post.get('new_confidence', 0.8),
            'source': 'airflow_retrain',
            'relabel_model': post.get('relabel_model'),
            'original_confidence': post.get('original_confidence')
        }
        valid_posts.append(training_sample)

    with open(output_path, 'w', encoding='utf-8') as f:
        for post in valid_posts:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    print(f"Validated {len(valid_posts)} posts for training")
    return len(valid_posts)


def merge_training_data(**context):
    """Merge new relabeled data with existing training data."""

    new_data_path = '/tmp/validated_training_data.jsonl'
    existing_data_path = '/opt/data/splits/train_v1.jsonl'
    output_path = '/opt/data/splits/train_incremental.jsonl'

    # Load new data
    with open(new_data_path, 'r', encoding='utf-8') as f:
        new_posts = [json.loads(line) for line in f]

    # Load existing data if exists
    existing_posts = []
    if os.path.exists(existing_data_path):
        with open(existing_data_path, 'r', encoding='utf-8') as f:
            existing_posts = [json.loads(line) for line in f]

    # Merge (deduplicate by post_id)
    existing_ids = {p['post_id'] for p in existing_posts}
    merged = existing_posts + [p for p in new_posts if p['post_id'] not in existing_ids]

    with open(output_path, 'w', encoding='utf-8') as f:
        for post in merged:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    print(f"Merged data: {len(existing_posts)} existing + {len(new_posts)} new = {len(merged)} total")
    return len(merged)


def hot_swap_model(**context):
    """Swap new model into production."""
    import shutil

    new_model = '/opt/ml/exports/phobert_stress_new.onnx'
    backup_model = '/opt/ml/exports/phobert_stress_backup.onnx'
    prod_model = '/opt/ml/exports/phobert_stress.onnx'

    if not os.path.exists(new_model):
        print("New model not found, skipping swap")
        return False

    # Backup current model
    if os.path.exists(prod_model):
        shutil.copy2(prod_model, backup_model)
        print(f"Backed up current model to {backup_model}")

    # Swap models
    shutil.move(new_model, prod_model)
    print(f"Swapped new model to production: {prod_model}")

    return True


# Create DAG
dag = DAG(
    'retrain_phobert',
    default_args=default_args,
    description='Retrain PhoBERT with low-confidence posts relabeled by Qwen3:14B',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    max_active_runs=1,
    tags=['ml', 'retraining', 'stress-detection'],
)

# Task 1: Query low-confidence posts from Cassandra
query_task = PythonOperator(
    task_id='query_low_confidence',
    python_callable=query_low_confidence_posts,
    dag=dag,
)

# Task 2: Relabel with Qwen3:14B
relabel_task = PythonOperator(
    task_id='relabel_with_qwen14b',
    python_callable=relabel_with_qwen,
    execution_timeout=timedelta(hours=2),  # Allow up to 2 hours
    dag=dag,
)

# Task 3: Validate labels
validate_task = PythonOperator(
    task_id='validate_labels',
    python_callable=validate_labels,
    dag=dag,
)

# Task 4: Merge with existing training data
merge_task = PythonOperator(
    task_id='merge_training_data',
    python_callable=merge_training_data,
    dag=dag,
)

# Task 5: Retrain PhoBERT (optional - runs only if torch is available)
retrain_task = BashOperator(
    task_id='retrain_phobert',
    bash_command='''
        if python -c "import torch" 2>/dev/null; then
            if [ -f /opt/ml/training/train_phobert.py ]; then
                cd /opt/ml && python training/train_phobert.py \
                    --train_file /opt/data/splits/train_incremental.jsonl \
                    --epochs 3 \
                    --output_dir /opt/ml/checkpoints/phobert_incremental
            else
                echo "Training script not found, skipping"
            fi
        else
            echo "PyTorch not installed in Airflow container - run training manually:"
            echo "  python ml/training/train_phobert.py --train_file data/splits/train_incremental.jsonl"
        fi
    ''',
    dag=dag,
)

# Task 6: Export to ONNX
export_task = BashOperator(
    task_id='export_onnx',
    bash_command='''
        if [ -d /opt/ml/checkpoints/phobert_incremental ] && [ -f /opt/ml/training/export_onnx.py ]; then
            if python -c "import torch" 2>/dev/null; then
                cd /opt/ml && python training/export_onnx.py \
                    --checkpoint /opt/ml/checkpoints/phobert_incremental \
                    --output /opt/ml/exports/phobert_stress_new.onnx
            else
                echo "PyTorch not available - run export manually"
            fi
        else
            echo "No new checkpoint to export, skipping"
        fi
    ''',
    dag=dag,
)

# Task 7: Hot-swap model
swap_task = PythonOperator(
    task_id='hot_swap_model',
    python_callable=hot_swap_model,
    dag=dag,
)

# Define task dependencies
query_task >> relabel_task >> validate_task >> merge_task >> retrain_task >> export_task >> swap_task
