"""
Reddit stream using PRAW to collect live submissions and comments
"""
import praw
import logging
from config.secrets import RedditCredentials
from config.vietnamese_keywords import get_stress_search_query, get_non_stress_search_query, get_vozforums_stress_query
from utils.schema import transform_submission, transform_comment, validate_post
from utils.rate_limiter import RateLimiter
from utils.backoff import ExponentialBackoff
from utils.circuit_breaker import CircuitBreaker
from utils.errors import RetryableError, PermanentError, classify_error
from utils.logging_context import set_correlation_id, clear_correlation_id, get_correlation_id
from utils.error_metrics import record_error, record_retry, update_circuit_breaker_state
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from prawcore.exceptions import ServerError, RequestException, ResponseException
from langdetect import detect, LangDetectException
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

logger = logging.getLogger(__name__)


class RedditStream:
    """
    Stream Reddit submissions and comments using PRAW
    """

    def __init__(self, config, kafka_producer):
        """
        Initialize Reddit stream

        Args:
            config: Configuration dictionary
            kafka_producer: RedditKafkaProducer instance
        """
        # Validate credentials
        RedditCredentials.validate()

        # Initialize PRAW with improved connection settings
        self.reddit = praw.Reddit(
            client_id=RedditCredentials.CLIENT_ID,
            client_secret=RedditCredentials.CLIENT_SECRET,
            user_agent=RedditCredentials.USER_AGENT,
            requestor_kwargs={
                'timeout': 30,
                'session': None  # Let PRAW create a new session
            },
            ratelimit_seconds=600  # Wait 10 minutes if rate limited
        )

        # Test authentication
        try:
            logger.info(f"Authenticated as: {self.reddit.user.me() or 'anonymous'}")
        except Exception as e:
            logger.warning(f"Could not fetch user info (may be running without auth): {e}")

        self.config = config
        self.kafka_producer = kafka_producer

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=config['rate_limiting']['requests_per_minute'],
            burst_limit=config['rate_limiting']['burst_limit'],
            window_minutes=config['rate_limiting'].get('window_minutes', 10)
        )

        # Initialize error handling components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config['error_handling']['circuit_breaker']['failure_threshold'],
            recovery_timeout=config['error_handling']['circuit_breaker']['recovery_timeout_seconds'],
            success_threshold=config['error_handling']['circuit_breaker']['success_threshold']
        )

        # Build subreddit string: "anxiety+depression+stress+mentalhealth"
        self.subreddit_str = '+'.join(config['reddit']['subreddits'])
        self.subreddit = self.reddit.subreddit(self.subreddit_str)

        self.post_count = 0
        self.submission_count = 0
        self.comment_count = 0
        self.skip_existing = config['reddit'].get('skip_existing', True)
        self.posts_per_minute = config['reddit'].get('posts_per_minute', 10)
        self.shutdown_event = None  # Will be set from main

        # Track processed post IDs to avoid duplicates
        self.processed_ids = set()

        # Thread pool for parallel processing
        self.max_workers = 8  # Parallel processing threads

        logger.info(
            f"Reddit stream initialized for r/{self.subreddit_str}, "
            f"skip_existing={self.skip_existing}, "
            f"posts_per_minute={self.posts_per_minute}, "
            f"rate_limit={config['rate_limiting']['requests_per_minute']} QPM "
            f"(burst: {config['rate_limiting']['burst_limit']})"
        )

    def check_rate_limit_headers(self):
        """
        Check Reddit API rate limit headers from last request.
        Updates rate limiter with current API state.
        """
        try:
            # Access PRAW's internal session to get last response headers
            if hasattr(self.reddit, '_core') and hasattr(self.reddit._core, '_rate_limiter'):
                headers = {}
                # PRAW tracks rate limit info internally
                rl = self.reddit._core._rate_limiter
                if hasattr(rl, 'remaining'):
                    headers['x-ratelimit-remaining'] = str(rl.remaining)
                if hasattr(rl, 'used'):
                    headers['x-ratelimit-used'] = str(rl.used)
                if hasattr(rl, 'reset_timestamp'):
                    import time
                    headers['x-ratelimit-reset'] = str(max(0, rl.reset_timestamp - time.time()))

                if headers:
                    self.rate_limiter.update_from_headers(headers)
        except Exception as e:
            logger.debug(f"Could not check rate limit headers: {e}")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ServerError, RequestException, ResponseException))
    )
    def stream_submissions(self):
        """
        Fetch new submissions from subreddits with parallel processing.

        Optimizations:
        - Parallel submission processing with ThreadPoolExecutor
        - Increased batch size
        - Reduced delays between batches

        This method runs indefinitely and fetches posts_per_minute posts every minute
        """
        logger.info(
            f"Starting submission stream (OPTIMIZED) for r/{self.subreddit_str} "
            f"(fetching up to {self.posts_per_minute} posts/minute, {self.max_workers} parallel workers)"
        )

        try:
            while True:
                # Calculate delay between fetches
                delay_seconds = 60.0 / self.posts_per_minute if self.posts_per_minute > 0 else 2.0

                # Fetch latest submissions (limit to posts_per_minute)
                logger.debug(f"Fetching up to {self.posts_per_minute} new submissions...")

                submissions = list(self.subreddit.new(limit=self.posts_per_minute))

                # Filter out already processed submissions
                new_submissions = [
                    sub for sub in submissions
                    if sub.id not in self.processed_ids
                ]

                if not new_submissions:
                    logger.debug(f"No new posts in this batch ({len(submissions)} checked)")
                    time.sleep(delay_seconds)
                    continue

                # Limit the size of processed_ids to prevent memory issues
                if len(self.processed_ids) > 10000:
                    self.processed_ids = set(list(self.processed_ids)[-5000:])

                # Process submissions in parallel
                processed_this_batch = 0
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_submission = {
                        executor.submit(self.process_single_submission, sub): sub
                        for sub in new_submissions
                    }

                    for future in as_completed(future_to_submission):
                        submission = future_to_submission[future]
                        try:
                            success, _ = future.result()
                            if success:
                                processed_this_batch += 1

                                if self.submission_count % 10 == 0:
                                    logger.info(
                                        f"Total processed: {self.submission_count} submissions "
                                        f"({self.post_count} total posts)"
                                    )

                                    # Check Reddit API headers
                                    self.check_rate_limit_headers()

                                    # Log rate limiter stats
                                    stats = self.rate_limiter.get_stats()
                                    logger.info(
                                        f"API Rate: {stats['current_requests_per_minute']}/min (burst), "
                                        f"10-min avg: {stats['average_qpm_10min']:.1f}/{stats['max_requests_per_minute']} QPM "
                                        f"({stats['utilization_percent_10min']:.1f}% utilized)"
                                    )

                                    # Log Reddit API info if available
                                    if 'api_remaining' in stats:
                                        logger.info(
                                            f"Reddit API: {stats['api_used']} used, "
                                            f"{stats['api_remaining']} remaining, "
                                            f"resets in {stats['api_reset_seconds']}s"
                                        )

                                    # Update circuit breaker state metric
                                    update_circuit_breaker_state(self.circuit_breaker.get_state())

                        except Exception as e:
                            logger.error(f"Error processing future for {submission.id}: {e}")

                        # Check for shutdown signal
                        if self.shutdown_event and self.shutdown_event.is_set():
                            logger.info("Shutdown signal received, stopping submission stream")
                            return

                # Log batch summary
                if processed_this_batch > 0:
                    logger.info(
                        f"Batch complete: {processed_this_batch} new posts published "
                        f"(skipped {len(submissions) - len(new_submissions)} duplicates)"
                    )

                # Wait before next batch (spread posts evenly across the minute)
                logger.debug(f"Waiting {delay_seconds:.1f}s before next batch...")
                time.sleep(delay_seconds)

        except Exception as e:
            logger.error(f"Fatal error in submission stream: {e}", exc_info=True)
            raise

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ServerError, RequestException, ResponseException))
    )
    def stream_comments(self):
        """
        Stream new comments from subreddits

        This method runs indefinitely and processes new comments as they appear
        """
        logger.info(f"Starting comment stream for r/{self.subreddit_str}")

        try:
            for comment in self.subreddit.stream.comments(
                skip_existing=self.skip_existing,
                pause_after=-1
            ):
                if comment is None:
                    # No new comments, wait a bit
                    time.sleep(1)
                    continue

                # Set correlation ID for tracing
                correlation_id = set_correlation_id()

                try:
                    # Respect rate limits
                    self.rate_limiter.wait_if_needed()

                    # Transform comment to standard format
                    post_data = transform_comment(comment)
                    post_data['correlation_id'] = correlation_id

                    # Validate post data
                    if validate_post(post_data):
                        # Send to Kafka with circuit breaker protection
                        try:
                            self.circuit_breaker.call(
                                self.kafka_producer.send_message,
                                message=post_data,
                                key=post_data['post_id']
                            )

                            self.post_count += 1
                            self.comment_count += 1

                            if self.comment_count % 50 == 0:
                                logger.info(
                                    f"Processed {self.comment_count} comments "
                                    f"(total: {self.post_count} posts)"
                                )

                                # Log rate limiter stats
                                stats = self.rate_limiter.get_stats()
                                logger.debug(f"Rate limiter: {stats}")

                                # Update circuit breaker state metric
                                update_circuit_breaker_state(self.circuit_breaker.get_state())

                        except Exception as kafka_error:
                            record_error(kafka_error, "kafka_send")
                            self.kafka_producer.send_to_dlq(post_data, kafka_error, correlation_id)

                    else:
                        logger.warning(
                            f"Invalid comment: {post_data.get('post_id', 'unknown')}, "
                            f"subreddit: {post_data.get('subreddit', 'unknown')}"
                        )
                        self.kafka_producer.send_to_dlq(post_data, "validation_failed", correlation_id)

                except Exception as e:
                    logger.error(f"Error processing comment {comment.id}: {e}", exc_info=True)
                    record_error(e, "comment_processing")
                    # Continue processing next comment
                    continue

                finally:
                    clear_correlation_id()

                # Check for shutdown signal
                if self.shutdown_event and self.shutdown_event.is_set():
                    logger.info("Shutdown signal received, stopping comment stream")
                    break

        except Exception as e:
            logger.error(f"Fatal error in comment stream: {e}", exc_info=True)
            raise

    def is_vietnamese(self, text: str, min_length: int = 20) -> bool:
        """
        Detect if text is Vietnamese using langdetect + Vietnamese diacritic validation.

        Strict filter to block English posts:
        1. langdetect must detect 'vi'
        2. Text must contain Vietnamese diacritics
        3. Text must not be majority English words

        Args:
            text: Text to check
            min_length: Minimum text length for reliable detection

        Returns:
            True if text is Vietnamese, False otherwise
        """
        if not text or len(text) < min_length:
            return False

        # Step 1: langdetect must detect Vietnamese
        try:
            lang = detect(text)
            if lang != 'vi':
                return False
        except LangDetectException:
            return False

        # Step 2: STRICT - Must contain Vietnamese diacritics (tone marks)
        # Vietnamese diacritics: à á ả ã ạ ă ắ ằ ẳ ẵ ặ â ấ ầ ẩ ẫ ậ
        #                        è é ẻ ẽ ẹ ê ế ề ể ễ ệ
        #                        ì í ỉ ĩ ị
        #                        ò ó ỏ õ ọ ô ố ồ ổ ỗ ộ ơ ớ ờ ở ỡ ợ
        #                        ù ú ủ ũ ụ ư ứ ừ ử ữ ự
        #                        ỳ ý ỷ ỹ ỵ
        #                        đ
        vietnamese_chars = set('àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ')
        vietnamese_chars.update('ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ')

        has_vietnamese_diacritics = any(char in vietnamese_chars for char in text)

        if not has_vietnamese_diacritics:
            logger.debug(f"Rejected: No Vietnamese diacritics - {text[:50]}...")
            return False

        # Step 3: Check that it's not majority English
        # Count words that are purely ASCII (likely English)
        words = text.split()
        ascii_words = sum(1 for word in words if word.isascii() and word.isalpha())
        total_words = len(words)

        if total_words > 0:
            english_ratio = ascii_words / total_words
            if english_ratio > 0.5:  # More than 50% ASCII words = likely English
                logger.debug(f"Rejected: {english_ratio:.0%} English words - {text[:50]}...")
                return False

        # Step 4: EXTRA STRICT - Require minimum Vietnamese diacritic density
        # At least 5% of characters must be Vietnamese diacritics
        vietnamese_char_count = sum(1 for char in text if char in vietnamese_chars)
        text_length = len(text.replace(' ', ''))  # Exclude spaces

        if text_length > 0:
            vietnamese_density = vietnamese_char_count / text_length
            if vietnamese_density < 0.05:  # Less than 5% Vietnamese chars
                logger.debug(f"Rejected: Only {vietnamese_density:.1%} Vietnamese characters - {text[:50]}...")
                return False

        return True

    def process_single_submission(self, submission, search_type: str = None) -> Tuple[bool, str]:
        """
        Process a single submission (used for parallel processing).

        Args:
            submission: PRAW submission object
            search_type: Optional category label ("stress" or "non-stress")

        Returns:
            Tuple of (success: bool, category: str)
        """
        # Skip if already processed
        if submission.id in self.processed_ids:
            return (False, search_type)

        # Add to processed set
        self.processed_ids.add(submission.id)

        # Set correlation ID
        correlation_id = set_correlation_id()

        try:
            # Respect rate limits
            self.rate_limiter.wait_if_needed()

            # Transform submission
            post_data = transform_submission(submission)
            post_data['correlation_id'] = correlation_id
            if search_type:
                post_data['search_category'] = search_type

            # Validate
            if validate_post(post_data):
                try:
                    self.circuit_breaker.call(
                        self.kafka_producer.send_message,
                        message=post_data,
                        key=post_data['post_id']
                    )

                    self.post_count += 1
                    self.submission_count += 1

                    logger.info(
                        f"Published post {submission.id} from r/{submission.subreddit.display_name}"
                    )

                    return (True, search_type)

                except Exception as kafka_error:
                    record_error(kafka_error, "kafka_send")
                    self.kafka_producer.send_to_dlq(post_data, kafka_error, correlation_id)
                    return (False, search_type)

            else:
                logger.warning(f"Invalid submission: {post_data.get('post_id', 'unknown')}")
                self.kafka_producer.send_to_dlq(post_data, "validation_failed", correlation_id)
                return (False, search_type)

        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)
            record_error(e, "submission_processing")
            return (False, search_type)

        finally:
            clear_correlation_id()

    def fetch_and_filter_batch(self, keyword: str, search_type: str, sort_method: str, limit: int = 500) -> List:
        """
        Fetch and filter submissions for Vietnamese content in parallel.

        Args:
            keyword: Search keyword
            search_type: "stress" or "non-stress"
            sort_method: Reddit sort method
            limit: Number of posts to fetch

        Returns:
            List of Vietnamese submissions
        """
        query = f'"{keyword}"'
        logger.debug(f"Fetching {limit} posts for '{keyword}' ({search_type}, {sort_method})")

        # Fetch submissions
        submissions = list(
            self.reddit.subreddit("all").search(
                query,
                sort=sort_method,
                time_filter="all",
                limit=limit
            )
        )

        # Parallel language detection
        vietnamese_submissions = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_submission = {
                executor.submit(self.is_vietnamese, sub.title): sub
                for sub in submissions
                if sub.id not in self.processed_ids
            }

            for future in as_completed(future_to_submission):
                submission = future_to_submission[future]
                try:
                    if future.result():
                        vietnamese_submissions.append(submission)
                except Exception as e:
                    logger.error(f"Error checking language for {submission.id}: {e}")

        logger.debug(f"Found {len(vietnamese_submissions)} Vietnamese posts out of {len(submissions)}")
        return vietnamese_submissions

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ServerError, RequestException, ResponseException))
    )
    def stream_vietnamese_keywords(self):
        """
        Collect Vietnamese posts using keyword search with parallel processing.

        Optimizations:
        - Parallel language detection
        - Batch processing with ThreadPoolExecutor
        - Larger fetch batches (300 posts)
        - Reduced sleep delays (2s instead of 5s)

        Target: 5,000 posts (2,500 stress + 2,500 non-stress)
        """
        from config.vietnamese_keywords import STRESS_KEYWORDS_VI, NON_STRESS_KEYWORDS_VI

        target_total = self.config['reddit'].get('target_posts', 5000)
        target_per_category = target_total // 2

        stress_count = 0
        non_stress_count = 0

        # Track keyword index for rotation
        stress_keyword_idx = 0
        non_stress_keyword_idx = 0

        logger.info(
            f"Starting Vietnamese keyword collection (OPTIMIZED for 100 QPM) "
            f"(target: {target_per_category} stress + {target_per_category} non-stress posts)"
        )
        logger.info(
            f"Strategy: Parallel processing with {self.max_workers} workers, "
            f"500 posts/batch, 100 QPM rate limit, rotating through {len(STRESS_KEYWORDS_VI)} stress "
            f"and {len(NON_STRESS_KEYWORDS_VI)} non-stress keywords"
        )

        try:
            while stress_count < target_per_category or non_stress_count < target_per_category:
                # Alternate between stress and non-stress searches
                if stress_count < target_per_category:
                    search_type = "stress"
                    keyword = STRESS_KEYWORDS_VI[stress_keyword_idx % len(STRESS_KEYWORDS_VI)]
                    stress_keyword_idx += 1
                elif non_stress_count < target_per_category:
                    search_type = "non-stress"
                    keyword = NON_STRESS_KEYWORDS_VI[non_stress_keyword_idx % len(NON_STRESS_KEYWORDS_VI)]
                    non_stress_keyword_idx += 1
                else:
                    break

                # Vary sort method to get diverse posts
                sort_methods = ["new", "top", "hot", "relevance"]
                sort_method = sort_methods[stress_keyword_idx % len(sort_methods)] if search_type == "stress" else sort_methods[non_stress_keyword_idx % len(sort_methods)]

                logger.info(
                    f"Searching '{keyword}' ({search_type}, sort={sort_method})... "
                    f"(collected: stress={stress_count}/{target_per_category}, "
                    f"non-stress={non_stress_count}/{target_per_category})"
                )

                # Fetch and filter Vietnamese posts in parallel
                vietnamese_submissions = self.fetch_and_filter_batch(
                    keyword, search_type, sort_method, limit=500
                )

                if not vietnamese_submissions:
                    logger.debug(f"No Vietnamese posts found for '{keyword}'")
                    time.sleep(1)
                    continue

                # Process submissions in parallel
                processed_this_batch = 0
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_submission = {
                        executor.submit(self.process_single_submission, sub, search_type): sub
                        for sub in vietnamese_submissions
                    }

                    for future in as_completed(future_to_submission):
                        submission = future_to_submission[future]
                        try:
                            success, category = future.result()
                            if success:
                                processed_this_batch += 1
                                if category == "stress":
                                    stress_count += 1
                                else:
                                    non_stress_count += 1

                                if processed_this_batch % 10 == 0:
                                    # Check Reddit API headers
                                    self.check_rate_limit_headers()

                                    logger.info(
                                        f"Batch progress: {processed_this_batch} posts - "
                                        f"Total: stress={stress_count}/{target_per_category}, "
                                        f"non-stress={non_stress_count}/{target_per_category}"
                                    )

                                    # Log rate stats
                                    stats = self.rate_limiter.get_stats()
                                    logger.info(
                                        f"Rate: {stats['average_qpm_10min']:.1f}/{stats['max_requests_per_minute']} QPM "
                                        f"({stats['utilization_percent_10min']:.1f}%)"
                                    )

                        except Exception as e:
                            logger.error(f"Error processing future for {submission.id}: {e}")

                        # Check targets
                        if (category == "stress" and stress_count >= target_per_category) or \
                           (category == "non-stress" and non_stress_count >= target_per_category):
                            break

                        # Check shutdown signal
                        if self.shutdown_event and self.shutdown_event.is_set():
                            logger.info("Shutdown signal received")
                            return

                # Log batch summary
                logger.info(
                    f"Batch complete: {processed_this_batch} Vietnamese {search_type} posts collected "
                    f"(out of {len(vietnamese_submissions)} candidates)"
                )

                # Minimal wait time between searches (rate limiter handles throttling)
                logger.debug("Waiting 0.5s before next search batch...")
                time.sleep(0.5)

            logger.info(
                f"✓ Vietnamese collection complete! "
                f"Total: {stress_count + non_stress_count} posts "
                f"(stress: {stress_count}, non-stress: {non_stress_count})"
            )

        except Exception as e:
            logger.error(f"Fatal error in Vietnamese keyword stream: {e}", exc_info=True)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ServerError, RequestException, ResponseException))
    )
    def stream_vozforums_stress(self):
        """
        Collect stress posts from r/vozforums only using Vietnamese keywords.
        Tracks first post date for training data reference.

        Target: 1000 stress posts from r/vozforums
        """
        from config.vietnamese_keywords import VOZFORUMS_STRESS_KEYWORDS
        from datetime import datetime

        target_posts = self.config['reddit'].get('target_posts', 1000)
        collected_count = 0
        first_post_date = None

        vozforums = self.reddit.subreddit("vozforums")
        keyword_idx = 0

        logger.info(
            f"Starting r/vozforums stress collection (target: {target_posts} posts) "
            f"with {len(VOZFORUMS_STRESS_KEYWORDS)} Vietnamese stress keywords"
        )

        try:
            while collected_count < target_posts:
                keyword = VOZFORUMS_STRESS_KEYWORDS[keyword_idx % len(VOZFORUMS_STRESS_KEYWORDS)]
                keyword_idx += 1

                sort_methods = ["new", "top", "hot", "relevance"]
                sort_method = sort_methods[keyword_idx % len(sort_methods)]

                logger.info(
                    f"Searching r/vozforums: '{keyword}' (sort={sort_method}) - "
                    f"collected {collected_count}/{target_posts}"
                )

                # Rate limit check
                self.rate_limiter.wait_if_needed()

                # Search r/vozforums only
                try:
                    submissions = list(vozforums.search(
                        query=keyword,
                        sort=sort_method,
                        time_filter="all",
                        limit=100
                    ))
                except Exception as e:
                    logger.error(f"Search error for '{keyword}': {e}")
                    time.sleep(5)
                    continue

                if not submissions:
                    logger.debug(f"No posts found for '{keyword}'")
                    time.sleep(1)
                    continue

                logger.info(f"Found {len(submissions)} posts for '{keyword}', filtering for Vietnamese...")

                # Filter Vietnamese posts in parallel
                vietnamese_submissions = []

                def check_vietnamese(sub):
                    """Helper to check if submission is Vietnamese"""
                    text = f"{sub.title} {sub.selftext}"
                    return self.is_vietnamese(text)

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {executor.submit(check_vietnamese, sub): sub for sub in submissions}
                    for future in as_completed(futures):
                        sub = futures[future]
                        try:
                            if future.result():
                                vietnamese_submissions.append(sub)
                        except Exception as e:
                            logger.warning(f"Language detection error for post {sub.id}: {e}")

                logger.info(f"After filtering: {len(vietnamese_submissions)} Vietnamese posts")

                if not vietnamese_submissions:
                    logger.info(f"No Vietnamese posts for '{keyword}' after language filtering")
                    time.sleep(1)
                    continue

                # Process submissions
                logger.info(f"Processing {len(vietnamese_submissions)} Vietnamese posts...")
                for sub in vietnamese_submissions:
                    if collected_count >= target_posts:
                        break

                    post_id = sub.id
                    if post_id in self.processed_ids:
                        logger.debug(f"Skipping duplicate post {post_id}")
                        continue

                    try:
                        post_data = transform_submission(sub, search_category=keyword, source="search")

                        if not validate_post(post_data):
                            logger.warning(f"Invalid post {post_id}: validation failed")
                            continue

                        # Track first post date
                        if first_post_date is None:
                            first_post_date = datetime.fromtimestamp(sub.created_utc)
                            logger.info(f"FIRST POST DATE: {first_post_date.isoformat()} (post_id={post_id})")

                        success = self.kafka_producer.send_message(post_data)
                        if success:
                            self.processed_ids.add(post_id)
                            collected_count += 1
                            self.post_count += 1
                            self.submission_count += 1
                            logger.info(f"Published post {post_id} to Kafka (total: {collected_count})")

                            if collected_count % 50 == 0:
                                logger.info(
                                    f"Progress: {collected_count}/{target_posts} posts "
                                    f"(keyword: '{keyword}')"
                                )
                        else:
                            logger.warning(f"Failed to publish post {post_id} to Kafka")
                    except Exception as e:
                        logger.error(f"Error processing {post_id}: {e}")

                time.sleep(0.5)

                # Check rate limit every 10 searches
                if keyword_idx % 10 == 0:
                    self.check_rate_limit_headers()

        except KeyboardInterrupt:
            logger.info("Collection interrupted by user")
        except Exception as e:
            logger.error(f"Error in vozforums stream: {e}")
            raise

        logger.info(
            f"r/vozforums collection complete: {collected_count} posts collected "
            f"(first post date: {first_post_date.isoformat() if first_post_date else 'N/A'})"
        )

    def get_stats(self):
        """
        Get stream statistics

        Returns:
            dict: Statistics
        """
        kafka_stats = self.kafka_producer.get_stats()
        rate_limiter_stats = self.rate_limiter.get_stats()

        return {
            'posts_processed': self.post_count,
            'submissions_processed': self.submission_count,
            'comments_processed': self.comment_count,
            'kafka_messages_sent': kafka_stats['messages_sent'],
            'kafka_errors': kafka_stats['errors'],
            'kafka_dlq_messages': kafka_stats['dlq_messages'],
            'kafka_success_rate': kafka_stats['success_rate'],
            'rate_limiter_utilization': rate_limiter_stats.get('utilization_percent_10min', 0)
        }

    def stop(self):
        """Stop the stream (placeholder for future graceful shutdown)"""
        logger.info("Stopping Reddit stream...")
        # PRAW streams don't have explicit stop methods
        # Graceful shutdown is handled by the main application
