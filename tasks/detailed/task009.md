# TASK-009: Reddit API Integration (PRAW)

**Owner:** Data Engineer
**Priority:** Critical
**Dependencies:** TASK-001 (Kafka Cluster Setup)
**Estimate:** 2 days

---

## Overview

Implement real-time Reddit data ingestion using PRAW (Python Reddit API Wrapper) to stream live posts and comments from target mental health subreddits to Kafka.

---

## Subtasks

### Subtask 009.1: Reddit API Credentials Setup

**Estimate:** 30 minutes

**Description:**
- Create Reddit application at https://www.reddit.com/prefs/apps
- Obtain credentials: `client_id`, `client_secret`, `user_agent`
- **[USER TASK]** Manually create Reddit app and save credentials

**Acceptance Criteria:**
- Reddit application created successfully
- Credentials obtained and documented
- Test authentication works

**Commands:**
```bash
# Create .env file template
cat > producers/reddit_producer/.env.template << 'EOF'
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=reddit_stress_detector/1.0.0 by /u/your_username
EOF
```

---

### Subtask 009.2: Secure Credential Storage

**Estimate:** 1 hour

**Description:**
- Set up credential storage (choose HashiCorp Vault, AWS Secrets Manager, or .env file)
- Implement credential loading logic
- Add .env to .gitignore to prevent accidental commits

**Acceptance Criteria:**
- Credentials stored securely
- No credentials in source code or version control
- Credential retrieval tested

**Files to Create/Modify:**
- `producers/reddit_producer/.gitignore`
- `producers/reddit_producer/config/secrets.py`

**Implementation:**
```python
# config/secrets.py
import os
from dotenv import load_dotenv

load_dotenv()

class RedditCredentials:
    CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
    CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
    USER_AGENT = os.getenv('REDDIT_USER_AGENT')

    @classmethod
    def validate(cls):
        if not all([cls.CLIENT_ID, cls.CLIENT_SECRET, cls.USER_AGENT]):
            raise ValueError("Missing Reddit credentials")
```

---

### Subtask 009.3: Project Structure Setup

**Estimate:** 30 minutes

**Description:**
- Create project directory structure for Reddit producer
- Set up Python virtual environment
- Create basic configuration files

**Acceptance Criteria:**
- Directory structure created
- Virtual environment activated
- Configuration files in place

**Commands:**
```bash
mkdir -p producers/reddit_producer/{config,utils,tests}
cd producers/reddit_producer
python3 -m venv venv
source venv/bin/activate
touch config/__init__.py config/config.py config/secrets.py
touch utils/__init__.py utils/rate_limiter.py
touch main.py
```

---

### Subtask 009.4: Install PRAW and Dependencies

**Estimate:** 15 minutes

**Description:**
- Install PRAW and other required packages
- Create requirements.txt
- Test PRAW installation

**Acceptance Criteria:**
- All dependencies installed
- requirements.txt created
- Import test successful

**Files to Create:**
- `producers/reddit_producer/requirements.txt`

**Content:**
```txt
praw==7.7.1
kafka-python==2.0.2
python-dotenv==1.0.0
requests==2.31.0
tenacity==8.2.3
prometheus-client==0.19.0
pyyaml==6.0.1
```

**Commands:**
```bash
pip install -r requirements.txt
python -c "import praw; print(praw.__version__)"
```

---

### Subtask 009.5: Configuration File Setup

**Estimate:** 30 minutes

**Description:**
- Create configuration file for target subreddits and Kafka settings
- Implement configuration loader
- Validate configuration

**Acceptance Criteria:**
- Configuration file created
- Configuration loader implemented
- Validation logic works

**Files to Create:**
- `producers/reddit_producer/config/config.yaml`
- `producers/reddit_producer/config/config.py`

