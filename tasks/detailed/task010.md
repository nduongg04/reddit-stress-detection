# TASK-010: Historical Backfill (PSAW)

**Owner:** Data Engineer
**Priority:** High
**Dependencies:** TASK-009 (Reddit API Integration)
**Estimate:** 1.5 days

---

## Overview

Implement historical data ingestion using PSAW (PushShift API Wrapper) to backfill 3-6 months of historical Reddit posts and comments from target mental health subreddits. This provides training data for the ML model and historical context for analysis.

---

## Subtasks

### Subtask 010.1: PSAW Setup and Installation

**Estimate:** 30 minutes

**Description:**
- Install PSAW library
- Understand Pushshift API limitations and rate limits
- Set up project structure for backfill scripts

**Acceptance Criteria:**
- PSAW installed successfully
- API limits documented
- Directory structure created

**Commands:**
```bash
cd producers/reddit_producer
pip install psaw==0.1.0

# Create backfill directory
mkdir -p backfill/{scripts,data,logs,checkpoints}
```

**Files to Update:**
- `producers/reddit_producer/requirements.txt`

**Add:**
```txt
psaw==0.1.0
```

---

### Subtask 010.2: Backfill Configuration

**Estimate:** 30 minutes

**Description:**
- Create configuration file for backfill parameters
- Define date ranges (3-6 months back)
- Configure batch sizes and rate limits

**Acceptance Criteria:**
- Configuration file created
- Date ranges calculated correctly
- Batch parameters defined

**Files to Create:**
- `producers/reddit_producer/backfill/config.yaml`

**Content:**
```yaml
backfill:
  # Date range for backfill
  start_date: "2024-04-01"  # Adjust based on current date
  end_date: "2024-10-01"    # Adjust based on current date

  # Subreddits to backfill (same as streaming)
  subreddits:
    - anxiety
    - depression
    - stress
    - mentalhealth

  # Batch configuration
  batch_size: 1000  # Posts per API request
  batch_delay_seconds: 2  # Delay between batches to respect rate limits

  # Data types to fetch
  data_types:
    - submissions
    - comments

  # Checkpoint configuration
  checkpoint_dir: backfill/checkpoints
  checkpoint_frequency: 10000  # Save checkpoint every N posts

  # Output configuration
  output_dir: backfill/data  # Optional: save raw data locally before Kafka
  save_raw: false  # Set true to save JSON files locally

kafka:
  topic: reddit.posts.raw.v1
  dlq_topic: reddit.posts.dlq.v1
  source_tag: psaw  # Tag to distinguish backfill data
```

---

### Subtask 010.3: Date Range Calculator

**Estimate:** 30 minutes

**Description:**
- Implement date range calculation utility
- Split date range into daily batches
- Handle timezone conversions

**Acceptance Criteria:**
- Date ranges calculated correctly
- Daily batches generated
- UTC timestamps used

**Files to Create:**
- `producers/reddit_producer/backfill/utils.py`

**Implementation:**
```python
from datetime import datetime, timedelta
import time

def calculate_date_ranges(start_date_str, end_date_str, batch_days=1):
    """
    Split date range into smaller batches
    Returns list of (start_timestamp, end_timestamp) tuples
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    ranges = []
    current = start_date

    while current < end_date:
        batch_end = min(current + timedelta(days=batch_days), end_date)

        # Convert to Unix timestamps
        start_ts = int(current.timestamp())
        end_ts = int(batch_end.timestamp())

        ranges.append({
            'start_ts': start_ts,
            'end_ts': end_ts,
            'start_date': current.strftime("%Y-%m-%d"),
            'end_date': batch_end.strftime("%Y-%m-%d")
        })

        current = batch_end

    return ranges

def format_timestamp(ts):
    """Format Unix timestamp for logging"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

# Example usage
ranges = calculate_date_ranges("2024-04-01", "2024-10-01", batch_days=1)
print(f"Total batches: {len(ranges)}")
```

---

### Subtask 010.4: Checkpoint Manager

**Estimate:** 1 hour

**Description:**
- Implement checkpoint system to track progress
- Enable resume from last successful checkpoint
- Store checkpoint metadata (date, post count, errors)

