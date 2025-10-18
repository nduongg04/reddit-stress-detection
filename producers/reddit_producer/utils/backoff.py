"""
Exponential backoff with jitter for retry logic
"""
import time
import random
import logging
from .errors import classify_error

logger = logging.getLogger(__name__)


class ExponentialBackoff:
    """
    Exponential backoff with jitter
    Formula: min(max_delay, base * 2^attempt + random(0, jitter))
    """

    def __init__(self, base_delay=1.0, max_delay=60.0,
                 jitter_factor=0.5, max_attempts=5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self.max_attempts = max_attempts
        self.current_attempt = 0

    def get_delay(self):
        """Calculate delay for current attempt"""
        if self.current_attempt == 0:
            return 0

        # Exponential calculation: base * 2^(attempt-1)
        exponential_delay = self.base_delay * (2 ** (self.current_attempt - 1))

        # Add jitter: random(0, jitter_factor * exponential_delay)
        jitter = random.uniform(0, self.jitter_factor * exponential_delay)

        # Apply max delay cap
        delay = min(exponential_delay + jitter, self.max_delay)

        logger.debug(f"Backoff delay for attempt {self.current_attempt}: {delay:.2f}s")
        return delay

    def wait(self):
        """Wait for calculated delay"""
        delay = self.get_delay()
        if delay > 0:
            logger.info(f"Backing off for {delay:.2f} seconds (attempt {self.current_attempt})")
            time.sleep(delay)

    def increment(self):
        """Increment attempt counter"""
        self.current_attempt += 1

    def should_retry(self):
        """Check if should retry based on max attempts"""
        return self.current_attempt < self.max_attempts

    def reset(self):
        """Reset attempt counter"""
        self.current_attempt = 0


def retry_with_backoff(base_delay=1.0, max_delay=60.0, max_attempts=5):
    """
    Decorator to add retry logic with exponential backoff

    Usage:
        @retry_with_backoff(base_delay=2.0, max_attempts=3)
        def my_function():
            # code that may fail
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            backoff = ExponentialBackoff(base_delay, max_delay, max_attempts=max_attempts)

            while backoff.should_retry():
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_type, is_retryable = classify_error(e)

                    if not is_retryable:
                        logger.error(f"Non-retryable error: {e}")
                        raise

                    backoff.increment()
                    if backoff.should_retry():
                        logger.warning(f"Retryable error: {e}. Retrying...")
                        backoff.wait()
                    else:
                        logger.error(f"Max retries exceeded for {func.__name__}")
                        raise

            raise Exception(f"Max retries exceeded for {func.__name__}")

        return wrapper
    return decorator
