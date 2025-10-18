# Reddit Producer (PRAW)

Real-time Reddit data ingestion service using PRAW (Python Reddit API Wrapper) to stream live posts and comments from mental health subreddits to Kafka.

## Overview

This producer streams real-time data from Reddit using the official Reddit API (PRAW). It monitors specified subreddits for new submissions and comments, transforms them into a standardized format, and publishes them to Kafka.

### Features

- **Real-time streaming** of Reddit submissions and comments
- **Rate limiting** to respect Reddit API limits (60 requests/minute)
- **Error handling** with Dead Letter Queue (DLQ) support
- **Health monitoring** via HTTP endpoints
- **Prometheus metrics** for observability
- **Graceful shutdown** handling
- **Automatic retry** on transient failures
- **Docker support** for containerized deployment

## Architecture

```
┌─────────────┐
│   Reddit    │
│     API     │
└──────┬──────┘
       │ PRAW
       ▼
┌─────────────────────┐
│  Reddit Stream      │
│  - Rate Limiter     │
│  - Schema Transform │
│  - Validation       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Kafka Producer     │
│  - Retry Logic      │
│  - DLQ Support      │
│  - Metrics          │
└──────┬──────────────┘
       │
       ▼
┌──────────────┬──────────────┐
│ reddit.posts │  reddit.posts│
│   .raw.v1    │    .dlq.v1   │
└──────────────┴──────────────┘
```

## Prerequisites

### Reddit API Credentials

You need to create a Reddit application to obtain API credentials:

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the form:
   - **Name**: Your app name (e.g., "Reddit Stress Detector")
   - **App type**: Select "script"
   - **Description**: Optional
   - **About URL**: Optional
   - **Redirect URI**: http://localhost:8080 (required but not used)
4. Click "Create app"
5. Note your `client_id` (under the app name) and `client_secret`

### System Requirements

- Python 3.9+
- Kafka cluster (see TASK-001)
- 500MB+ RAM
- Network access to Reddit API

## Installation

### 1. Create Virtual Environment

```bash
cd producers/reddit_producer
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Create a `.env` file from the template:

```bash
cp .env.template .env
```

Edit `.env` and add your Reddit API credentials:

```env
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=reddit_stress_detector/1.0.0 by /u/your_username
```

**⚠️ Important**: Never commit the `.env` file to version control!

## Configuration

Edit `config/config.yaml` to customize:

### Subreddits

```yaml
reddit:
  subreddits:
    - anxiety
    - depression
    - stress
    - mentalhealth
```

### Kafka Settings

```yaml
kafka:
  bootstrap_servers:
    - localhost:9092
  topic: reddit.posts.raw.v1
  dlq_topic: reddit.posts.dlq.v1
```

### Rate Limiting

```yaml
rate_limiting:
  requests_per_minute: 60  # Reddit API limit
  burst_limit: 10
```

## Usage

### Basic Usage

Start the producer:

```bash
python main.py
```

### Command Line Options

```bash
# Use custom config file
python main.py --config path/to/config.yaml

# Stream only submissions (no comments)
python main.py --stream-type submissions

# Stream only comments (no submissions)
python main.py --stream-type comments

# Run in test mode for 60 seconds
python main.py --test-mode --duration 60
```

### Running with Docker

Build the Docker image:

```bash
docker build -t reddit-producer .
```

Run the container:

```bash
docker run -d \
  --name reddit-producer \
  --network reddit-network \
  --env-file .env \
  -p 8080:8080 \
  reddit-producer
```

### Docker Compose Integration

Add to your `docker-compose.yml`:

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
  ports:
    - "8080:8080"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

## Monitoring

### Health Check Endpoint

Check if the producer is healthy:

```bash
curl http://localhost:8080/health
```

Response:

```json
{
  "status": "healthy",
  "uptime_seconds": 3600.5,
  "uptime_formatted": "1h 0m 0s",
  "timestamp": 1234567890.0
}
```

### Statistics Endpoint

Get detailed statistics:

```bash
curl http://localhost:8080/stats
```

Response:

```json
{
  "uptime_seconds": 3600.5,
  "timestamp": 1234567890.0,
  "stream": {
    "posts_processed": 1500,
    "submissions_processed": 300,
    "comments_processed": 1200,
    "kafka_messages_sent": 1485,
    "kafka_errors": 15,
    "kafka_dlq_messages": 15,
    "kafka_success_rate": 99.0,
    "rate_limiter_utilization": 45.5
  }
}
```

### Prometheus Metrics

Scrape Prometheus metrics:

```bash
curl http://localhost:8080/metrics
```

Available metrics:

- `reddit_producer_messages_sent_total` - Total messages sent to Kafka
- `reddit_producer_message_size_bytes` - Message size histogram
- `reddit_producer_send_latency_seconds` - Send latency histogram
- `reddit_producer_uptime_seconds` - Producer uptime

## Data Schema

### Submission Format

```json
{
  "post_id": "abc123",
  "title": "Post title",
  "body": "Post body text",
  "author": "username",
  "subreddit": "anxiety",
  "created_utc": 1234567890,
  "score": 42,
  "num_comments": 10,
  "url": "https://reddit.com/...",
  "permalink": "https://reddit.com/r/anxiety/...",
  "type": "submission",
  "source": "praw",
  "ingestion_timestamp": "2025-10-10T12:00:00.000000"
}
```

### Comment Format

```json
{
  "post_id": "def456",
  "title": "",
  "body": "Comment body text",
  "author": "username",
  "subreddit": "depression",
  "created_utc": 1234567890,
  "score": 5,
  "parent_id": "t3_parent_id",
  "link_id": "t3_link_id",
  "permalink": "https://reddit.com/r/depression/.../def456",
  "type": "comment",
  "source": "praw",
  "ingestion_timestamp": "2025-10-10T12:00:00.000000"
}
```

## Testing

### Run Unit Tests

```bash
python -m pytest tests/ -v
```

### Run Integration Tests

```bash
./test_integration.sh
```

This will:

1. Check Kafka connectivity
2. Validate credentials
3. Run unit tests
4. Start producer in test mode
5. Verify health endpoints
6. Check messages in Kafka

### Manual Testing

Consume messages from Kafka to verify:

```bash
# Consume from main topic
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 \
  --from-beginning \
  --max-messages 10