**Acceptance Criteria:**
- Checkpoints saved correctly
- Resume from checkpoint works
- Prevents duplicate ingestion

**Files to Create:**
- `producers/reddit_producer/backfill/checkpoint.py`

**Implementation:**
```python
import json
import os
from datetime import datetime
from pathlib import Path

class CheckpointManager:
    def __init__(self, checkpoint_dir):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, subreddit, data_type, last_processed_date, stats):
        """Save checkpoint for a subreddit and data type"""
        checkpoint_file = self.checkpoint_dir / f"{subreddit}_{data_type}.json"

        checkpoint_data = {
            "subreddit": subreddit,
            "data_type": data_type,
            "last_processed_date": last_processed_date,
            "last_updated": datetime.utcnow().isoformat(),
            "stats": stats
        }

        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

    def load_checkpoint(self, subreddit, data_type):
        """Load checkpoint for a subreddit and data type"""
        checkpoint_file = self.checkpoint_dir / f"{subreddit}_{data_type}.json"

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, 'r') as f:
            return json.load(f)

    def get_resume_date(self, subreddit, data_type, default_start_date):
        """Get date to resume from, or default start date"""
        checkpoint = self.load_checkpoint(subreddit, data_type)

        if checkpoint:
            return checkpoint['last_processed_date']

        return default_start_date

    def clear_checkpoint(self, subreddit, data_type):
        """Clear checkpoint (useful for restarting backfill)"""
        checkpoint_file = self.checkpoint_dir / f"{subreddit}_{data_type}.json"
        if checkpoint_file.exists():
            os.remove(checkpoint_file)

    def list_checkpoints(self):
        """List all checkpoints"""
        checkpoints = []
        for file in self.checkpoint_dir.glob("*.json"):
            with open(file, 'r') as f:
                checkpoints.append(json.load(f))
        return checkpoints
```

---

### Subtask 010.5: PSAW Submissions Fetcher

**Estimate:** 2 hours

**Description:**
- Implement PSAW API client for fetching submissions
- Handle API pagination
- Transform to standardized schema

**Acceptance Criteria:**
- Fetches submissions successfully
- Pagination handled correctly
- Data transformed to match schema

**Files to Create:**
- `producers/reddit_producer/backfill/psaw_client.py`