**config.yaml:**
```yaml
reddit:
  subreddits:
    - anxiety
    - depression
    - stress
    - mentalhealth
  stream_types:
    - submissions
    - comments
  skip_existing: true

kafka:
  bootstrap_servers:
    - localhost:9092
  topic: reddit.posts.raw.v1
  dlq_topic: reddit.posts.dlq.v1

producer:
  max_retries: 3
  retry_backoff_ms: 1000
  request_timeout_ms: 30000

rate_limiting:
  requests_per_minute: 60
  burst_limit: 10

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

### Subtask 009.6: Rate Limiter Implementation

**Estimate:** 1 hour

**Description:**
- Implement rate limiting to respect Reddit API limits (60 requests/minute)
- Add exponential backoff for rate limit errors
- Implement request tracking

**Acceptance Criteria:**
- Rate limiter respects 60 req/min limit
- Exponential backoff works correctly
- Request metrics tracked

**Files to Create:**
- `producers/reddit_producer/utils/rate_limiter.py`

**Implementation:**
```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    def __init__(self, requests_per_minute=60, burst_limit=10):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.requests = deque()
        self.lock = Lock()

    def wait_if_needed(self):
        with self.lock:
            now = time.time()

            # Remove requests older than 1 minute
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            # Check if we've hit the limit
            if len(self.requests) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.requests[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self.requests.append(time.time())

    def reset(self):
        with self.lock:
            self.requests.clear()
```

**Tests:**
```python
# Test rate limiter
limiter = RateLimiter(requests_per_minute=60)
start = time.time()
for i in range(65):
    limiter.wait_if_needed()
elapsed = time.time() - start
assert elapsed >= 60  # Should take at least 60 seconds
```

---

### Subtask 009.7: Reddit Data Schema Definition

**Estimate:** 30 minutes

**Description:**
- Define data schema for Reddit posts and comments
- Create data transformation functions
- Ensure compatibility with downstream consumers

**Acceptance Criteria:**
- Schema matches specification in PRD
- Transformation functions tested
- Schema validation works

**Files to Create:**
- `producers/reddit_producer/utils/schema.py`

**Implementation:**
```python
from datetime import datetime
import json

def transform_submission(submission):
    """Transform PRAW submission to standardized format"""
    return {
        "post_id": submission.id,
        "title": submission.title,
        "body": submission.selftext,
        "author": submission.author.name if submission.author else "[deleted]",
        "subreddit": submission.subreddit.display_name,
        "created_utc": int(submission.created_utc),
        "score": submission.score,
        "num_comments": submission.num_comments,
        "url": submission.url,
        "type": "submission",
        "source": "praw",
        "ingestion_timestamp": datetime.utcnow().isoformat()
    }

def transform_comment(comment):
    """Transform PRAW comment to standardized format"""
    return {
        "post_id": comment.id,
        "title": "",  # Comments don't have titles
        "body": comment.body,
        "author": comment.author.name if comment.author else "[deleted]",
        "subreddit": comment.subreddit.display_name,
        "created_utc": int(comment.created_utc),
        "score": comment.score,
        "parent_id": comment.parent_id,
        "type": "comment",
        "source": "praw",
        "ingestion_timestamp": datetime.utcnow().isoformat()
    }

def validate_post(post_dict):
    """Validate post has required fields"""
    required_fields = ['post_id', 'body', 'author', 'subreddit', 'created_utc']
    return all(field in post_dict for field in required_fields)
```

---

### Subtask 009.8: Kafka Producer Implementation

**Estimate:** 1.5 hours

**Description:**
- Implement Kafka producer with error handling
- Add retry logic for failed sends
- Implement delivery callbacks

**Acceptance Criteria:**
- Producer successfully connects to Kafka
- Messages delivered reliably
- Failed messages logged

**Files to Create:**
- `producers/reddit_producer/utils/kafka_producer.py`

**Implementation:**
```python
from kafka import KafkaProducer
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class RedditKafkaProducer:
    def __init__(self, config):
        self.config = config
        self.producer = KafkaProducer(
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=config['producer']['max_retries'],
            max_in_flight_requests_per_connection=1,
            compression_type='gzip'
        )
        self.topic = config['kafka']['topic']
        self.dlq_topic = config['kafka']['dlq_topic']
        self.message_count = 0
        self.error_count = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_message(self, message, key=None):
        """Send message to Kafka with retry logic"""
        try:
            future = self.producer.send(
                self.topic,
                value=message,
                key=key
            )
            future.add_callback(self.on_success)
            future.add_errback(self.on_error)
            self.message_count += 1
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.send_to_dlq(message, str(e))
            self.error_count += 1
            raise

    def on_success(self, metadata):
        logger.debug(f"Message sent to {metadata.topic} partition {metadata.partition} offset {metadata.offset}")

    def on_error(self, exception):
        logger.error(f"Error sending message: {exception}")
        self.error_count += 1

    def send_to_dlq(self, message, error_msg):
        """Send failed message to DLQ"""
        dlq_message = {
            "original_message": message,
            "error_type": "producer_error",
            "error_message": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.producer.send(self.dlq_topic, value=dlq_message)

    def flush(self):
        self.producer.flush()

    def close(self):
        self.producer.close()
        logger.info(f"Producer closed. Sent {self.message_count} messages, {self.error_count} errors")
```

---

### Subtask 009.9: PRAW Stream Implementation

**Estimate:** 2 hours

**Description:**
- Implement Reddit stream using PRAW
- Handle both submissions and comments
- Implement error recovery

**Acceptance Criteria:**
- Stream receives live Reddit data
- Both submissions and comments processed
- Stream recovers from interruptions

**Files to Create:**
- `producers/reddit_producer/reddit_stream.py`

**Implementation:**
```python
import praw
import logging
from config.secrets import RedditCredentials
from utils.schema import transform_submission, transform_comment, validate_post
from utils.rate_limiter import RateLimiter
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class RedditStream:
    def __init__(self, config, kafka_producer):
        RedditCredentials.validate()

        self.reddit = praw.Reddit(
            client_id=RedditCredentials.CLIENT_ID,
            client_secret=RedditCredentials.CLIENT_SECRET,
            user_agent=RedditCredentials.USER_AGENT
        )

        self.config = config
        self.kafka_producer = kafka_producer
        self.rate_limiter = RateLimiter(
            requests_per_minute=config['rate_limiting']['requests_per_minute']
        )

        # Build subreddit string: "anxiety+depression+stress+mentalhealth"
        self.subreddit_str = '+'.join(config['reddit']['subreddits'])
        self.subreddit = self.reddit.subreddit(self.subreddit_str)

        self.post_count = 0

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=60))
    def stream_submissions(self):
        """Stream new submissions from subreddits"""
        logger.info(f"Starting submission stream for r/{self.subreddit_str}")

        for submission in self.subreddit.stream.submissions(skip_existing=True):
            try:
                self.rate_limiter.wait_if_needed()
                post_data = transform_submission(submission)

                if validate_post(post_data):
                    self.kafka_producer.send_message(
                        message=post_data,
                        key=post_data['post_id']
                    )
                    self.post_count += 1

                    if self.post_count % 100 == 0:
                        logger.info(f"Processed {self.post_count} submissions")
                else:
                    logger.warning(f"Invalid submission: {post_data['post_id']}")

            except Exception as e:
                logger.error(f"Error processing submission {submission.id}: {e}")
                continue

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=60))
    def stream_comments(self):
        """Stream new comments from subreddits"""
        logger.info(f"Starting comment stream for r/{self.subreddit_str}")

        for comment in self.subreddit.stream.comments(skip_existing=True):
            try:
                self.rate_limiter.wait_if_needed()
                post_data = transform_comment(comment)

                if validate_post(post_data):
                    self.kafka_producer.send_message(
                        message=post_data,
                        key=post_data['post_id']
                    )
                    self.post_count += 1

                    if self.post_count % 100 == 0:
                        logger.info(f"Processed {self.post_count} comments")
                else:
                    logger.warning(f"Invalid comment: {post_data['post_id']}")

            except Exception as e:
                logger.error(f"Error processing comment {comment.id}: {e}")
                continue

    def get_stats(self):
        return {
            "posts_processed": self.post_count,
            "kafka_messages_sent": self.kafka_producer.message_count,
            "kafka_errors": self.kafka_producer.error_count
        }