# Consume from DLQ
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.dlq.v1 \
  --from-beginning
```

## Troubleshooting

### Producer Won't Start

**Check credentials:**

```bash
python -c "from config.secrets import RedditCredentials; RedditCredentials.validate()"
```

**Check Kafka connectivity:**

```bash
nc -z localhost 9092
```

### No Messages Appearing

**Check logs:**

```bash
tail -f logs/reddit_producer.log
```

**Common causes:**

- Reddit API rate limiting (normal, will auto-recover)
- No new posts in monitored subreddits (normal during quiet periods)
- Invalid credentials
- Network issues

### High Error Rate

**Check DLQ messages:**

```bash
docker exec reddit-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.dlq.v1 \
  --from-beginning
```

**Common error types:**

- `kafka_error` - Kafka connectivity issues
- `schema_validation_error` - Invalid post format
- `rate_limit_error` - Exceeded Reddit API limits

### Rate Limiting Issues

The producer automatically handles Reddit's rate limits (60 requests/minute). If you see rate limit warnings:

- This is normal behavior
- The producer will automatically slow down
- Check rate limiter stats: `curl http://localhost:8080/stats`

### Memory Issues

If the producer uses too much memory:

1. Reduce batch sizes in Kafka producer config
2. Lower rate limiting thresholds
3. Monitor fewer subreddits

## Performance Considerations

### Expected Throughput

- **Submissions**: 5-50 per minute (varies by subreddit activity)
- **Comments**: 50-500 per minute (varies by subreddit activity)
- **Total**: ~60 requests/minute (API limit)

### Resource Usage

- **CPU**: <20% (single core)
- **Memory**: ~200-500MB
- **Network**: ~10-100 KB/s

### Optimization Tips

1. **Use fewer subreddits** to reduce API calls
2. **Stream only what you need** (submissions or comments, not both)
3. **Enable compression** (already enabled by default)
4. **Monitor rate limiter utilization** and adjust if needed

## Security

### Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for sensitive data
3. **Rotate credentials** periodically
4. **Limit access** to `.env` file (chmod 600)
5. **Use secrets management** (Vault, AWS Secrets Manager) in production

### Reddit API Guidelines

Follow Reddit's API rules:

- Respect rate limits (60 req/min)
- Use descriptive user agent
- Don't scrape deleted content
- Follow subreddit rules
- See: https://github.com/reddit-archive/reddit/wiki/API

## Maintenance

### Log Rotation

Logs automatically rotate at 10MB with 5 backup files. Configure in `config/logging.yaml`.

### Monitoring Checklist

- Check health endpoint regularly
- Monitor error rate (<1% is good)
- Watch rate limiter utilization (<80% is good)
- Review DLQ messages periodically
- Monitor Kafka lag

### Graceful Shutdown

The producer handles shutdown signals (SIGINT, SIGTERM) gracefully:

1. Stops accepting new Reddit posts
2. Flushes pending Kafka messages
3. Logs final statistics
4. Closes connections cleanly

## Dependencies

See `requirements.txt` for full list:

- `praw==7.7.1` - Reddit API wrapper
- `kafka-python==2.0.2` - Kafka client
- `python-dotenv==1.0.0` - Environment variables
- `tenacity==8.2.3` - Retry logic
- `prometheus-client==0.19.0` - Metrics
- `pyyaml==6.0.1` - Configuration

## License

[Your License Here]

## Support

For issues or questions:

1. Check logs: `logs/reddit_producer.log`
2. Review troubleshooting section
3. Check Reddit API status
4. Verify Kafka cluster health

## Related Documentation

- [TASK-009: Reddit API Integration](../../tasks/detailed/task009.md)
- [Kafka Setup Guide](../../docs/kafka-setup.md)
- [Project PRD](../../docs/prd.md)