**Implementation:**
```python
from psaw import PushshiftAPI
import logging
from utils.schema import validate_post
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class PSAWClient:
    def __init__(self, config):
        self.api = PushshiftAPI()
        self.config = config
        self.batch_delay = config['backfill']['batch_delay_seconds']

    def fetch_submissions(self, subreddit, start_ts, end_ts, limit=1000):
        """
        Fetch submissions for a subreddit within a time range
        Returns generator of transformed submissions
        """
        logger.info(f"Fetching submissions from r/{subreddit} "
                   f"between {start_ts} and {end_ts}")

        try:
            submissions = self.api.search_submissions(
                subreddit=subreddit,
                after=start_ts,
                before=end_ts,
                limit=limit,
                filter=['id', 'title', 'selftext', 'author', 'created_utc',
                       'score', 'num_comments', 'url', 'subreddit']
            )

            count = 0
            for submission in submissions:
                try:
                    post_data = self._transform_submission(submission)

                    if validate_post(post_data):
                        yield post_data
                        count += 1
                    else:
                        logger.warning(f"Invalid submission: {submission.id}")

                except Exception as e:
                    logger.error(f"Error transforming submission {submission.id}: {e}")
                    continue

            logger.info(f"Fetched {count} submissions from r/{subreddit}")

            # Rate limiting
            time.sleep(self.batch_delay)

        except Exception as e:
            logger.error(f"Error fetching submissions: {e}")
            raise

    def fetch_comments(self, subreddit, start_ts, end_ts, limit=1000):
        """
        Fetch comments for a subreddit within a time range
        Returns generator of transformed comments
        """
        logger.info(f"Fetching comments from r/{subreddit} "
                   f"between {start_ts} and {end_ts}")

        try:
            comments = self.api.search_comments(
                subreddit=subreddit,
                after=start_ts,
                before=end_ts,
                limit=limit,
                filter=['id', 'body', 'author', 'created_utc',
                       'score', 'parent_id', 'subreddit']
            )

            count = 0
            for comment in comments:
                try:
                    post_data = self._transform_comment(comment)

                    if validate_post(post_data):
                        yield post_data
                        count += 1
                    else:
                        logger.warning(f"Invalid comment: {comment.id}")

                except Exception as e:
                    logger.error(f"Error transforming comment {comment.id}: {e}")
                    continue

            logger.info(f"Fetched {count} comments from r/{subreddit}")

            # Rate limiting
            time.sleep(self.batch_delay)

        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            raise

    def _transform_submission(self, submission):
        """Transform PSAW submission to standardized format"""
        return {
            "post_id": submission.id,
            "title": getattr(submission, 'title', ''),
            "body": getattr(submission, 'selftext', ''),
            "author": getattr(submission, 'author', '[deleted]'),
            "subreddit": submission.subreddit,
            "created_utc": int(submission.created_utc),
            "score": getattr(submission, 'score', 0),
            "num_comments": getattr(submission, 'num_comments', 0),
            "url": getattr(submission, 'url', ''),
            "type": "submission",
            "source": "psaw",  # Tag as backfill data
            "ingestion_timestamp": datetime.utcnow().isoformat()
        }

    def _transform_comment(self, comment):
        """Transform PSAW comment to standardized format"""
        return {
            "post_id": comment.id,
            "title": "",  # Comments don't have titles
            "body": getattr(comment, 'body', ''),
            "author": getattr(comment, 'author', '[deleted]'),
            "subreddit": comment.subreddit,
            "created_utc": int(comment.created_utc),
            "score": getattr(comment, 'score', 0),
            "parent_id": getattr(comment, 'parent_id', ''),
            "type": "comment",
            "source": "psaw",  # Tag as backfill data
            "ingestion_timestamp": datetime.utcnow().isoformat()
        }
```

---

### Subtask 010.6: Deduplication Logic

**Estimate:** 1 hour

**Description:**
- Implement deduplication to prevent duplicate posts
- Track processed post IDs
- Handle overlap between PRAW and PSAW data

**Acceptance Criteria:**
- Duplicate posts filtered out
- Post ID tracking works
- No duplicate data in Kafka

**Files to Create:**
- `producers/reddit_producer/backfill/deduplicator.py`

**Implementation:**
```python
import os
from pathlib import Path

class Deduplicator:
    def __init__(self, cache_dir="backfill/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.seen_ids = set()
        self.cache_file = self.cache_dir / "seen_post_ids.txt"

        # Load existing IDs
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                self.seen_ids = set(line.strip() for line in f)

    def is_duplicate(self, post_id):
        """Check if post ID has been seen before"""
        return post_id in self.seen_ids

    def mark_seen(self, post_id):
        """Mark post ID as seen"""
        if post_id not in self.seen_ids:
            self.seen_ids.add(post_id)

            # Append to file
            with open(self.cache_file, 'a') as f:
                f.write(f"{post_id}\n")

    def get_unique_post(self, post_data):
        """
        Check if post is unique, mark as seen if it is
        Returns post_data if unique, None if duplicate
        """
        post_id = post_data['post_id']

        if self.is_duplicate(post_id):
            return None

        self.mark_seen(post_id)
        return post_data

    def get_stats(self):
        """Get deduplication statistics"""
        return {
            "total_seen_ids": len(self.seen_ids)
        }

    def clear_cache(self):
        """Clear deduplication cache (use with caution!)"""
        if self.cache_file.exists():
            os.remove(self.cache_file)
        self.seen_ids.clear()
```

---

### Subtask 010.7: Backfill Main Script

**Estimate:** 2 hours

**Description:**
- Create main backfill orchestration script
- Implement batch processing logic
- Integrate checkpoint and deduplication

**Acceptance Criteria:**
- Script runs end-to-end successfully
- Checkpoints saved correctly
- Progress tracked and logged

**Files to Create:**
- `producers/reddit_producer/backfill/backfill_main.py`

