"""
Rate limiter to respect Reddit API limits (100 requests/minute with 10-minute averaging)
"""
import time
from collections import deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Advanced rate limiter for Reddit API requests

    Reddit enforces 100 QPM averaged over 10-minute window, allowing bursts.
    This implementation supports:
    - 100 QPM sustained rate
    - Burst support up to 50 requests
    - 10-minute averaging window
    - Adaptive throttling
    """

    def __init__(self, requests_per_minute=100, burst_limit=50, window_minutes=10):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests allowed per minute (100 for Reddit)
            burst_limit: Maximum burst requests allowed (50 recommended)
            window_minutes: Averaging window in minutes (10 for Reddit)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60

        # Track requests in 1-minute and 10-minute windows
        self.requests_1min = deque()
        self.requests_10min = deque()
        self.lock = Lock()

        # Track Reddit API headers
        self.api_remaining = None
        self.api_used = None
        self.api_reset = None

        logger.info(
            f"Rate limiter initialized: {requests_per_minute} QPM (avg over {window_minutes}min), "
            f"burst limit: {burst_limit}"
        )

    def update_from_headers(self, headers):
        """
        Update rate limiter state from Reddit API response headers

        Args:
            headers: Response headers dict with X-Ratelimit-* fields
        """
        with self.lock:
            self.api_remaining = headers.get('x-ratelimit-remaining')
            self.api_used = headers.get('x-ratelimit-used')
            self.api_reset = headers.get('x-ratelimit-reset')

            if self.api_remaining is not None:
                logger.debug(
                    f"Reddit API: {self.api_used} used, {self.api_remaining} remaining, "
                    f"resets in {self.api_reset}s"
                )

    def wait_if_needed(self):
        """
        Wait if necessary to respect rate limits with 10-minute averaging

        Strategy:
        - Allow bursts up to burst_limit in 1 minute
        - Enforce average of requests_per_minute over 10-minute window
        - Use Reddit API headers for adaptive throttling
        """
        with self.lock:
            now = time.time()

            # Clean up old requests (1-minute window)
            while self.requests_1min and self.requests_1min[0] < now - 60:
                self.requests_1min.popleft()

            # Clean up old requests (10-minute window)
            while self.requests_10min and self.requests_10min[0] < now - self.window_seconds:
                self.requests_10min.popleft()

            # Calculate current rates
            current_1min = len(self.requests_1min)
            current_10min = len(self.requests_10min)
            avg_per_min_10min = current_10min / self.window_minutes if current_10min > 0 else 0

            # Check burst limit (1-minute window)
            if current_1min >= self.burst_limit:
                sleep_time = 60 - (now - self.requests_1min[0])
                if sleep_time > 0:
                    logger.warning(
                        f"Burst limit reached ({current_1min}/{self.burst_limit} req/min). "
                        f"Sleeping {sleep_time:.2f}s"
                    )
                    time.sleep(sleep_time)
                    now = time.time()

                    # Clean up after sleep
                    while self.requests_1min and self.requests_1min[0] < now - 60:
                        self.requests_1min.popleft()

            # Check 10-minute average (enforce QPM limit)
            max_requests_10min = self.requests_per_minute * self.window_minutes
            if current_10min >= max_requests_10min:
                sleep_time = self.window_seconds - (now - self.requests_10min[0])
                if sleep_time > 0:
                    logger.warning(
                        f"10-minute average limit reached ({avg_per_min_10min:.1f}/{self.requests_per_minute} QPM). "
                        f"Sleeping {sleep_time:.2f}s"
                    )
                    time.sleep(sleep_time)
                    now = time.time()

                    # Clean up after sleep
                    while self.requests_10min and self.requests_10min[0] < now - self.window_seconds:
                        self.requests_10min.popleft()

            # Adaptive throttling based on Reddit API headers
            if self.api_remaining is not None:
                try:
                    remaining = float(self.api_remaining)
                    reset_seconds = float(self.api_reset) if self.api_reset else 60

                    # If we're close to the limit, slow down
                    if remaining < 10 and reset_seconds > 0:
                        # Spread remaining requests over reset period
                        sleep_time = reset_seconds / max(remaining, 1)
                        if sleep_time > 0.1:  # Only sleep if significant
                            logger.warning(
                                f"Approaching API limit ({remaining} remaining). "
                                f"Throttling to {sleep_time:.2f}s per request"
                            )
                            time.sleep(min(sleep_time, 5))  # Cap at 5s

                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing rate limit headers: {e}")

            # Record this request in both windows
            timestamp = time.time()
            self.requests_1min.append(timestamp)
            self.requests_10min.append(timestamp)

    def get_current_rate(self):
        """Get current number of requests in the last minute"""
        with self.lock:
            now = time.time()

            # Remove old requests
            while self.requests_1min and self.requests_1min[0] < now - 60:
                self.requests_1min.popleft()

            return len(self.requests_1min)

    def reset(self):
        """Reset the rate limiter (clear all recorded requests)"""
        with self.lock:
            self.requests_1min.clear()
            self.requests_10min.clear()
            self.api_remaining = None
            self.api_used = None
            self.api_reset = None
            logger.info("Rate limiter reset")

    def get_stats(self):
        """Get rate limiter statistics"""
        with self.lock:
            now = time.time()

            # Clean up old requests
            while self.requests_1min and self.requests_1min[0] < now - 60:
                self.requests_1min.popleft()
            while self.requests_10min and self.requests_10min[0] < now - self.window_seconds:
                self.requests_10min.popleft()

            current_1min = len(self.requests_1min)
            current_10min = len(self.requests_10min)
            avg_per_min_10min = current_10min / self.window_minutes if current_10min > 0 else 0

            stats = {
                'current_requests_per_minute': current_1min,
                'current_requests_per_10min': current_10min,
                'average_qpm_10min': avg_per_min_10min,
                'max_requests_per_minute': self.requests_per_minute,
                'burst_limit': self.burst_limit,
                'utilization_percent_1min': (current_1min / self.burst_limit) * 100,
                'utilization_percent_10min': (avg_per_min_10min / self.requests_per_minute) * 100,
            }

            # Add Reddit API header info if available
            if self.api_remaining is not None:
                stats.update({
                    'api_remaining': self.api_remaining,
                    'api_used': self.api_used,
                    'api_reset_seconds': self.api_reset
                })

            return stats
