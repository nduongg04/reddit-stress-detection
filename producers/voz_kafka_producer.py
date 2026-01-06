#!/usr/bin/env python3
"""
VOZ Kafka Producer - Crawl VOZ.vn and push to Kafka

Crawls voz.vn/f/tam-su.17 forum and publishes posts to Kafka topic.
The Spark streaming pipeline then processes posts with LLM inference.

Flow: VOZ.vn → This Producer → Kafka → Spark → Cassandra → Streamlit

Usage:
    python producers/voz_kafka_producer.py [--target 100] [--delay 1.0] [--reset]
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Kafka imports
try:
    from confluent_kafka import Producer
except ImportError:
    print("Installing confluent-kafka...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "confluent-kafka"], check=True)
    from confluent_kafka import Producer

# Configuration
BASE_URL = "https://voz.vn"
FORUM_URL = f"{BASE_URL}/f/tam-su.17/"
SOURCE = "voz.vn/f/tam-su.17"

# Kafka settings
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "voz.posts.raw.v1")

# Paths
DATA_DIR = Path("data/raw")
CHECKPOINT_FILE = DATA_DIR / ".voz_kafka_checkpoint.json"

# Request settings
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
MAX_RETRIES = 3
MAX_WORKERS = 3

# Stress keywords for filtering
STRESS_KEYWORDS = [
    "stress", "trầm cảm", "lo âu", "áp lực", "mệt mỏi", "kiệt sức",
    "buồn", "khóc", "đau khổ", "cô đơn", "thất vọng", "chán",
    "công việc", "deadline", "sếp", "thất nghiệp", "lương",
    "học", "thi", "điểm", "luận văn", "trượt",
    "nợ", "tiền", "phá sản", "vay", "thiếu",
    "chia tay", "thất tình", "ly hôn", "ngoại tình", "người yêu",
    "gia đình", "bố mẹ", "vợ chồng", "cãi nhau", "mâu thuẫn",
    "bệnh", "đau", "mất ngủ", "bệnh viện",
    "bạn bè", "cô lập", "bắt nạt", "tẩy chay",
    "tâm sự", "giúp", "làm sao", "không biết",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def contains_stress_keywords(text: str) -> bool:
    """Check if text contains stress-related keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in STRESS_KEYWORDS)


