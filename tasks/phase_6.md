# Phase 6: Airflow Retraining Pipeline

## Goal
Automated retraining pipeline using Airflow to continuously improve model quality by relabeling low-confidence predictions with Qwen3:14B.

## Architecture
```
Cassandra (low-confidence posts) → Airflow DAG → Qwen3:14B relabeling → New training data → PhoBERT retraining
```

## Tasks

### 6.1 Airflow Setup
- [ ] Uncomment Airflow services in docker-compose.yml
- [ ] Configure PostgreSQL backend for Airflow
- [ ] Set up DAGs directory
- [ ] Test Airflow webserver and scheduler

### 6.2 Retraining DAG
- [ ] Create `retrain_phobert.py` DAG
- [ ] Schedule: Daily at 2 AM
- [ ] Query low-confidence posts from Cassandra
- [ ] Relabel with Qwen3:14B
- [ ] Append to training data
- [ ] Trigger retraining

### 6.3 Low-Confidence Query
- [ ] Query posts with confidence < 0.5
- [ ] Limit to 100 newest posts
- [ ] Export to JSONL format
- [ ] Track already-relabeled posts

### 6.4 Qwen3:14B Relabeling
- [ ] Connect to Ollama API
- [ ] Use enhanced prompt for better accuracy
- [ ] Validate output format
- [ ] Save relabeled data

### 6.5 Incremental Training
- [ ] Merge with existing training data
- [ ] Balance dataset
- [ ] Retrain PhoBERT
- [ ] Export new ONNX model
- [ ] Hot-swap model in Spark

## DAG Structure

```
┌─────────────────────────────────────────────────────────────┐
│  retrain_phobert DAG (Daily @ 2 AM)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐│
│  │ query_low    │ ──► │ relabel_with │ ──► │ validate     ││
│  │ _confidence  │     │ _qwen14b     │     │ _labels      ││
│  └──────────────┘     └──────────────┘     └──────────────┘│
│                                                              │
│                              │                               │
│                              ▼                               │
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐│
│  │ hot_swap     │ ◄── │ export_onnx  │ ◄── │ retrain      ││
│  │ _model       │     │              │     │ _phobert     ││
│  └──────────────┘     └──────────────┘     └──────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Files Structure

```
airflow/
  dags/
    retrain_phobert.py          # Main retraining DAG
  plugins/
    operators/
      cassandra_operator.py     # Custom Cassandra operator
      ollama_operator.py        # Custom Ollama operator
  config/
    airflow.cfg                 # Airflow configuration

scripts/
  airflow_retrain/
    query_low_confidence.py     # Query Cassandra
    relabel_with_qwen.py        # Qwen3:14B labeling
    merge_training_data.py      # Merge datasets
    retrain_model.py            # PhoBERT training
    export_onnx.py              # Export ONNX
    hot_swap.py                 # Model swap
```

## DAG Code

```python
# airflow/dags/retrain_phobert.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

default_args = {
    'owner': 'stress-detection',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'retrain_phobert',
    default_args=default_args,
    description='Retrain PhoBERT with low-confidence posts relabeled by Qwen3:14B',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False,
    max_active_runs=1,
)

# Task 1: Query low-confidence posts
query_task = PythonOperator(
    task_id='query_low_confidence',
    python_callable=query_low_confidence_posts,
    op_kwargs={
        'confidence_threshold': 0.5,
        'limit': 100,
        'output_path': '/tmp/low_confidence_posts.jsonl'
    },
    dag=dag,
)

# Task 2: Relabel with Qwen3:14B
relabel_task = PythonOperator(
    task_id='relabel_with_qwen14b',
    python_callable=relabel_with_qwen,
    op_kwargs={
        'input_path': '/tmp/low_confidence_posts.jsonl',
        'output_path': '/tmp/relabeled_posts.jsonl',
        'model': 'qwen3:14b'
    },
    dag=dag,
)

# Task 3: Validate labels
validate_task = PythonOperator(
    task_id='validate_labels',
    python_callable=validate_labels,
    op_kwargs={
        'input_path': '/tmp/relabeled_posts.jsonl',
        'output_path': '/tmp/validated_posts.jsonl'
    },
    dag=dag,
)

# Task 4: Retrain PhoBERT
retrain_task = BashOperator(
    task_id='retrain_phobert',
    bash_command='''
        cd /opt/ml && python train_phobert.py \
            --new_data /tmp/validated_posts.jsonl \
            --epochs 3 \
            --output_dir /opt/ml/checkpoints/phobert_incremental
    ''',
    dag=dag,
)

# Task 5: Export to ONNX
export_task = BashOperator(
    task_id='export_onnx',
    bash_command='''
        cd /opt/ml && python export_onnx.py \
            --checkpoint /opt/ml/checkpoints/phobert_incremental \
            --output /opt/models/phobert_stress_new.onnx
    ''',
    dag=dag,
)

# Task 6: Hot-swap model
swap_task = PythonOperator(
    task_id='hot_swap_model',
    python_callable=hot_swap_model,
    op_kwargs={
        'new_model': '/opt/models/phobert_stress_new.onnx',
        'target_model': '/opt/models/phobert_stress.onnx'
    },
    dag=dag,
)

# Define task dependencies
query_task >> relabel_task >> validate_task >> retrain_task >> export_task >> swap_task
```

## Query Low-Confidence Posts

```python
# scripts/airflow_retrain/query_low_confidence.py
from cassandra.cluster import Cluster
import json

