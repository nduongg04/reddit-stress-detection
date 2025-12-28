"""
Training Service API
Dedicated service for heavy model training (PhoBERT)
Separated from Airflow to avoid OOM issues

Endpoints:
- POST /api/train - Start training job
- GET /api/jobs/<job_id> - Get job status
- GET /api/jobs/<job_id>/logs - Get training logs
"""

from flask import Flask, request, jsonify
import threading
import uuid
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import logging

# Add project paths
sys.path.insert(0, '/workspace')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Job storage (in production, use Redis/database)
jobs = {}
jobs_lock = threading.Lock()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_worker(job_id, config):
    """Background worker to train model"""
    from ml.models.train_phobert_retrain import train_phobert
    
    with jobs_lock:
        jobs[job_id]['state'] = 'running'
        jobs[job_id]['started_at'] = datetime.now().isoformat()
    
    try:
        logger.info(f"[Job {job_id}] Starting PhoBERT training...")
        logger.info(f"[Job {job_id}] Config: {config}")
        
        # Train model
        model_dir = train_phobert(config, job_id=job_id)
        
        with jobs_lock:
            jobs[job_id]['state'] = 'completed'
            jobs[job_id]['model_dir'] = model_dir
            jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        logger.info(f"[Job {job_id}] Training completed: {model_dir}")
        
    except Exception as e:
        logger.error(f"[Job {job_id}] Training failed: {str(e)}", exc_info=True)
        
        with jobs_lock:
            jobs[job_id]['state'] = 'failed'
            jobs[job_id]['error'] = str(e)
            jobs[job_id]['failed_at'] = datetime.now().isoformat()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'training-api'})


@app.route('/api/train', methods=['POST'])
def start_training():
    """
    Start a new training job
    
    Request body:
    {
        "model_type": "phobert",
        "data_file": "/path/to/data.csv",
        "config": {
            "epochs": 10,
            "batch_size": 16,
            "learning_rate": 2e-5,
            ...
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'data_file' not in data:
            return jsonify({'error': 'Missing data_file parameter'}), 400
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job record
        job = {
            'job_id': job_id,
            'model_type': data.get('model_type', 'phobert'),
            'data_file': data['data_file'],
            'config': data.get('config', {}),
            'state': 'queued',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'model_dir': None,
            'error': None
        }
        
        with jobs_lock:
            jobs[job_id] = job
        
        # Start training in background thread
        thread = threading.Thread(
            target=train_worker,
            args=(job_id, data.get('config', {})),
            kwargs={'data_file': data['data_file']},
            daemon=True
        )
        thread.start()
        
        logger.info(f"Training job {job_id} queued")
        
        return jsonify({
            'job_id': job_id,
            'state': 'queued',
            'message': 'Training job started'
        }), 202
        
    except Exception as e:
        logger.error(f"Failed to start training: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get job status and details"""
    with jobs_lock:
        job = jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job)


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs"""
    with jobs_lock:
        job_list = list(jobs.values())
    
    # Sort by created_at descending
    job_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({
        'jobs': job_list,
        'total': len(job_list)
    })


@app.route('/api/jobs/<job_id>/logs', methods=['GET'])
def get_job_logs(job_id):
    """Get training logs for a job"""
    with jobs_lock:
        job = jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Read log file if exists
    log_file = f'/workspace/ml/models/training_logs/{job_id}.log'
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
        return jsonify({'logs': logs})
    else:
        return jsonify({'logs': 'No logs available yet'})


if __name__ == '__main__':
    # Ensure log directory exists
    os.makedirs('/workspace/ml/models/training_logs', exist_ok=True)
    
    # Run server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