```

---

### Subtask 009.10: Main Application Script

**Estimate:** 1 hour

**Description:**
- Create main application entry point
- Implement graceful shutdown handling
- Add command-line argument parsing

**Acceptance Criteria:**
- Application starts and runs continuously
- Graceful shutdown on SIGTERM/SIGINT
- CLI arguments work

**Files to Create:**
- `producers/reddit_producer/main.py`

**Implementation:**
```python
import signal
import sys
import logging
import yaml
from threading import Thread
from reddit_stream import RedditStream
from utils.kafka_producer import RedditKafkaProducer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    logger.info("Shutdown signal received, stopping gracefully...")
    shutdown_flag = True

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load configuration
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    logger.info("Starting Reddit Producer...")
    logger.info(f"Target subreddits: {config['reddit']['subreddits']}")

    # Initialize Kafka producer
    kafka_producer = RedditKafkaProducer(config)

    # Initialize Reddit stream
    reddit_stream = RedditStream(config, kafka_producer)

    try:
        # Start submission stream in separate thread
        submission_thread = Thread(
            target=reddit_stream.stream_submissions,
            daemon=True
        )
        submission_thread.start()

        # Start comment stream in separate thread
        comment_thread = Thread(
            target=reddit_stream.stream_comments,
            daemon=True
        )
        comment_thread.start()

        # Keep main thread alive
        while not shutdown_flag:
            submission_thread.join(timeout=1)
            comment_thread.join(timeout=1)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Flushing remaining messages...")
        kafka_producer.flush()
        kafka_producer.close()

        stats = reddit_stream.get_stats()
        logger.info(f"Final stats: {stats}")
        logger.info("Reddit Producer stopped")