**Implementation:**
```python
import yaml
import logging
from pathlib import Path
from psaw_client import PSAWClient
from utils import calculate_date_ranges, format_timestamp
from checkpoint import CheckpointManager
from deduplicator import Deduplicator
from utils.kafka_producer import RedditKafkaProducer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backfill/logs/backfill.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackfillOrchestrator:
    def __init__(self, config_path='backfill/config.yaml'):
        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize components
        self.psaw_client = PSAWClient(self.config)
        self.checkpoint_manager = CheckpointManager(
            self.config['backfill']['checkpoint_dir']
        )
        self.deduplicator = Deduplicator()
        self.kafka_producer = RedditKafkaProducer(self.config)

        # Stats tracking
        self.stats = {
            'total_posts': 0,
            'duplicates': 0,
            'errors': 0,
            'kafka_sent': 0
        }

    def backfill_subreddit(self, subreddit, data_type):
        """Backfill data for a single subreddit and data type"""
        logger.info(f"Starting backfill for r/{subreddit} - {data_type}")

        # Get resume date from checkpoint
        start_date = self.checkpoint_manager.get_resume_date(
            subreddit,
            data_type,
            self.config['backfill']['start_date']
        )
        end_date = self.config['backfill']['end_date']

        logger.info(f"Date range: {start_date} to {end_date}")

        # Calculate date ranges (process day by day)
        date_ranges = calculate_date_ranges(start_date, end_date, batch_days=1)

        for date_range in date_ranges:
            try:
                logger.info(f"Processing {date_range['start_date']} to {date_range['end_date']}")

                # Fetch posts for this date range
                if data_type == 'submissions':
                    posts = self.psaw_client.fetch_submissions(
                        subreddit,
                        date_range['start_ts'],
                        date_range['end_ts'],
                        limit=self.config['backfill']['batch_size']
                    )
                else:  # comments
                    posts = self.psaw_client.fetch_comments(
                        subreddit,
                        date_range['start_ts'],
                        date_range['end_ts'],
                        limit=self.config['backfill']['batch_size']
                    )

                # Process posts
                batch_count = 0
                for post in posts:
                    self.stats['total_posts'] += 1

                    # Deduplication
                    unique_post = self.deduplicator.get_unique_post(post)
                    if not unique_post:
                        self.stats['duplicates'] += 1
                        continue

                    # Send to Kafka
                    try:
                        self.kafka_producer.send_message(
                            message=unique_post,
                            key=unique_post['post_id']
                        )
                        self.stats['kafka_sent'] += 1
                        batch_count += 1

                    except Exception as e:
                        logger.error(f"Kafka send error: {e}")
                        self.stats['errors'] += 1

                logger.info(f"Batch complete: {batch_count} posts sent")

                # Save checkpoint
                self.checkpoint_manager.save_checkpoint(
                    subreddit,
                    data_type,
                    date_range['end_date'],
                    self.stats.copy()
                )

            except Exception as e:
                logger.error(f"Error processing date range {date_range['start_date']}: {e}")
                self.stats['errors'] += 1
                continue

        logger.info(f"Backfill complete for r/{subreddit} - {data_type}")

    def run_full_backfill(self):
        """Run backfill for all configured subreddits and data types"""
        logger.info("Starting full backfill")
        logger.info(f"Subreddits: {self.config['backfill']['subreddits']}")
        logger.info(f"Data types: {self.config['backfill']['data_types']}")

        for subreddit in self.config['backfill']['subreddits']:
            for data_type in self.config['backfill']['data_types']:
                try:
                    self.backfill_subreddit(subreddit, data_type)
                except Exception as e:
                    logger.error(f"Failed backfill for {subreddit}/{data_type}: {e}")
                    continue

        # Final stats
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"Total posts processed: {self.stats['total_posts']}")
        logger.info(f"Duplicates filtered: {self.stats['duplicates']}")
        logger.info(f"Sent to Kafka: {self.stats['kafka_sent']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

        # Cleanup
        self.kafka_producer.flush()
        self.kafka_producer.close()

def main():
    orchestrator = BackfillOrchestrator()
    orchestrator.run_full_backfill()

if __name__ == "__main__":
    main()
```

---

### Subtask 010.8: Resume from Checkpoint Feature

**Estimate:** 30 minutes

