#!/usr/bin/env python3
"""
VOZ.vn Crawler for Stress Detection Data Collection

Crawls voz.vn/f/tam-su.17 forum to collect Vietnamese posts.
Stores posts directly in Cassandra for reliable persistence.
Implements resume capability, rate limiting, and progress logging.

Usage:
    python scripts/voz_crawler.py [--target 12000] [--delay 1.0] [--reset]

Requirements:
    - Cassandra running (docker-compose up -d cassandra)
    - Schema created (cassandra/schema/04_voz_raw_posts.cql)
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

# Cassandra imports with Python 3.12+ compatibility
try:
    from cassandra.cluster import Cluster
    from cassandra.query import SimpleStatement
except ImportError:
    print("Installing cassandra-driver...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "cassandra-driver[eventlet]"], check=True)
    from cassandra.cluster import Cluster
    from cassandra.query import SimpleStatement

# Configuration
BASE_URL = "https://voz.vn"
SOURCE = "voz.vn"

# Primary forum - Tâm sự (personal stories/venting) is best for stress content
FORUM_URL = f"{BASE_URL}/f/chuyen-tro-linh-tinh%E2%84%A2.17/"

# Parallel crawling settings
MAX_WORKERS = 5  # Concurrent thread fetches

# Search queries for stress-related threads (Vietnamese)
SEARCH_QUERIES = [
    "stress",
    "trầm cảm",
    "lo âu",
    "áp lực công việc",
    "áp lực học tập",
    "mất ngủ",
    "tâm sự buồn",
    "khủng hoảng",
    "kiệt sức",
    "burnout",
    "chia tay",
    "thất tình",
    "cô đơn",
    "bế tắc",
    "tuyệt vọng",
    "nợ nần",
    "thất nghiệp",
    "mâu thuẫn gia đình",
    "ly hôn",
    "sức khỏe tâm thần",
]

# Cassandra settings
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = "reddit_rt"

# Paths (checkpoint only - data goes to Cassandra)
DATA_DIR = Path("data/raw")
CHECKPOINT_FILE = DATA_DIR / ".voz_checkpoint.json"

# Request settings
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_RETRIES = 3
RETRY_DELAY = 5.0

# Stress keywords for filtering - VERY RELAXED mode (collect as much as possible)
# Posts must contain at least one keyword to be collected
STRESS_KEYWORDS = [
    # === DIRECT STRESS/MENTAL HEALTH ===
    "stress", "trầm cảm", "lo âu", "anxiety", "depression", "panic",
    "kiệt sức", "burnout", "mệt mỏi", "không chịu nổi", "quá tải",
    "tuyệt vọng", "bế tắc", "khủng hoảng", "hoang mang", "rối loạn",
    "mất ngủ", "insomnia", "tâm thần", "tự tử", "muốn chết", "tự hại",
    "trị liệu", "tâm lý", "sức khỏe", "bác sĩ", "thuốc", "điều trị",
    "trầm uất", "u uất", "suy sụp", "gục ngã", "đổ vỡ",

    # === EMOTIONS (expanded) ===
    "buồn", "khóc", "đau khổ", "cô đơn", "thất vọng", "tức giận",
    "chán", "chán nản", "chán đời", "không muốn", "sợ", "lo lắng",
    "áp lực", "mệt", "căng thẳng", "khó chịu", "bực", "ức chế",
    "đau lòng", "xót xa", "tủi thân", "tủi nhục", "nhục nhã",
    "hối hận", "ân hận", "day dứt", "dằn vặt", "tội lỗi",
    "giận", "ghét", "hận", "oán", "ganh tị", "đố kỵ",
    "sợ hãi", "hoảng sợ", "lo sợ", "bất an", "hồi hộp",
    "thương", "nhớ", "tiếc", "nuối tiếc", "luyến tiếc",
    "tuyệt vọng", "vô vọng", "mất hy vọng", "chán sống",
    "cảm xúc", "tâm trạng", "mood", "tinh thần", "mental",

    # === WORK/CAREER (expanded) ===
    "công việc", "deadline", "sếp", "đuổi việc", "sa thải",
    "thất nghiệp", "mất việc", "lương", "đồng nghiệp", "overtime",
    "nghỉ việc", "resign", "nhảy việc", "tìm việc", "phỏng vấn",
    "KPI", "target", "doanh số", "áp lực công việc", "workload",
    "văn phòng", "office", "remote", "WFH", "công ty",
    "thăng tiến", "tăng lương", "giảm lương", "cắt giảm",
    "toxic", "môi trường làm việc", "đồng nghiệp", "team",
    "freelance", "startup", "dự án", "project", "report",

    # === ACADEMIC/EDUCATION (expanded) ===
    "học", "thi", "đại học", "rớt", "điểm", "luận văn", "thesis",
    "trượt", "đỗ", "đậu", "kết quả", "thành tích", "GPA",
    "sinh viên", "học sinh", "trường", "lớp", "giáo viên", "thầy", "cô",
    "bài tập", "assignment", "deadline học", "ôn thi", "tốt nghiệp",
    "du học", "học bổng", "chứng chỉ", "bằng cấp", "IELTS", "TOEIC",
    "gap year", "bỏ học", "nghỉ học", "chuyển trường",
    "áp lực học", "áp lực thi", "stress học",

    # === FINANCIAL (expanded) ===
    "nợ", "tiền", "phá sản", "vay", "chi tiêu", "túng", "thiếu",
    "lãi suất", "ngân hàng", "tín dụng", "credit", "trả góp",
    "đầu tư", "thua lỗ", "lỗ", "mất tiền", "sập", "scam",
    "crypto", "coin", "chứng khoán", "stock", "forex",
    "mua nhà", "thuê nhà", "tiền nhà", "tiền trọ",
    "lương không đủ", "hết tiền", "cháy túi", "kẹt tiền",
    "chi phí", "học phí", "viện phí", "hóa đơn", "bill",
    "nghèo", "khó khăn", "túng thiếu", "chật vật",

    # === RELATIONSHIPS (expanded) ===
    "chia tay", "thất tình", "ly hôn", "ngoại tình", "phản bội",
    "người yêu", "bạn gái", "bạn trai", "vợ", "chồng", "ex",
    "crush", "thích", "yêu", "tình cảm", "tình yêu", "hẹn hò",
    "FA", "độc thân", "single", "kết hôn", "cưới", "đám cưới",
    "ghen", "ghen tuông", "jealous", "nghi ngờ", "tin tưởng",
    "bồ", "người thứ ba", "tiểu tam", "tuesday", "cắm sừng",
    "cold", "lạnh nhạt", "xa cách", "breakup", "chia xa",
    "ghosting", "block", "unfriend", "unfollow",
    "tình một đêm", "ONS", "FWB", "situationship",
    "mối quan hệ", "relationship", "couple", "yêu xa", "LDR",

    # === FAMILY (expanded) ===
    "gia đình", "bố mẹ", "con cái", "mâu thuẫn", "cãi nhau",
    "bạo lực", "bạo hành", "đánh", "chửi", "mắng",
    "ba", "mẹ", "cha", "má", "bà", "ông", "anh", "chị", "em",
    "con", "cháu", "dâu", "rể", "mẹ chồng", "bố chồng",
    "mẹ vợ", "bố vợ", "nhà chồng", "nhà vợ", "sui gia",
    "thừa kế", "di chúc", "chia tài sản", "tranh chấp",
    "nuôi con", "quyền nuôi con", "tiền cấp dưỡng",
    "áp lực gia đình", "kỳ vọng", "so sánh", "con nhà người ta",
    "hôn nhân", "vợ chồng", "gia đạo", "hạnh phúc gia đình",

    # === LIFE EVENTS (expanded) ===
    "qua đời", "mất", "tai nạn", "bệnh", "ốm", "đau",
    "tang", "đám tang", "viếng", "chia buồn", "mất mát",
    "ung thư", "cancer", "HIV", "AIDS", "bệnh nặng", "bệnh viện",
    "phẫu thuật", "mổ", "nhập viện", "cấp cứu", "ICU",
    "chuyển nhà", "chuyển công tác", "xa quê", "xa nhà",
    "kết hôn", "sinh con", "mang thai", "sảy thai", "vô sinh",
    "nghĩa vụ", "quân sự", "đi lính", "xuất ngũ",
    "về hưu", "nghỉ hưu", "tuổi già", "lão hóa",

    # === SOCIAL (expanded) ===
    "bạn bè", "cô lập", "bắt nạt", "ghét", "tẩy chay",
    "bạn thân", "bestie", "friendship", "trust", "tin tưởng",
    "introvert", "extrovert", "ngại giao tiếp", "social anxiety",
    "hội nhóm", "group", "community", "cộng đồng",
    "drama", "gossip", "nói xấu", "đồn đại", "tin đồn",
    "fake friend", "toxic friend", "backstab", "phản bội",
    "peer pressure", "áp lực đồng trang lứa", "FOMO",
    "mạng xã hội", "facebook", "instagram", "tiktok", "social media",

    # === ENVIRONMENT/LIVING ===
    "nhà trọ", "phòng trọ", "ở ghép", "roommate", "hàng xóm",
    "tiếng ồn", "ô nhiễm", "kẹt xe", "tắc đường", "giao thông",
    "thời tiết", "nóng", "lạnh", "mưa", "bão", "lũ",
    "Sài Gòn", "Hà Nội", "thành phố", "quê", "tỉnh lẻ",

    # === HELP-SEEKING (expanded) ===
    "tâm sự", "tư vấn", "giúp", "hỏi", "ý kiến", "advice",
    "làm sao", "nên", "phải làm gì", "xin hỏi", "cho hỏi",
    "ai biết", "ai có kinh nghiệm", "chia sẻ", "share",
    "cần giúp", "help", "SOS", "urgent", "gấp",
    "lời khuyên", "góp ý", "suggest", "recommendation",
    "kinh nghiệm", "experience", "bài học", "lesson",

    # === VIETNAMESE SLANG/COMMON ===
    "vãi", "vcl", "vl", "dm", "đm", "wtf", "omg",
    "ức", "bực", "điên", "khùng", "phát điên", "muốn điên",
    "nản", "chịu không nổi", "hết chịu nổi", "quá sức",
    "khổ", "cực", "vất vả", "gian nan", "khó khăn",
    "thảm", "bi kịch", "éo le", "trớ trêu", "oái oăm",
    "ế", "ế show", "thất bại", "fail", "flop",
    "lạc lõng", "lạc loài", "không ai hiểu", "cô độc",
]

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def contains_stress_keywords(text: str) -> bool:
    """Check if text contains any stress-related keywords."""
    text_lower = text.lower()
    for keyword in STRESS_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def connect_to_cassandra():
    """Connect to Cassandra cluster."""
    logger.info(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")

    # Use eventlet for Python 3.12+ compatibility
    try:
        from cassandra.io.eventletreactor import EventletConnection
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, connection_class=EventletConnection)
    except ImportError:
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)

    session = cluster.connect(CASSANDRA_KEYSPACE)
    logger.info(f"Connected to keyspace: {CASSANDRA_KEYSPACE}")
    return cluster, session


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
                logger.info(f"Loaded checkpoint: page {data.get('last_page', 1)}, {len(data.get('seen_urls', []))} URLs seen")
                return data
            except (json.JSONDecodeError, IOError) as e:
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


class VOZCrawler:
    """Crawler for VOZ.vn tam-su forum with Cassandra storage."""

    def __init__(self, target_posts: int = 12000, delay: float = 1.0):
        self.target_posts = target_posts
        self.delay = delay
        self.session = self._create_session()
        self.checkpoint = Checkpoint(CHECKPOINT_FILE)
        self.posts_collected = self.checkpoint.total_posts
        self.posts_skipped = 0  # Posts without stress keywords
        self.start_time = time.time()

        # Cassandra connection
        self.cluster, self.cassandra = connect_to_cassandra()
        self._prepare_statements()

    def _prepare_statements(self):
        """Prepare Cassandra statements for better performance."""
        self.insert_stmt = self.cassandra.prepare("""
            INSERT INTO voz_raw_posts (post_id, text, timestamp, crawled_at, source, url)
            VALUES (?, ?, ?, ?, ?, ?)
        """)

        self.check_exists_stmt = self.cassandra.prepare("""
            SELECT post_id FROM voz_raw_posts WHERE post_id = ?
        """)

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            # Note: Do not set Accept-Encoding - let requests handle it automatically
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        return session

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch URL with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for {url}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        logger.error(f"Failed to fetch {url} after {MAX_RETRIES} attempts")
        return None

    def _sleep_with_jitter(self):
        """Sleep with random jitter to avoid detection."""
        jitter = random.uniform(0.5, 1.5)
        time.sleep(self.delay * jitter)

    def get_forum_page(self, forum_url: str, page: int = 1) -> Optional[BeautifulSoup]:
        """Fetch a forum listing page."""
        url = f"{forum_url}page-{page}" if page > 1 else forum_url
        html = self._fetch_with_retry(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def search_voz(self, query: str, page: int = 1) -> Optional[BeautifulSoup]:
        """Search VOZ forum for a specific query."""
        # VOZ search uses GET with 'q' parameter
        from urllib.parse import quote
        url = f"{SEARCH_URL}?q={quote(query)}&o=date"
        if page > 1:
            url += f"&page={page}"
        html = self._fetch_with_retry(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def extract_thread_urls_with_titles(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract thread URLs and titles from forum listing page.

        Returns list of (url, title) tuples for pre-filtering by title.
        """
        results = []
        # XenForo 2 uses structItem for thread listings
        for item in soup.select(".structItem--thread"):
            title_elem = item.select_one(".structItem-title a[data-tp-primary]")
            if not title_elem:
                title_elem = item.select_one(".structItem-title a:not(.labelLink)")
            if title_elem and title_elem.get("href"):
                url = urljoin(BASE_URL, title_elem["href"])
                title = title_elem.get_text(strip=True)
                results.append((url, title))
        return results

    def extract_search_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract thread URLs from VOZ search results."""
        urls = []
        # Search results use contentRow class
        for item in soup.select(".contentRow"):
            title_elem = item.select_one(".contentRow-title a")
            if title_elem and title_elem.get("href"):
                href = title_elem["href"]
                # Only get thread URLs (not user profiles, etc.)
                if "/t/" in href:
                    url = urljoin(BASE_URL, href)
                    urls.append(url)
        return urls

    def has_next_search_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page in search results."""
        next_link = soup.select_one(".pageNav-jump--next")
        return next_link is not None

    def extract_post_data(self, url: str) -> Optional[dict]:
        """Extract first post data from a thread page."""
        html = self._fetch_with_retry(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Extract post ID from URL
        match = re.search(r"\.(\d+)/?$", url)
        post_id = match.group(1) if match else None
        if not post_id:
            logger.warning(f"Could not extract post_id from {url}")
            return None

        # Find first post content (XenForo uses article.message for posts)
        first_post = soup.select_one("article.message--post")
        if not first_post:
            first_post = soup.select_one(".message-body")

        if not first_post:
            logger.warning(f"No post content found at {url}")
            return None

        # Extract text content
        content_elem = first_post.select_one(".message-body .bbWrapper")
        if not content_elem:
            content_elem = first_post.select_one(".message-content .bbWrapper")
        if not content_elem:
            content_elem = first_post.select_one(".bbWrapper")

        if not content_elem:
            logger.warning(f"No text content found at {url}")
            return None

        # Clean text: remove quotes, get text only
        for quote in content_elem.select(".bbCodeBlock--quote"):
            quote.decompose()
        for spoiler in content_elem.select(".bbCodeSpoiler"):
            spoiler.decompose()

        text = content_elem.get_text(separator=" ", strip=True)
        if not text:
            logger.warning(f"Empty text content at {url}")
            return None

        # Extract timestamp
        timestamp = None
        time_elem = first_post.select_one("time[datetime]")
        if time_elem:
            timestamp = time_elem.get("datetime")
        if not timestamp:
            time_elem = soup.select_one(".message-date time[datetime]")
            if time_elem:
                timestamp = time_elem.get("datetime")

        return {
            "post_id": post_id,
            "text": text,
            "timestamp": timestamp,
            "source": SOURCE,
            "url": url,
            "crawled_at": datetime.now(timezone.utc),
        }

    def has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page."""
        next_link = soup.select_one(".pageNav-jump--next")
        return next_link is not None

    def save_post_to_cassandra(self, post: dict) -> bool:
        """Save post to Cassandra. Returns True if successful."""
        try:
            # Parse timestamp
            post_timestamp = None
            if post["timestamp"]:
                try:
                    post_timestamp = datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    post_timestamp = None

            # Insert into Cassandra (post_id, text, timestamp, crawled_at, source, url)
            self.cassandra.execute(
                self.insert_stmt,
                (
                    post["post_id"],
                    post["text"],
                    post_timestamp,
                    post["crawled_at"],
                    post["source"],
                    post["url"],
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save post {post['post_id']} to Cassandra: {e}")
            return False

    def log_progress(self):
        """Log progress every 100 posts."""
        elapsed = time.time() - self.start_time
        rate = self.posts_collected / elapsed * 3600 if elapsed > 0 else 0
        logger.info(
            f"Progress: {self.posts_collected}/{self.target_posts} posts "
            f"({self.posts_collected/self.target_posts*100:.1f}%) | "
            f"Rate: {rate:.0f} posts/hour | "
            f"Page: {self.checkpoint.last_page}"
        )

    def _process_thread(self, url: str, title: str) -> Optional[dict]:
        """Process a single thread - fetch and extract if title matches keywords."""
        # Pre-filter by title (skip threads unlikely to be stress-related)
        if not contains_stress_keywords(title):
            return None

        post = self.extract_post_data(url)
        if post and contains_stress_keywords(post["text"]):
            return post
        return None

    def run(self):
        """Main crawl loop - simple sequential crawling, collect all posts with keywords."""
        logger.info(f"Starting VOZ crawler - Target: {self.target_posts} posts")
        logger.info(f"Storage: Cassandra ({CASSANDRA_HOST}:{CASSANDRA_PORT}/{CASSANDRA_KEYSPACE})")
        logger.info(f"Forum: {FORUM_URL}")
        logger.info(f"Workers: {MAX_WORKERS} | Keywords: {len(STRESS_KEYWORDS)}")

        if self.checkpoint.total_posts > 0:
            logger.info(f"Resuming from page {self.checkpoint.last_page} with {self.checkpoint.total_posts} posts")

        seen_urls = self.checkpoint.seen_urls
        page = self.checkpoint.last_page

        try:
            while self.posts_collected < self.target_posts:
                logger.info(f"Fetching page {page}...")

                soup = self.get_forum_page(FORUM_URL, page)
                if not soup:
                    logger.warning(f"Failed to fetch page {page}, retrying...")
                    time.sleep(self.delay * 2)
                    continue

                threads = self.extract_thread_urls_with_titles(soup)
                if not threads:
                    logger.info("No more threads found")
                    break

                # Get new URLs only (no title filtering - fetch all)
                new_threads = [(url, title) for url, title in threads if url not in seen_urls]
                logger.info(f"Page {page}: {len(threads)} threads, {len(new_threads)} new")

                if not new_threads:
                    # All threads on this page already seen, move to next
                    page += 1
                    self.checkpoint.last_page = page
                    continue

                # Parallel fetch all new threads
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
                            if post and contains_stress_keywords(post["text"]):
                                if self.save_post_to_cassandra(post):
                                    self.posts_collected += 1
                                    self.checkpoint.total_posts = self.posts_collected

                                    if self.posts_collected % 25 == 0:
                                        self.log_progress()
                            else:
                                self.posts_skipped += 1
                        except Exception as e:
                            logger.debug(f"Error processing {url}: {e}")

                # Move to next page
                if self.has_next_page(soup):
                    page += 1
                    self.checkpoint.last_page = page
                else:
                    logger.info("Reached last page")
                    break

                # Save checkpoint periodically
                self.checkpoint.save()
                time.sleep(self.delay)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.checkpoint.save()
            self._log_summary()
            self._cleanup()

    def _log_summary(self):
        """Log final summary."""
        elapsed = time.time() - self.start_time
        hours = elapsed / 3600
        total_processed = self.posts_collected + self.posts_skipped
        filter_rate = (self.posts_collected / total_processed * 100) if total_processed > 0 else 0
        logger.info("=" * 60)
        logger.info("Crawl Summary")
        logger.info("=" * 60)
        logger.info(f"Stress posts collected: {self.posts_collected}")
        logger.info(f"Non-stress posts skipped: {self.posts_skipped}")
        logger.info(f"Filter rate: {filter_rate:.1f}% matched stress keywords")
        logger.info(f"Elapsed time: {hours:.2f} hours")
        logger.info(f"Average rate: {self.posts_collected / hours:.0f} posts/hour" if hours > 0 else "N/A")
        logger.info(f"Last page: {self.checkpoint.last_page}")
        logger.info(f"Storage: Cassandra table voz_raw_posts")
        logger.info("=" * 60)

    def _cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'cluster') and self.cluster:
            self.cluster.shutdown()
            logger.info("Cassandra connection closed")


def get_current_count():
    """Get current post count from Cassandra."""
    try:
        cluster, session = connect_to_cassandra()
        result = session.execute("SELECT COUNT(*) FROM voz_raw_posts")
        count = result.one()[0]
        cluster.shutdown()
        return count
    except Exception as e:
        logger.warning(f"Could not get current count: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="VOZ.vn Crawler for Stress Detection")
    parser.add_argument("--target", type=int, default=12000, help="Target number of posts (default: 12000)")
    parser.add_argument("--delay", type=float, default=1.0, help="Base delay between requests in seconds (default: 1.0)")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint and start fresh")
    parser.add_argument("--count", action="store_true", help="Show current post count and exit")
    args = parser.parse_args()

    if args.count:
        count = get_current_count()
        print(f"Current posts in Cassandra: {count}")
        return

    if args.reset:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
            logger.info("Checkpoint reset")
        # Note: Does NOT delete Cassandra data - use cqlsh TRUNCATE if needed

    crawler = VOZCrawler(target_posts=args.target, delay=args.delay)
    crawler.run()


if __name__ == "__main__":
    main()
