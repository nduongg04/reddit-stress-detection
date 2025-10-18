"""
Circuit breaker pattern implementation
Prevents repeated calls to failing services
"""
import time
import logging
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failure threshold exceeded, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    Prevents repeated calls to failing services
    """

    def __init__(self, failure_threshold=5, recovery_timeout=60,
                 success_threshold=2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = Lock()

    def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection
        """
        with self.lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception(f"Circuit breaker is OPEN. Service unavailable.")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(f"Circuit breaker success count: {self.success_count}/{self.success_threshold}")

                if self.success_count >= self.success_threshold:
                    logger.info("Circuit breaker closing - service recovered")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    def _on_failure(self):
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker reopening - service still failing")
                self.state = CircuitState.OPEN
                self.success_count = 0

            elif self.failure_count >= self.failure_threshold:
                logger.error(f"Circuit breaker opening - failure threshold reached ({self.failure_count})")
                self.state = CircuitState.OPEN

    def get_state(self):
        """Get current circuit state"""
        return self.state

    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            logger.info("Circuit breaker manually reset")
