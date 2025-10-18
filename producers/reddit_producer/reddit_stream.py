"""
Reddit stream using PRAW to collect live submissions and comments
"""
import praw
import logging
from config.secrets import RedditCredentials
from utils.schema import transform_submission, transform_comment, validate_post
from utils.rate_limiter import RateLimiter
from utils.backoff import ExponentialBackoff
from utils.circuit_breaker import CircuitBreaker
from utils.errors import RetryableError, PermanentError, classify_error
from utils.logging_context import set_correlation_id, clear_correlation_id, get_correlation_id
from utils.error_metrics import record_error, record_retry, update_circuit_breaker_state
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from prawcore.exceptions import ServerError, RequestException, ResponseException
import time

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
            burst_limit=config['rate_limiting']['burst_limit']
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
        self.shutdown_event = None  # Will be set from main

        logger.info(
            f"Reddit stream initialized for r/{self.subreddit_str}, "
            f"skip_existing={self.skip_existing}"
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((ServerError, RequestException, ResponseException))
    )
    def stream_submissions(self):
        """
        Stream new submissions from subreddits

        This method runs indefinitely and processes new submissions as they appear
        """
        logger.info(f"Starting submission stream for r/{self.subreddit_str}")

        try:
            for submission in self.subreddit.stream.submissions(
                skip_existing=self.skip_existing,
                pause_after=-1
            ):
                if submission is None:
                    # No new submissions, wait a bit
                    time.sleep(1)
                    continue

                # Set correlation ID for tracing
                correlation_id = set_correlation_id()

                try:
                    # Respect rate limits
                    self.rate_limiter.wait_if_needed()

                    # Transform submission to standard format
                    post_data = transform_submission(submission)
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
                            self.submission_count += 1

                            if self.submission_count % 10 == 0:
                                logger.info(
                                    f"Processed {self.submission_count} submissions "
                                    f"(total: {self.post_count} posts)"
                                )

                                # Log rate limiter stats
                                stats = self.rate_limiter.get_stats()
                                logger.info(
                                    f"API Rate: {stats['current_requests_per_minute']}/60 req/min "
                                    f"({stats['utilization_percent']:.1f}% utilized)"
                                )

                                # Update circuit breaker state metric
                                update_circuit_breaker_state(self.circuit_breaker.get_state())

                        except Exception as kafka_error:
                            record_error(kafka_error, "kafka_send")
                            self.kafka_producer.send_to_dlq(post_data, kafka_error, correlation_id)

                    else:
                        logger.warning(
                            f"Invalid submission: {post_data.get('post_id', 'unknown')}, "
                            f"subreddit: {post_data.get('subreddit', 'unknown')}"
                        )
                        self.kafka_producer.send_to_dlq(post_data, "validation_failed", correlation_id)

                except Exception as e:
                    logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)
                    record_error(e, "submission_processing")
                    # Continue processing next submission
                    continue

                finally:
                    clear_correlation_id()

                # Check for shutdown signal
                if self.shutdown_event and self.shutdown_event.is_set():
                    logger.info("Shutdown signal received, stopping submission stream")
                    break

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
            'rate_limiter_utilization': rate_limiter_stats['utilization_percent']
        }

    def stop(self):
        """Stop the stream (placeholder for future graceful shutdown)"""
        logger.info("Stopping Reddit stream...")
        # PRAW streams don't have explicit stop methods
        # Graceful shutdown is handled by the main application