if __name__ == "__main__":
    main()
```

---

### Subtask 009.11: Health Check Endpoint

**Estimate:** 1 hour

**Description:**
- Implement HTTP health check endpoint for monitoring
- Expose metrics (messages sent, errors, uptime)
- Test health endpoint

**Acceptance Criteria:**
- Health endpoint returns 200 when healthy
- Metrics exposed correctly
- Prometheus-compatible format

**Files to Create:**
- `producers/reddit_producer/health_server.py`

**Implementation:**
```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
from threading import Thread
from prometheus_client import Counter, Gauge, generate_latest

# Prometheus metrics
messages_sent = Counter('reddit_producer_messages_sent_total', 'Total messages sent')
errors_total = Counter('reddit_producer_errors_total', 'Total errors')
stream_uptime = Gauge('reddit_producer_uptime_seconds', 'Producer uptime in seconds')

class HealthHandler(BaseHTTPRequestHandler):
    start_time = time.time()

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            health_data = {
                "status": "healthy",
                "uptime_seconds": time.time() - self.start_time
            }
            self.wfile.write(json.dumps(health_data).encode())

        elif self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(generate_latest())

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging

def start_health_server(port=8080):
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
```

---

### Subtask 009.12: Logging Setup

**Estimate:** 30 minutes

**Description:**
- Configure structured logging
- Add log rotation
- Set up different log levels for components

**Acceptance Criteria:**
- Logs formatted correctly
- Log rotation configured
- Different log levels work

**Files to Create:**
- `producers/reddit_producer/config/logging.yaml`

**Content:**
```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: logs/reddit_producer.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  reddit_stream:
    level: INFO
    handlers: [console, file]
    propagate: false

  kafka_producer:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

---

### Subtask 009.13: Unit Tests

**Estimate:** 1.5 hours

**Description:**
- Write unit tests for core components
- Test schema transformation
- Test rate limiter
- Test Kafka producer logic

**Acceptance Criteria:**
- All tests pass
- Code coverage >70%
- Edge cases covered

**Files to Create:**
- `producers/reddit_producer/tests/test_schema.py`
- `producers/reddit_producer/tests/test_rate_limiter.py`
- `producers/reddit_producer/tests/test_kafka_producer.py`

**Example test:**
```python
# tests/test_schema.py
import unittest
from unittest.mock import Mock
from utils.schema import transform_submission, validate_post

class TestSchema(unittest.TestCase):
    def test_transform_submission(self):
        # Mock PRAW submission
        mock_submission = Mock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Title"
        mock_submission.selftext = "Test Body"
        mock_submission.author.name = "testuser"
        mock_submission.subreddit.display_name = "anxiety"
        mock_submission.created_utc = 1234567890
        mock_submission.score = 10
        mock_submission.num_comments = 5
        mock_submission.url = "https://reddit.com/test"

        result = transform_submission(mock_submission)

        self.assertEqual(result['post_id'], "test123")
        self.assertEqual(result['title'], "Test Title")
        self.assertEqual(result['subreddit'], "anxiety")
        self.assertEqual(result['type'], "submission")
        self.assertEqual(result['source'], "praw")

    def test_validate_post(self):
        valid_post = {
            'post_id': '123',
            'body': 'test',
            'author': 'user',
            'subreddit': 'test',
            'created_utc': 123456
        }
        self.assertTrue(validate_post(valid_post))

        invalid_post = {'post_id': '123'}
        self.assertFalse(validate_post(invalid_post))

if __name__ == '__main__':
    unittest.main()
```

