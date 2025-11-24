"""
Daily Vietnamese ABSA PhoBERT Retraining DAG
Active Learning Pipeline with Ollama Validation

DAG Flow:
1. Fetch real-time Reddit posts from Cassandra (last 24 hours)
2. Run PhoBERT inference to get predictions
3. Calculate prediction uncertainty (entropy-based)
4. Select top-100 most uncertain predictions
5. Validate uncertain predictions with Ollama
6. Combine validated data with existing training set
7. Retrain PhoBERT model with new data
8. Save new model version with metadata
9. Update Spark to use new model version
10. Send metrics to monitoring

Schedule: Daily at 2 AM UTC
Active Learning: Ollama validates uncertain predictions (no human needed)
Model Versioning: Timestamped models with performance tracking
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import json
import os
import sys
import pandas as pd
import numpy as np
import torch
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/opt/airflow/dags')
sys.path.insert(0, '/opt/airflow')

# Default args
default_args = {
    'owner': 'reddit-ml',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'vietnamese_absa_daily_retrain',
    default_args=default_args,
    description='Daily PhoBERT ABSA retraining with active learning',
    schedule_interval='0 2 * * *',  # 2 AM UTC daily
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'vietnamese', 'absa', 'active-learning']
)


def fetch_recent_posts(**context):
    """
    Task 1: Fetch posts from Cassandra (last 24 hours)

    Returns posts that were processed by Spark in the last day
    to be used for active learning selection
    """
    from cassandra.cluster import Cluster

    print("Connecting to Cassandra...")
    cluster = Cluster(['cassandra'], port=9042)  # Docker network
    session = cluster.connect('reddit_rt')

    # Calculate yesterday's date partitions
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    # Fetch posts from last 24 hours
    # Use classified_posts_by_hour table which has model predictions
    query = """
        SELECT post_id, title, body, subreddit,
               stress_score, stress_label, created_utc, hour_partition
        FROM classified_posts_by_hour
        WHERE subreddit = 'vozforums'
          AND hour_partition >= %s
        ALLOW FILTERING;
    """

    partition_start = yesterday.strftime('%Y-%m-%d-%H')
    rows = session.execute(query, [partition_start])

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
                'text': text.strip(),
                'subreddit': row.subreddit,
                'stress_score': float(row.stress_score) if row.stress_score else 0.0,
                'stress_label': bool(row.stress_label) if row.stress_label else False,
                'created_utc': row.created_utc
            })

    cluster.shutdown()

    print(f"✓ Fetched {len(posts)} posts from last 24 hours")

    # Save to XCom
    context['task_instance'].xcom_push(key='recent_posts', value=posts)

    return len(posts)


def run_inference(**context):
    """
    Task 2: Run PhoBERT inference on recent posts

    Returns predictions with probabilities for uncertainty calculation
    """
    from transformers import AutoTokenizer, AutoModel
    from torch import nn

    # Get posts from previous task
    posts = context['task_instance'].xcom_pull(
        task_ids='fetch_recent_posts',
        key='recent_posts'
    )

    if not posts or len(posts) == 0:
        print("No posts to process")
        return 0

    print(f"Running inference on {len(posts)} posts...")

    # Load current model
    model_dir = '/opt/airflow/ml/models/vietnamese_absa_phobert_v1'

    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(model_dir)

    # Reconstruct model architecture
    class PhoBERTMultiLabelClassifier(nn.Module):
        def __init__(self, model_name, num_labels):
            super().__init__()
            self.phobert = AutoModel.from_pretrained(model_name)
            self.dropout = nn.Dropout(0.3)
            self.classifier = nn.Linear(self.phobert.config.hidden_size, num_labels)

        def forward(self, input_ids, attention_mask):
            outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
            pooled_output = outputs.last_hidden_state[:, 0, :]
            pooled_output = self.dropout(pooled_output)
            logits = self.classifier(pooled_output)
            return logits

    model = PhoBERTMultiLabelClassifier('vinai/phobert-base-v2', num_labels=10)
    model.load_state_dict(torch.load(f'{model_dir}/model.pt', map_location='cpu'))
    model.eval()

    # Run inference
    predictions = []
    with torch.no_grad():
        for post in posts:
            encoding = tokenizer(
                post['text'],
                max_length=256,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            logits = model(encoding['input_ids'], encoding['attention_mask'])
            probs = torch.sigmoid(logits).squeeze().numpy()

            predictions.append({
                'post_id': post['post_id'],
                'text': post['text'],
                'probabilities': probs.tolist()
            })

    print(f"✓ Generated {len(predictions)} predictions")

    # Save predictions to XCom
    context['task_instance'].xcom_push(key='predictions', value=predictions)

    return len(predictions)


def select_uncertain_predictions(**context):
    """
    Task 3: Calculate uncertainty and select top-100 uncertain predictions

    Uses entropy-based uncertainty calculation from OllamaValidator
    """
    sys.path.insert(0, '/opt/airflow/utils')
    from ollama_validator import OllamaValidator

    # Get predictions from previous task
    predictions = context['task_instance'].xcom_pull(
        task_ids='run_inference',
        key='predictions'
    )

    if not predictions or len(predictions) == 0:
        print("No predictions to process")
        return 0

    print(f"Selecting uncertain predictions from {len(predictions)} predictions...")

    # Initialize validator
    validator = OllamaValidator(
        aspects_file='/opt/airflow/ml/lda/absa_mental_health_aspects.json',
        uncertainty_threshold=0.5
    )

    # Extract texts and probabilities
    texts = [p['text'] for p in predictions]
    probs = np.array([p['probabilities'] for p in predictions])

    # Select uncertain samples (top 100)
    uncertain_samples = validator.select_uncertain_samples(
        texts, probs, top_n=100
    )

    print(f"✓ Selected {len(uncertain_samples)} uncertain predictions")

    if len(uncertain_samples) > 0:
        avg_uncertainty = np.mean([s['uncertainty'] for s in uncertain_samples])
        print(f"  Average uncertainty: {avg_uncertainty:.3f}")

    # Save to XCom
    context['task_instance'].xcom_push(key='uncertain_samples', value=uncertain_samples)

    return len(uncertain_samples)


def validate_with_ollama(**context):
    """
    Task 4: Validate uncertain predictions with Ollama

    Uses Ollama LLM to re-label uncertain predictions
    No human intervention needed
    """
    sys.path.insert(0, '/opt/airflow/utils')
    from ollama_validator import OllamaValidator

    # Get uncertain samples
    uncertain_samples = context['task_instance'].xcom_pull(
        task_ids='select_uncertain_predictions',
        key='uncertain_samples'
    )

    if not uncertain_samples or len(uncertain_samples) == 0:
        print("No uncertain samples to validate")
        return 0

    print(f"Validating {len(uncertain_samples)} uncertain predictions with Ollama...")

    # Initialize validator
    validator = OllamaValidator(
        aspects_file='/opt/airflow/ml/lda/absa_mental_health_aspects.json',
        model_name='llama3.1:8b',
        uncertainty_threshold=0.5
    )

    # Validate batch
    validated = validator.validate_batch(uncertain_samples, verbose=True)

    print(f"✓ Validated {len(validated)} samples")

    # Statistics
    corrected_count = sum(1 for v in validated if v.get('corrected', False))
    print(f"  Corrected: {corrected_count} ({(corrected_count/len(validated))*100:.1f}%)")

    # Save validated data to CSV
    output_dir = '/opt/airflow/ml/dataset/active_learning'
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'{output_dir}/validated_{timestamp}.csv'

    # Create DataFrame
    rows = []
    for v in validated:
        row = {
            'post_id': f"active_learning_{timestamp}_{v['index']}",
            'text': v['text'],
        }
        # Add label columns
        for i in range(10):
            row[f'label_{i}'] = v['validated_labels'][i]

        row['uncertainty'] = v['uncertainty']
        row['confidence'] = v['confidence']
        row['corrected'] = v['corrected']

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)

    print(f"✓ Saved validated data to {output_file}")

    # Save to XCom
    context['task_instance'].xcom_push(key='validated_file', value=output_file)
    context['task_instance'].xcom_push(key='validated_count', value=len(validated))

    return len(validated)


def retrain_model(**context):
    """
    Task 5: Retrain PhoBERT with original + validated data

    Combines:
    - Original training data (vozforums_absa_labeled.csv)
    - Newly validated data from active learning

    Trains new model version
    """
    from ml.models.train_absa_phobert import train, CONFIG

    # Get validated data file
    validated_file = context['task_instance'].xcom_pull(
        task_ids='validate_with_ollama',
        key='validated_file'
    )

    validated_count = context['task_instance'].xcom_pull(
        task_ids='validate_with_ollama',
        key='validated_count'
    )

    print(f"Retraining model with {validated_count} new samples...")

    # Load original training data
    original_data = pd.read_csv('/opt/airflow/ml/dataset/labeled/vozforums_absa_labeled.csv')
    print(f"Original training data: {len(original_data)} samples")

    # Combine with validated data if available
    if validated_file and os.path.exists(validated_file):
        validated_data = pd.read_csv(validated_file)
        print(f"Validated data: {len(validated_data)} samples")

        # Combine datasets
        combined_data = pd.concat([original_data, validated_data], ignore_index=True)
        print(f"Combined dataset: {len(combined_data)} samples")

        # Save combined dataset
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_file = f'/opt/airflow/ml/dataset/labeled/combined_{timestamp}.csv'
        combined_data.to_csv(combined_file, index=False)

        # Update config to use combined data
        CONFIG['data_file'] = combined_file

    # Create new model version directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_model_dir = f'/opt/airflow/ml/models/vietnamese_absa_phobert_{timestamp}'
    CONFIG['output_dir'] = new_model_dir

    print(f"Training new model version: {new_model_dir}")

    # Train model
    train(CONFIG)

    print(f"✓ Model training complete: {new_model_dir}")

    # Save model metadata
    metadata = {
        'version': timestamp,
        'trained_at': datetime.now().isoformat(),
        'original_samples': len(original_data),
        'validated_samples': validated_count,
        'total_samples': len(original_data) + validated_count,
        'model_dir': new_model_dir,
        'config': CONFIG
    }

    with open(f'{new_model_dir}/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    # Save to XCom
    context['task_instance'].xcom_push(key='model_version', value=timestamp)
    context['task_instance'].xcom_push(key='model_dir', value=new_model_dir)

    return new_model_dir


def update_model_registry(**context):
    """
    Task 6: Update model registry with new version

    Maintains registry of all model versions for tracking and rollback
    """
    model_version = context['task_instance'].xcom_pull(
        task_ids='retrain_model',
        key='model_version'
    )

    model_dir = context['task_instance'].xcom_pull(
        task_ids='retrain_model',
        key='model_dir'
    )

    print(f"Updating model registry with version {model_version}...")

    registry_file = '/opt/airflow/ml/models/registry/registry.json'

    # Load existing registry
    if os.path.exists(registry_file):
        with open(registry_file, 'r') as f:
            registry = json.load(f)
    else:
        registry = {'models': []}

    # Load model metadata
    with open(f'{model_dir}/metadata.json', 'r') as f:
        metadata = json.load(f)

    # Load test metrics
    with open(f'{model_dir}/test_metrics.json', 'r') as f:
        test_metrics = json.load(f)

    # Add new model to registry
    registry['models'].append({
        'version': model_version,
        'model_dir': model_dir,
        'trained_at': metadata['trained_at'],
        'total_samples': metadata['total_samples'],
        'test_f1_micro': test_metrics['f1_micro'],
        'test_f1_macro': test_metrics['f1_macro'],
        'active': True  # Mark as active (latest)
    })

    # Mark previous models as inactive
    for model in registry['models'][:-1]:
        model['active'] = False

    # Save registry
    os.makedirs(os.path.dirname(registry_file), exist_ok=True)
    with open(registry_file, 'w') as f:
        json.dump(registry, f, indent=2)

    print(f"✓ Registry updated")
    print(f"  Active model: {model_version}")
    print(f"  F1 (micro): {test_metrics['f1_micro']:.4f}")
    print(f"  F1 (macro): {test_metrics['f1_macro']:.4f}")

    return model_version


def send_metrics(**context):
    """
    Task 7: Send retraining metrics to monitoring

    Logs metrics for Grafana visualization
    """
    model_version = context['task_instance'].xcom_pull(
        task_ids='retrain_model',
        key='model_version'
    )

    validated_count = context['task_instance'].xcom_pull(
        task_ids='validate_with_ollama',
        key='validated_count'
    )

    print("Sending metrics to monitoring...")

    # Load test metrics
    model_dir = context['task_instance'].xcom_pull(
        task_ids='retrain_model',
        key='model_dir'
    )

    with open(f'{model_dir}/test_metrics.json', 'r') as f:
        test_metrics = json.load(f)

    # Log metrics (would send to Prometheus/Grafana in production)
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'model_version': model_version,
        'validated_samples': validated_count,
        'test_f1_micro': test_metrics['f1_micro'],
        'test_f1_macro': test_metrics['f1_macro'],
        'test_hamming_loss': test_metrics['hamming_loss']
    }

    print(f"✓ Metrics: {json.dumps(metrics, indent=2)}")

    # Save metrics log
    metrics_log = '/opt/airflow/logs/retraining_metrics.jsonl'
    os.makedirs(os.path.dirname(metrics_log), exist_ok=True)

    with open(metrics_log, 'a') as f:
        f.write(json.dumps(metrics) + '\n')

    return metrics


# Define tasks
task_fetch = PythonOperator(
    task_id='fetch_recent_posts',
    python_callable=fetch_recent_posts,
    dag=dag
)

task_inference = PythonOperator(
    task_id='run_inference',
    python_callable=run_inference,
    dag=dag
)

task_select_uncertain = PythonOperator(
    task_id='select_uncertain_predictions',
    python_callable=select_uncertain_predictions,
    dag=dag
)

task_validate = PythonOperator(
    task_id='validate_with_ollama',
    python_callable=validate_with_ollama,
    dag=dag
)

task_retrain = PythonOperator(
    task_id='retrain_model',
    python_callable=retrain_model,
    dag=dag
)

task_registry = PythonOperator(
    task_id='update_model_registry',
    python_callable=update_model_registry,
    dag=dag
)

task_metrics = PythonOperator(
    task_id='send_metrics',
    python_callable=send_metrics,
    dag=dag
)

# Define task dependencies
task_fetch >> task_inference >> task_select_uncertain >> task_validate >> task_retrain >> task_registry >> task_metrics