**Description:**
- Test checkpoint resume functionality
- Ensure no data loss on interruption
- Verify idempotency

**Acceptance Criteria:**
- Resume works after interruption
- No duplicate data sent
- Checkpoint state accurate

**Test Script:**
```bash
# Start backfill
python backfill/backfill_main.py

# Interrupt after 30 seconds (Ctrl+C)
# Then restart - should resume from checkpoint
python backfill/backfill_main.py
```

---

### Subtask 010.9: Progress Monitoring Script

**Estimate:** 1 hour

**Description:**
- Create script to monitor backfill progress
- Display progress percentage
- Estimate time remaining

**Acceptance Criteria:**
- Progress displayed correctly
- ETA calculated
- Can run while backfill is running

**Files to Create:**
- `producers/reddit_producer/backfill/monitor_progress.py`

**Implementation:**
```python
import json
from pathlib import Path
from datetime import datetime
import time

class BackfillMonitor:
    def __init__(self, checkpoint_dir='backfill/checkpoints'):
        self.checkpoint_dir = Path(checkpoint_dir)

    def get_progress(self):
        """Get progress for all backfill tasks"""
        checkpoints = []

        for file in self.checkpoint_dir.glob("*.json"):
            with open(file, 'r') as f:
                checkpoint = json.load(f)
                checkpoints.append(checkpoint)

        return checkpoints

    def display_progress(self):
        """Display formatted progress"""
        checkpoints = self.get_progress()

        if not checkpoints:
            print("No backfill progress found")
            return

        print("\n" + "=" * 80)
        print("BACKFILL PROGRESS")
        print("=" * 80)

        for cp in checkpoints:
            print(f"\nSubreddit: r/{cp['subreddit']} - Type: {cp['data_type']}")
            print(f"Last processed: {cp['last_processed_date']}")
            print(f"Last updated: {cp['last_updated']}")
            print(f"Stats:")
            for key, value in cp['stats'].items():
                print(f"  {key}: {value}")

        print("=" * 80 + "\n")

def main():
    monitor = BackfillMonitor()

    # Continuous monitoring mode
    try:
        while True:
            monitor.display_progress()
            time.sleep(30)  # Refresh every 30 seconds
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    main()
```

---

### Subtask 010.10: Testing

**Estimate:** 1 hour

**Description:**
- Test backfill with small date range
- Verify data in Kafka
- Test checkpoint and resume
- **[USER TASK]** Manually verify data quality in Kafka UI

**Acceptance Criteria:**
- Test backfill completes successfully
- Data appears in Kafka
- Checkpoints work
- Resume works

**Test Commands:**
```bash
# Test with 1-day backfill
# Edit config.yaml:
# start_date: "2024-10-06"
# end_date: "2024-10-07"

# Run backfill
python backfill/backfill_main.py

# Check Kafka topic
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 \
  --from-beginning \
  --max-messages 10 | jq '.source'

# Should see "psaw" as source
```

---

### Subtask 010.11: Documentation

**Estimate:** 1 hour

**Description:**
- Document backfill process
- Add usage examples
- Document checkpoint management

**Acceptance Criteria:**
- Documentation complete
- Examples provided
- Troubleshooting guide included

**Files to Create:**
- `producers/reddit_producer/backfill/README.md`

