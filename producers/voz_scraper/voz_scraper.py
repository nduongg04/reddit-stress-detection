"""
Vozforums.com Web Scraper - Simple version with CloudFlare bypass
"""
import cloudscraper
from bs4 import BeautifulSoup
import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin
from pathlib import Path

logger = logging.getLogger(__name__)


class VozScraper:
    """Scraper for vozforums.com"""
    
    BASE_URL = "https://voz.vn"
    
    # Target forums (expanded - removing broken forums, adding discovered ones)
    TARGET_FORUMS = [
        ("tam-su-cuoc-song.17", "Tâm sự cuộc sống"),
        ("hoc-duong.82", "Học đường"),
        ("gia-dinh-hon-nhan.95", "Gia đình hôn nhân"),
        ("tinh-yeu.87", "Tình yêu"),
        # New forums discovered via systematic search (IDs 1-150)
        ("chuyen-tro-linh-tinh%E2%84%A2.17", "Chuyện trò linh tinh"),  # Casual chat/life discussions
        ("kinh-te-luat.92", "Kinh tế / Luật"),  # Economics/Law - financial stress
        ("tien-%C4%91ien-tu.94", "Tiền điện tử"),  # Cryptocurrency - financial stress
    ]
    
    # Stress keywords
    STRESS_KEYWORDS = [
        "căng thẳng", "stress", "trầm cảm", "lo âu", "buồn", "chán nản",
        "tuyệt vọng", "áp lực", "mệt mỏi", "thất bại", "deadline", "cô đơn"
    ]
    
    def __init__(self, config: dict, kafka_producer=None):
        self.config = config
        self.kafka_producer = kafka_producer
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        self.processed_threads = set()
        self.collected_count = 0
        self.delay = config.get('scraper', {}).get('delay_seconds', 1.5)
        logger.info("✓ VozScraper initialized")
    
    def _contains_stress_keywords(self, text: str) -> bool:
        """Check if text contains stress keywords"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.STRESS_KEYWORDS)
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page with CloudFlare bypass"""
        try:
            response = self.scraper.get(url, timeout=30)
            response.raise_for_status()
            time.sleep(self.delay)
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_thread_info(self, soup: BeautifulSoup, forum_name: str) -> Optional[Dict]:
        """Extract thread information"""
        try:
            title_elem = soup.find('h1', class_='p-title-value')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            
            first_post = soup.find('article', class_='message--post')
            if not first_post:
                return None
            
            content_elem = first_post.find('div', class_='bbWrapper')
            if not content_elem:
                return None
            content = content_elem.get_text(strip=True)
            
            author_elem = first_post.find('a', class_='username')
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"
            
            time_elem = first_post.find('time')
            timestamp = int(time.time())  # Default to current time
            if time_elem and time_elem.get('data-time'):
                try:
                    timestamp = int(time_elem.get('data-time'))
                except (ValueError, TypeError):
                    pass  # Use default timestamp
            
            thread_id = first_post.get('data-content', str(hash(title)))
            
            canonical = soup.find('link', rel='canonical')
            url = canonical['href'] if canonical else ''
            
            full_text = f"{title} {content}"
            
            return {
                'thread_id': thread_id,
                'title': title,
                'content': content,
                'author': author,
                'timestamp': timestamp,
                'forum': forum_name,
                'url': url,
                'full_text': full_text
            }
        except Exception as e:
            logger.error(f"Error extracting thread: {e}")
            return None
    
    def _get_thread_urls(self, forum_id: str, max_pages: int = 10) -> List[str]:
        """Get thread URLs from forum"""
        thread_urls = []
        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/f/{forum_id}/page-{page}" if page > 1 else f"{self.BASE_URL}/f/{forum_id}/"
            logger.info(f"Fetching forum page {page}: {url}")
            
            soup = self._fetch_page(url)
            if not soup:
                break
            
            threads = soup.find_all('div', class_='structItem--thread')
            if not threads:
                logger.info(f"No threads on page {page}")
                break
            
            for item in threads:
                link = item.find('a', {'data-preview-url': True})
                if link:
                    thread_urls.append(urljoin(self.BASE_URL, link['href']))
            
            logger.info(f"Found {len(threads)} threads on page {page}")
        
        return thread_urls
    
    def _scrape_thread(self, thread_url: str, forum_name: str) -> Optional[Dict]:
        """Scrape single thread"""
        if thread_url in self.processed_threads:
            return None
        
        logger.debug(f"Scraping: {thread_url}")
        soup = self._fetch_page(thread_url)
        if not soup:
            return None
        
        thread_info = self._extract_thread_info(soup, forum_name)
        if not thread_info:
            return None
        
        # Skip keyword filtering - these forums are already stress-related
        # Will filter by keywords during preprocessing phase instead
        
        self.processed_threads.add(thread_url)
        return thread_info
    
    def _transform_to_kafka_format(self, thread_data: Dict) -> Dict:
        """Transform to Kafka format"""
        return {
            'post_id': thread_data['thread_id'],
            'title': thread_data['title'],
            'selftext': thread_data['content'],
            'author': thread_data['author'],
            'created_utc': thread_data['timestamp'],
            'subreddit': 'vozforums',
            'score': 0,
            'num_comments': 0,
            'url': thread_data['url'],
            'source': 'vozforums.com',
            'forum': thread_data['forum'],
            'search_category': 'stress',
            'collected_at': datetime.utcnow().isoformat()
        }
    
    def scrape_vozforums(self, target_posts: int = 10000) -> List[Dict]:
        """Main scraping function"""
        logger.info(f"Starting voz scraping (target: {target_posts} posts)")
        all_posts = []
        
        posts_per_forum = target_posts // len(self.TARGET_FORUMS)
        # Increase max_pages to go deeper into forum history
        # Each page has ~20 threads, so for 5000 posts we need ~250 pages per forum
        max_pages_per_forum = (posts_per_forum // 20) + 100  # Increased from +5 to +100
        
        for forum_id, forum_name in self.TARGET_FORUMS:
            if self.collected_count >= target_posts:
                break
            
            logger.info(f"Scraping forum: {forum_name}")
            thread_urls = self._get_thread_urls(forum_id, max_pages_per_forum)
            logger.info(f"Found {len(thread_urls)} threads in {forum_name}")
            
            # Filter out already processed URLs
            new_urls = [url for url in thread_urls if url not in self.processed_threads]
            if len(new_urls) < len(thread_urls):
                skipped = len(thread_urls) - len(new_urls)
                logger.info(f"Skipping {skipped} already crawled threads, {len(new_urls)} new threads to process")
            
            for url in new_urls:
                if self.collected_count >= target_posts:
                    break
                
                # Mark as processed
                self.processed_threads.add(url)
                
                thread_data = self._scrape_thread(url, forum_name)
                if thread_data:
                    kafka_message = self._transform_to_kafka_format(thread_data)
                    all_posts.append(kafka_message)
                    self.collected_count += 1
                    
                    if self.kafka_producer:
                        self.kafka_producer.send_message(kafka_message)
                    
                    if self.collected_count % 10 == 0:
                        logger.info(f"Progress: {self.collected_count}/{target_posts} ({(self.collected_count/target_posts)*100:.1f}%)")
        
        logger.info(f"Scraping complete: {self.collected_count} posts")
        return all_posts
    
    def save_to_file(self, posts: List[Dict], output_file: str):
        """Save posts to JSON"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(posts)} posts to {output_file}")