class Checkpoint:
    """Manages crawler checkpoint for resume capability."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded checkpoint: page {data.get('last_page', 1)}, {data.get('total_posts', 0)} posts")
                return data
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return {"last_page": 1, "seen_urls": [], "total_posts": 0}

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @property
    def last_page(self) -> int:
        return self.data.get("last_page", 1)

    @last_page.setter
    def last_page(self, value: int):
        self.data["last_page"] = value

    @property
    def seen_urls(self) -> set:
        return set(self.data.get("seen_urls", []))

    def add_url(self, url: str):
        if "seen_urls" not in self.data:
            self.data["seen_urls"] = []
        if url not in self.data["seen_urls"]:
            self.data["seen_urls"].append(url)

    @property
    def total_posts(self) -> int:
        return self.data.get("total_posts", 0)

    @total_posts.setter
    def total_posts(self, value: int):
        self.data["total_posts"] = value


class VOZKafkaProducer:
    """Crawl VOZ.vn and publish to Kafka."""

    def __init__(self, target_posts: int = 100, delay: float = 1.0):
        self.target_posts = target_posts
        self.delay = delay
        self.session = self._create_session()
        self.checkpoint = Checkpoint(CHECKPOINT_FILE)
        self.posts_collected = self.checkpoint.total_posts
        self.start_time = time.time()

        # Kafka producer
        self.producer = self._create_kafka_producer()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        })
        return session

    def _create_kafka_producer(self) -> Producer:
        config = {
            "bootstrap.servers": KAFKA_SERVERS,
            "client.id": "voz-crawler-producer",
            "acks": "all",
            "retries": 3,
            "batch.size": 16384,
            "linger.ms": 100,
            "compression.type": "snappy",
        }
        logger.info(f"Connecting to Kafka: {KAFKA_SERVERS}")
        return Producer(config)

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 * (attempt + 1))
        return None

    def get_forum_page(self, page: int = 1) -> Optional[BeautifulSoup]:
        url = f"{FORUM_URL}page-{page}" if page > 1 else FORUM_URL
        html = self._fetch_with_retry(url)
        return BeautifulSoup(html, "html.parser") if html else None

    def extract_thread_urls(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract (url, title) tuples from forum page."""
        results = []
        for item in soup.select(".structItem--thread"):
            title_elem = item.select_one(".structItem-title a[data-tp-primary]")
            if not title_elem:
                title_elem = item.select_one(".structItem-title a:not(.labelLink)")
            if title_elem and title_elem.get("href"):
                url = urljoin(BASE_URL, title_elem["href"])
                title = title_elem.get_text(strip=True)
                results.append((url, title))
        return results

    def extract_post_data(self, url: str) -> Optional[dict]:
        """Extract first post from thread."""
        html = self._fetch_with_retry(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Extract post ID
        match = re.search(r"\.(\d+)/?$", url)
        post_id = match.group(1) if match else None
        if not post_id:
            return None

        # Find first post
        first_post = soup.select_one("article.message--post")
        if not first_post:
            return None

        # Extract text
        content_elem = first_post.select_one(".message-body .bbWrapper")
        if not content_elem:
            content_elem = first_post.select_one(".bbWrapper")
        if not content_elem:
            return None

        # Clean text
        for quote in content_elem.select(".bbCodeBlock--quote"):
            quote.decompose()

        text = content_elem.get_text(separator=" ", strip=True)
        if not text or len(text) < 50:
            return None

        # Extract timestamp
        timestamp = None
        time_elem = first_post.select_one("time[datetime]")
        if time_elem:
            timestamp = time_elem.get("datetime")

        return {
            "post_id": post_id,
            "text": text,
            "url": url,
            "source": SOURCE,
            "timestamp": timestamp,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }

    def has_next_page(self, soup: BeautifulSoup) -> bool:
        return soup.select_one(".pageNav-jump--next") is not None

    def publish_to_kafka(self, post: dict):
        """Publish post to Kafka topic."""
        self.producer.produce(
            KAFKA_TOPIC,
            key=post["post_id"].encode("utf-8"),
            value=json.dumps(post, ensure_ascii=False).encode("utf-8"),
            callback=lambda err, msg: logger.error(f"Kafka error: {err}") if err else None,
        )

    def log_progress(self):
        elapsed = time.time() - self.start_time
        rate = self.posts_collected / elapsed * 60 if elapsed > 0 else 0
        if self.target_posts >= 999999999:
            # Continuous mode
            logger.info(
                f"Published: {self.posts_collected} posts | "
                f"Rate: {rate:.1f}/min | Page: {self.checkpoint.last_page}"
            )
        else:
            logger.info(
                f"Progress: {self.posts_collected}/{self.target_posts} "
                f"({self.posts_collected/self.target_posts*100:.1f}%) | "
                f"Rate: {rate:.1f}/min | Page: {self.checkpoint.last_page}"
            )

    def run(self):
        """Main crawl loop."""
        logger.info("=" * 60)
        logger.info("VOZ Kafka Producer")
        logger.info("=" * 60)
        if self.target_posts >= 999999999:
            logger.info("Mode: CONTINUOUS (Ctrl+C to stop)")
        else:
            logger.info(f"Target: {self.target_posts} posts")
        logger.info(f"Kafka: {KAFKA_SERVERS} → {KAFKA_TOPIC}")
        logger.info(f"Forum: {FORUM_URL}")
        logger.info("=" * 60)

        seen_urls = self.checkpoint.seen_urls
        page = self.checkpoint.last_page

        try:
            while self.posts_collected < self.target_posts:
                logger.info(f"Fetching page {page}...")

                soup = self.get_forum_page(page)
                if not soup:
                    time.sleep(self.delay * 2)
                    continue

                threads = self.extract_thread_urls(soup)
                new_threads = [(url, title) for url, title in threads if url not in seen_urls]

                logger.info(f"Page {page}: {len(threads)} threads, {len(new_threads)} new")

                if not new_threads:
                    page += 1
                    self.checkpoint.last_page = page
                    continue

                # Process threads in parallel
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(self.extract_post_data, url): (url, title)
                        for url, title in new_threads
                    }

                    for future in as_completed(futures):
                        url, title = futures[future]
                        seen_urls.add(url)
                        self.checkpoint.add_url(url)

                        try:
                            post = future.result()
                            if post:
                                self.publish_to_kafka(post)
                                self.posts_collected += 1
                                self.checkpoint.total_posts = self.posts_collected

                                if self.posts_collected % 10 == 0:
                                    self.log_progress()
                                    self.producer.flush()

                                if self.posts_collected >= self.target_posts:
                                    break
                        except Exception as e:
                            logger.debug(f"Error: {e}")

                # Next page
                if self.has_next_page(soup):
                    page += 1
                    self.checkpoint.last_page = page
                else:
                    logger.info("Reached last page")
                    break

                self.checkpoint.save()
                time.sleep(self.delay + random.uniform(0.5, 1.5))

        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.producer.flush()
            self.checkpoint.save()
            self._log_summary()

    def _log_summary(self):
        elapsed = time.time() - self.start_time
        logger.info("=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)
        logger.info(f"Posts published: {self.posts_collected}")
        logger.info(f"Time: {elapsed/60:.1f} minutes")
        logger.info(f"Rate: {self.posts_collected/elapsed*60:.1f} posts/min")
        logger.info(f"Kafka topic: {KAFKA_TOPIC}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="VOZ Kafka Producer")
    parser.add_argument("--target", type=int, default=100, help="Target posts (default: 100)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between pages (default: 1.0)")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint")
    parser.add_argument("--continuous", action="store_true", help="Run continuously until stopped")
    args = parser.parse_args()

    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("Checkpoint reset")

    # Continuous mode: set very high target
    target = 999999999 if args.continuous else args.target

    producer = VOZKafkaProducer(target_posts=target, delay=args.delay)
    producer.run()


if __name__ == "__main__":
    main()