**Content:**
```markdown
# Historical Backfill with PSAW

This directory contains scripts for backfilling historical Reddit data using the Pushshift API.

## Quick Start

1. Configure backfill parameters in `config.yaml`
2. Run backfill: `python backfill_main.py`
3. Monitor progress: `python monitor_progress.py`

## Configuration

Edit `config.yaml`:
- Set `start_date` and `end_date`
- Configure `subreddits` list
- Adjust `batch_size` and `batch_delay_seconds`

## Resuming Backfill

Backfill automatically saves checkpoints. If interrupted, simply restart:

```bash
python backfill_main.py
```

It will resume from the last checkpoint.

## Clearing Checkpoints

To restart from scratch:

```bash
rm -rf backfill/checkpoints/*
rm -rf backfill/cache/*
```

## Monitoring

Real-time progress monitoring:

```bash
python monitor_progress.py
```

## Troubleshooting

**Issue:** Rate limit errors
**Solution:** Increase `batch_delay_seconds` in config

**Issue:** Duplicate data
**Solution:** Clear deduplication cache and restart

**Issue:** Missing data
**Solution:** Check checkpoint dates and adjust start_date
```

---

### Subtask 010.12: Performance Optimization

**Estimate:** 1 hour

**Description:**
- Optimize batch sizes for throughput
- Test different delay settings
- Measure backfill performance

**Acceptance Criteria:**
- Optimal batch size determined
- Throughput measured (posts/hour)
- No API violations

**Test different configurations:**
```yaml
# Configuration A: Conservative
batch_size: 500
batch_delay_seconds: 3

# Configuration B: Moderate
batch_size: 1000
batch_delay_seconds: 2

# Configuration C: Aggressive
batch_size: 2000
batch_delay_seconds: 1
```

---

### Subtask 010.13: Estimate Total Backfill Time

**Estimate:** 30 minutes

**Description:**
- Calculate total posts to backfill
- Estimate completion time
- Document expected duration
- **[USER TASK]** Review and approve backfill schedule

**Acceptance Criteria:**
- Estimate calculated
- Schedule documented
- Stakeholders informed

**Calculation:**
```python
# Rough estimates:
# - 4 subreddits
# - 6 months = 180 days
# - Average 1000 submissions/day per subreddit
# - Average 5000 comments/day per subreddit

total_submissions = 4 * 180 * 1000 = 720,000
total_comments = 4 * 180 * 5000 = 3,600,000
total_posts = 4,320,000

# At 1000 posts per batch with 2s delay:
batches = 4,320,000 / 1000 = 4,320 batches
time_seconds = 4,320 * 2 = 8,640 seconds = 2.4 hours

# With API limits and error handling, estimate 4-6 hours total
```

---

### Subtask 010.14: Final Integration Test

**Estimate:** 1 hour

**Description:**
- Run full backfill for 1 week of data
- Verify data quality
- Confirm no duplicates with live data
- **[USER TASK]** Verify backfill data quality

**Acceptance Criteria:**
- Full week backfill successful
- Data quality verified
- No overlap issues with PRAW data

---

## Rollback Plan

If backfill causes issues:

1. **Stop backfill:**
   ```bash
   # Kill the backfill process
   pkill -f backfill_main.py
   ```

2. **Revert Kafka topic (if needed):**
   ```bash
   # Delete and recreate topic (WARNING: deletes all data)
   kafka-topics --bootstrap-server localhost:9092 --delete --topic reddit.posts.raw.v1
   kafka-topics --bootstrap-server localhost:9092 --create --topic reddit.posts.raw.v1 \
     --partitions 6 --replication-factor 1
   ```

3. **Clear checkpoints:**
   ```bash
   rm -rf backfill/checkpoints/*
   rm -rf backfill/cache/*
   ```

---

## Testing Checklist

- [ ] PSAW installed and working
- [ ] Configuration file created
- [ ] Date ranges calculated correctly
- [ ] Checkpoint system tested
- [ ] Deduplication prevents duplicates
- [ ] Data sent to Kafka successfully
- [ ] Source tag "psaw" present in messages
- [ ] Resume from checkpoint works
- [ ] Progress monitoring script works
- [ ] No duplicate data with PRAW stream
- [ ] Performance optimized
- [ ] Total time estimated
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-009: Reddit producer with Kafka integration
- PSAW library understanding

**Blocks:**
- TASK-018: Dataset Collection & Labeling (needs historical data)
- TASK-028: Backfill Airflow DAG

---

## Notes

- Pushshift API may have delays (data is not real-time)
- Some posts may be deleted/removed and not available
- API rate limits are less strict than Reddit API but still apply
- Deduplication cache can grow large (several MB for millions of posts)
- Consider running backfill during off-peak hours
- Monitor Kafka disk space during backfill

---

## Estimated Completion

**Total Time:** 12-14 hours (1.5 days)

**Breakdown:**
- Setup & Configuration: 2 hours
- Implementation: 7 hours
- Testing: 2 hours
- Documentation & Optimization: 3 hours