---

### Subtask 009.14: Integration Testing

**Estimate:** 1 hour

**Description:**
- Test end-to-end flow with test subreddit
- Verify messages appear in Kafka
- Test failure recovery

**Acceptance Criteria:**
- Producer connects to Reddit and Kafka
- Messages delivered successfully
- **[USER TASK]** Manually verify messages in Kafka UI

**Test Script:**
```bash
# Start producer
python main.py

# In another terminal, consume from Kafka
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 \
  --from-beginning \
  --max-messages 10
```

---

### Subtask 009.15: Docker Integration (Optional)

**Estimate:** 1 hour

**Description:**
- Create Dockerfile for Reddit producer
- Add to docker-compose
- Test containerized deployment

**Acceptance Criteria:**
- Docker image builds successfully
- Container runs and connects to Kafka
- Environment variables passed correctly

**Files to Create:**
- `producers/reddit_producer/Dockerfile`

**Content:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**Add to docker-compose.yml:**
```yaml
reddit-producer:
  build: ./producers/reddit_producer
  container_name: reddit-producer
  env_file:
    - ./producers/reddit_producer/.env
  depends_on:
    - kafka
  networks:
    - reddit-network
  restart: unless-stopped
```

---

### Subtask 009.16: Documentation

**Estimate:** 1 hour

**Description:**
- Create README with setup and usage instructions
- Document configuration options
- Add troubleshooting guide

**Acceptance Criteria:**
- README complete and clear
- Configuration documented
- Troubleshooting guide helpful

**Files to Create:**
- `producers/reddit_producer/README.md`

---

### Subtask 009.17: Performance Testing

**Estimate:** 1 hour

**Description:**
- Monitor resource usage (CPU, memory)
- Measure message throughput
- Test rate limiting effectiveness
- **[USER TASK]** Monitor metrics and validate performance

**Acceptance Criteria:**
- Resource usage acceptable (<500MB RAM, <20% CPU)
- Throughput measured and documented
- Rate limiting prevents API violations

**Test Commands:**
```bash
# Monitor resource usage
docker stats reddit-producer

# Check Kafka topic lag
kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group spark-streaming
```

---

### Subtask 009.18: Final Verification

**Estimate:** 30 minutes

**Description:**
- Run producer for 1 hour continuously
- Verify no crashes or memory leaks
- Check error rate <1%
- **[USER TASK]** Verify all acceptance criteria met

**Acceptance Criteria:**
- Producer runs for 1+ hour without issues
- Error rate <1%
- All metrics within acceptable ranges

---

## Rollback Plan

If issues occur:

1. **Stop the producer:**
   ```bash
   docker-compose stop reddit-producer
   ```

2. **Switch back to mock producer:**
   ```bash
   docker-compose up -d mock-producer
   ```

3. **Investigate logs:**
   ```bash
   docker logs reddit-producer
   ```

4. **Fix issues and redeploy**

---

## Testing Checklist

- [ ] Reddit API credentials obtained and secured
- [ ] Producer connects to Reddit successfully
- [ ] Messages sent to Kafka topic
- [ ] Rate limiting prevents API violations
- [ ] Error handling routes malformed data to DLQ
- [ ] Health endpoint returns 200
- [ ] Metrics exposed correctly
- [ ] Producer runs for 1+ hour without crashes
- [ ] Resource usage acceptable
- [ ] Error rate <1%
- [ ] Logs are clear and informative
- [ ] Graceful shutdown works
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-001: Kafka cluster operational
- Docker environment set up
- Reddit API access

**Blocks:**
- TASK-010: Historical Backfill (PSAW)
- TASK-011: Error Handling & Retry Logic
- TASK-024: Producer Metrics & Health Checks
- TASK-032: Security Hardening

---

## Notes

- Reddit API has rate limits (60 requests/minute per OAuth client)
- PRAW handles some rate limiting automatically, but we add extra safety
- Stream may have brief interruptions; retry logic handles this
- Comments typically have higher volume than submissions
- Test with small subreddits first before scaling to larger ones

---

## Estimated Completion

**Total Time:** 15-16 hours (2 days)

**Breakdown:**
- Setup & Configuration: 3 hours
- Implementation: 8 hours
- Testing & Debugging: 3 hours
- Documentation: 2 hours
