"""
Rate limiter to respect Reddit API limits (60 requests/minute)
"""
import time
from collections import deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API requests

    Ensures we don't exceed Reddit's API rate limits (60 requests/minute)
    """

    def __init__(self, requests_per_minute=60, burst_limit=10):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_limit: Maximum burst requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.requests = deque()
        self.lock = Lock()

        logger.info(
            f"Rate limiter initialized: {requests_per_minute} req/min, "
            f"burst limit: {burst_limit}"
        )

    def wait_if_needed(self):
        """
        Wait if necessary to respect rate limits

        This method blocks until it's safe to make another request
        """
        with self.lock:
            now = time.time()

            # Remove requests older than 1 minute
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            # Check if we've hit the rate limit
            if len(self.requests) >= self.requests_per_minute:
                # Calculate how long to wait
                sleep_time = 60 - (now - self.requests[0])

                if sleep_time > 0:
                    logger.warning(
                        f"Rate limit reached ({self.requests_per_minute} req/min). "
                        f"Sleeping for {sleep_time:.2f} seconds"
                    )
                    time.sleep(sleep_time)

                    # Clean up old requests after sleeping
                    now = time.time()
                    while self.requests and self.requests[0] < now - 60:
                        self.requests.popleft()

            # Record this request
            self.requests.append(time.time())

    def get_current_rate(self):
        """Get current number of requests in the last minute"""
        with self.lock:
            now = time.time()

            # Remove old requests
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            return len(self.requests)

    def reset(self):
        """Reset the rate limiter (clear all recorded requests)"""
        with self.lock:
            self.requests.clear()
            logger.info("Rate limiter reset")

    def get_stats(self):
        """Get rate limiter statistics"""
        with self.lock:
            now = time.time()

            # Remove old requests
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            return {
                'current_requests_per_minute': len(self.requests),
                'max_requests_per_minute': self.requests_per_minute,
                'utilization_percent': (len(self.requests) / self.requests_per_minute) * 100
            }