def query_low_confidence_posts(confidence_threshold=0.5, limit=100, output_path='/tmp/posts.jsonl'):
    """Query posts with confidence < threshold from Cassandra."""
    cluster = Cluster(['cassandra'])
    session = cluster.connect('reddit_rt')

    # Get recent hour buckets
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    hour_buckets = [(now - timedelta(hours=i)).strftime('%Y-%m-%d-%H') for i in range(24)]

    posts = []
    for bucket in hour_buckets:
        if len(posts) >= limit:
            break

        query = """
            SELECT post_id, text, aspects, aspect_probs, confidence, stress_label
            FROM voz_classified_posts
            WHERE hour_bucket = %s
            ALLOW FILTERING
        """
        rows = session.execute(query, [bucket])

        for row in rows:
            if row.confidence and row.confidence < confidence_threshold:
                posts.append({
                    'post_id': row.post_id,
                    'text': row.text,
                    'original_aspects': list(row.aspects) if row.aspects else [],
                    'original_confidence': row.confidence,
                    'original_stress_label': row.stress_label
                })

                if len(posts) >= limit:
                    break

    # Sort by confidence (lowest first) and take top N
    posts.sort(key=lambda x: x['original_confidence'])
    posts = posts[:limit]

    # Write to JSONL
    with open(output_path, 'w', encoding='utf-8') as f:
        for post in posts:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    print(f"Exported {len(posts)} low-confidence posts to {output_path}")
    cluster.shutdown()
    return len(posts)
```

## Relabel with Qwen3:14B

```python
# scripts/airflow_retrain/relabel_with_qwen.py
import json
import requests

ASPECT_NAMES = [
    "work_stress", "financial_anxiety", "relationship_issues",
    "academic_pressure", "exhaustion", "depression",
    "loneliness", "health_concerns", "family_conflict", "future_uncertainty"
]

def relabel_with_qwen(input_path, output_path, model='qwen3:14b'):
    """Relabel posts using Qwen3:14B for higher accuracy."""

    ollama_host = 'host.docker.internal:11434'

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

    results = []
    with open(input_path, 'r', encoding='utf-8') as f:
        posts = [json.loads(line) for line in f]

    for i, post in enumerate(posts):
        print(f"Relabeling {i+1}/{len(posts)}: {post['post_id']}")

        prompt = prompt_template.format(text=post['text'][:800])

        try:
            response = requests.post(
                f"http://{ollama_host}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256}
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
                    post['new_confidence'] = data.get("confidence", 0.8)
                    post['relabel_model'] = model

                    results.append(post)
                    print(f"  -> Aspects: {post['new_aspects']}, Confidence: {post['new_confidence']}")
                    continue

        except Exception as e:
            print(f"  -> Error: {e}")

        # Fallback: keep original
        post['new_aspects'] = post['original_aspects']
        post['new_stress_label'] = post['original_stress_label']
        post['new_confidence'] = post['original_confidence']
        post['relabel_model'] = 'fallback'
        results.append(post)

    # Write results
    with open(output_path, 'w', encoding='utf-8') as f:
        for post in results:
            f.write(json.dumps(post, ensure_ascii=False) + '\n')

    relabeled_count = sum(1 for p in results if p.get('relabel_model') == model)
    print(f"Successfully relabeled {relabeled_count}/{len(results)} posts")
    return relabeled_count
```

## Docker Compose Update

```yaml
# Add to docker-compose.yml

  # Airflow PostgreSQL Backend
  airflow-postgres:
    image: postgres:15
    hostname: airflow-postgres
    container_name: reddit-airflow-postgres
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - airflow-postgres-data:/var/lib/postgresql/data
    networks:
      - reddit-network
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Airflow Webserver
  airflow-webserver:
    image: apache/airflow:2.7.3
    hostname: airflow-webserver
    container_name: reddit-airflow-webserver
    depends_on:
      airflow-postgres:
        condition: service_healthy
      cassandra:
        condition: service_healthy
    ports:
      - "8082:8080"
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres/airflow
      AIRFLOW__CORE__FERNET_KEY: ""
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "true"
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__API__AUTH_BACKENDS: "airflow.api.auth.backend.basic_auth"
      _AIRFLOW_DB_UPGRADE: "true"
      _AIRFLOW_WWW_USER_CREATE: "true"
      _AIRFLOW_WWW_USER_USERNAME: airflow
      _AIRFLOW_WWW_USER_PASSWORD: airflow
      OLLAMA_HOST: host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/plugins:/opt/airflow/plugins
      - ./ml:/opt/ml
      - ./data:/opt/data
    command: webserver
    networks:
      - reddit-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Airflow Scheduler
  airflow-scheduler:
    image: apache/airflow:2.7.3
    hostname: airflow-scheduler
    container_name: reddit-airflow-scheduler
    depends_on:
      airflow-postgres:
        condition: service_healthy
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres/airflow
      AIRFLOW__CORE__FERNET_KEY: ""
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "true"
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      OLLAMA_HOST: host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/plugins:/opt/airflow/plugins
      - ./ml:/opt/ml
      - ./data:/opt/data
    command: scheduler
    networks:
      - reddit-network
```

## Validation Criteria

- [ ] Airflow webserver accessible at http://localhost:8082
- [ ] DAG appears in Airflow UI
- [ ] Query task exports correct posts
- [ ] Qwen3:14B relabeling works
- [ ] Validation filters invalid labels
- [ ] Retraining completes without errors
- [ ] ONNX export produces valid model
- [ ] Hot-swap doesn't interrupt streaming

## Performance Targets

| Metric | Target |
|--------|--------|
| Query time | < 30 seconds |
| Relabel per post | < 30 seconds |
| Total 100 posts | < 1 hour |
| Retraining | < 30 minutes |
| ONNX export | < 5 minutes |
| Hot-swap | < 10 seconds |

## Access URLs

| Service | URL |
|---------|-----|
| Airflow UI | http://localhost:8082 |
| Credentials | airflow / airflow |
