# Real-Time Reddit Stress Detection - Monitoring Guide

## 🚀 System Overview

**Data Flow:**
```
Reddit API (10 posts/min) → Kafka → Spark Streaming (ML v4) → Cassandra
```

## 📊 How to Monitor Real-Time Processing

### Option 1: Run the Monitoring Script (Recommended)
```bash
./run_realtime_demo.sh
```

**Output Example:**
```
[01:07:17] ⏸️  Waiting for new Reddit posts...
[01:08:30] ✅ NEW: 2 post(s) classified | Total: 24
           Latest: mentalhealth | 0.95 | True
```

### Option 2: Web UIs

1. **Spark Streaming Dashboard** (Best for detailed metrics)
   - URL: http://localhost:4040
   - Shows: Batch processing times, input rates, ML inference stats

2. **Spark Master UI**
   - URL: http://localhost:8081
   - Shows: Running applications, worker status

3. **Grafana Dashboard**
   - URL: http://localhost:3000 (admin/admin)
   - Shows: Stress detection visualizations

### Option 3: Command Line Monitoring

```bash
# Watch classified posts count (updates every 5 seconds)
watch -n 5 'docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;"'

# Monitor producer activity
docker logs -f reddit-producer | grep "Published"

# Check latest high-stress posts
docker exec reddit-cassandra cqlsh -e \
  "SELECT subreddit, title, stress_score FROM reddit_rt.classified_posts_by_hour \
   WHERE stress_score > 0.8 ALLOW FILTERING LIMIT 5;"
```

## 🔄 Current Configuration

- **Producer Rate:** 10 posts/minute (configurable in `producers/reddit_producer/config/config.yaml`)
- **Spark Batch Interval:** Every 10 seconds
- **ML Model:** DistilBERT v4 (stress detection)
- **Processing Time:** ~1-2 seconds per post

## 📈 Expected Behavior

1. **Producer:** Publishes 10 new posts every ~60 seconds
2. **Kafka:** Queues messages in `reddit.posts.raw.v1` topic
3. **Spark:** Processes batches every 10 seconds
4. **ML Inference:** Classifies each post (stress score 0-1)
5. **Cassandra:** Stores classified posts in real-time

## ⚡ Performance Metrics

- **Throughput:** ~6-10 posts/minute (limited by Reddit API)
- **Latency:** 30-60 seconds (producer → Cassandra)
- **ML Accuracy:** ~80% (F1: 0.83)

## 🎯 Sample Queries

```bash
# Total posts classified today
docker exec reddit-cassandra cqlsh -e \
  "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;"

# High-stress posts with details
docker exec reddit-cassandra cqlsh -e \
  "SELECT subreddit, title, stress_score, stress_label \
   FROM reddit_rt.classified_posts_by_hour \
   WHERE stress_score > 0.9 ALLOW FILTERING;"

# Stress detection rate
docker exec reddit-cassandra cqlsh -e \
  "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour \
   WHERE stress_label = true ALLOW FILTERING;"
```

## 🐛 Troubleshooting

### No new posts appearing?
```bash
# Check producer
docker logs reddit-producer --tail 20

# Check Spark job
docker logs reddit-spark-master --tail 50

# Restart pipeline
docker-compose restart reddit-producer
docker exec reddit-spark-master pkill -f kafka_to_cassandra_with_ml.py
# Then restart Spark job
```

### Spark not processing?
- Check Spark UI: http://localhost:4040
- Verify producer is publishing: `docker logs -f reddit-producer`
- Check Kafka has messages: 
  ```bash
  docker exec reddit-kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic reddit.posts.raw.v1 \
    --max-messages 1
  ```
