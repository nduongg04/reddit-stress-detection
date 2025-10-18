# TASK-011: Error Handling & Retry Logic

**Owner:** Data Engineer
**Priority:** High
**Dependencies:** TASK-009 (Reddit API Integration)
**Estimate:** 1 day

---

## Overview

Implement robust error handling and retry logic for the Reddit producer to ensure resilience against transient failures, API errors, network issues, and malformed data. This includes exponential backoff, circuit breaker patterns, DLQ routing, and graceful shutdown mechanisms.

---

## Subtasks

### Subtask 011.1: Error Classification System

**Estimate:** 45 minutes

**Description:**
- Define error categories (transient, permanent, validation)
- Create error type enum
- Implement error classification logic

**Acceptance Criteria:**
- All error types classified correctly
- Error categories documented
- Classification logic tested

**Files to Create:**
- `producers/reddit_producer/utils/errors.py`

**Implementation:**
```python
from enum import Enum

class ErrorType(Enum):
    """Error classification for retry logic"""
    # Transient errors - retry
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    KAFKA_TEMPORARY = "kafka_temporary"

    # Permanent errors - do not retry
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    INVALID_REQUEST = "invalid_request"
    RESOURCE_NOT_FOUND = "resource_not_found"

    # Validation errors - send to DLQ
    SCHEMA_VALIDATION = "schema_validation"
    MALFORMED_DATA = "malformed_data"
    MISSING_REQUIRED_FIELD = "missing_required_field"

class RetryableError(Exception):
    """Exception for errors that should be retried"""
    def __init__(self, message, error_type, original_exception=None):
        super().__init__(message)
        self.error_type = error_type
        self.original_exception = original_exception

class PermanentError(Exception):
    """Exception for errors that should not be retried"""
    def __init__(self, message, error_type, original_exception=None):
        super().__init__(message)
        self.error_type = error_type
        self.original_exception = original_exception

def classify_error(exception):
    """
    Classify exception into error type
    Returns (ErrorType, bool is_retryable)
    """
    import prawcore
    from kafka.errors import KafkaError
    import requests

    # PRAW/Reddit API errors
    if isinstance(exception, prawcore.exceptions.ResponseException):
        if exception.response.status_code == 429:
            return ErrorType.RATE_LIMIT, True
        elif exception.response.status_code >= 500:
            return ErrorType.API_ERROR, True
        elif exception.response.status_code == 401:
            return ErrorType.AUTHENTICATION_ERROR, False
        elif exception.response.status_code == 403:
            return ErrorType.AUTHORIZATION_ERROR, False
        elif exception.response.status_code == 404:
            return ErrorType.RESOURCE_NOT_FOUND, False
        else:
            return ErrorType.INVALID_REQUEST, False

    # Network errors
    if isinstance(exception, (requests.exceptions.ConnectionError,
                             requests.exceptions.Timeout)):
        return ErrorType.NETWORK_ERROR, True

    # Kafka errors
    if isinstance(exception, KafkaError):
        if hasattr(exception, 'retriable') and exception.retriable():
            return ErrorType.KAFKA_TEMPORARY, True
        return ErrorType.KAFKA_TEMPORARY, False

    # Validation errors
    if isinstance(exception, (ValueError, KeyError)):
        return ErrorType.SCHEMA_VALIDATION, False

    # Default: treat as transient
    return ErrorType.API_ERROR, True
```

---

### Subtask 011.2: Exponential Backoff Implementation

**Estimate:** 1 hour

**Description:**
- Implement exponential backoff with jitter
- Configure min/max delays
- Add backoff calculator

**Acceptance Criteria:**
- Backoff delays increase exponentially
- Jitter prevents thundering herd
- Max delay enforced

**Files to Create:**
- `producers/reddit_producer/utils/backoff.py`

**Implementation:**
```python
import time
import random
import logging

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

# Decorator for automatic retry with backoff
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
```

---

### Subtask 011.3: Circuit Breaker Pattern

**Estimate:** 1.5 hours

**Description:**
- Implement circuit breaker to prevent cascading failures
- Configure failure thresholds
- Add automatic recovery mechanism

**Acceptance Criteria:**
- Circuit opens after threshold failures
- Circuit half-opens for recovery testing
- Circuit closes after successful recovery

**Files to Create:**
- `producers/reddit_producer/utils/circuit_breaker.py`

**Implementation:**
```python
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
```

---

### Subtask 011.4: Enhanced DLQ Handler

**Estimate:** 1 hour

**Description:**
- Enhance DLQ with detailed error metadata
- Add correlation IDs for tracing
- Implement error categorization

**Acceptance Criteria:**
- DLQ messages include full error context
- Correlation IDs tracked
- Error categories preserved

**Files to Update:**
- `producers/reddit_producer/utils/kafka_producer.py`

**Enhanced Implementation:**
```python
import uuid
from datetime import datetime
import json
import logging
from utils.errors import classify_error, ErrorType

logger = logging.getLogger(__name__)

class EnhancedKafkaProducer:
    def __init__(self, config):
        # ... existing init code ...
        self.dlq_stats = {
            'total_dlq_messages': 0,
            'by_error_type': {}
        }

    def send_to_dlq(self, message, error, correlation_id=None):
        """
        Send failed message to DLQ with enhanced metadata
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # Classify error
        error_type, is_retryable = classify_error(error)

        dlq_message = {
            "correlation_id": correlation_id,
            "original_message": message,
            "error_metadata": {
                "error_type": error_type.value,
                "error_message": str(error),
                "is_retryable": is_retryable,
                "exception_class": error.__class__.__name__,
                "timestamp": datetime.utcnow().isoformat()
            },
            "producer_metadata": {
                "producer_version": "1.0.0",
                "hostname": os.getenv('HOSTNAME', 'unknown')
            }
        }

        try:
            self.producer.send(
                self.dlq_topic,
                value=dlq_message,
                key=correlation_id
            )

            # Update stats
            self.dlq_stats['total_dlq_messages'] += 1
            error_type_str = error_type.value
            self.dlq_stats['by_error_type'][error_type_str] = \
                self.dlq_stats['by_error_type'].get(error_type_str, 0) + 1

            logger.error(f"Message sent to DLQ. Correlation ID: {correlation_id}, "
                        f"Error Type: {error_type.value}")

        except Exception as dlq_error:
            logger.critical(f"Failed to send message to DLQ: {dlq_error}")
            # Last resort: write to local file
            self._write_to_local_dlq(dlq_message)

    def _write_to_local_dlq(self, message):
        """Fallback: write to local file if Kafka DLQ unavailable"""
        local_dlq_dir = Path("logs/dlq_fallback")
        local_dlq_dir.mkdir(parents=True, exist_ok=True)

        filename = f"dlq_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
        filepath = local_dlq_dir / filename

        with open(filepath, 'w') as f:
            json.dump(message, f, indent=2)

        logger.warning(f"Message written to local DLQ: {filepath}")

    def get_dlq_stats(self):
        """Get DLQ statistics"""
        return self.dlq_stats
```

---

### Subtask 011.5: Graceful Shutdown Handler

**Estimate:** 1 hour

**Description:**
- Implement proper SIGTERM/SIGINT handling
- Ensure all messages flushed before exit
- Clean up resources properly

**Acceptance Criteria:**
- No data loss during shutdown
- All connections closed cleanly
- Exit status code correct

**Files to Update:**
- `producers/reddit_producer/main.py`

**Enhanced Implementation:**
```python
import signal
import sys
import logging
import atexit
from threading import Event

logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = Event()

class GracefulShutdownHandler:
    """
    Handle graceful shutdown with cleanup
    """

    def __init__(self, kafka_producer, reddit_stream):
        self.kafka_producer = kafka_producer
        self.reddit_stream = reddit_stream
        self.shutdown_started = False

    def register_handlers(self):
        """Register signal handlers"""
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        atexit.register(self._cleanup)

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals"""
        if self.shutdown_started:
            logger.warning("Forced shutdown requested")
            sys.exit(1)

        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        self.shutdown_started = True
        shutdown_event.set()

    def _cleanup(self):
        """Cleanup resources"""
        if not self.shutdown_started:
            return

        logger.info("Performing cleanup...")

        try:
            # Flush remaining messages
            logger.info("Flushing Kafka producer...")
            self.kafka_producer.flush(timeout=30)

            # Get final stats
            stats = self.reddit_stream.get_stats()
            dlq_stats = self.kafka_producer.get_dlq_stats()

            logger.info("=" * 60)
            logger.info("Shutdown Statistics:")
            logger.info(f"  Posts processed: {stats['posts_processed']}")
            logger.info(f"  Messages sent: {stats['kafka_messages_sent']}")
            logger.info(f"  Errors: {stats['kafka_errors']}")
            logger.info(f"  DLQ messages: {dlq_stats['total_dlq_messages']}")
            logger.info("=" * 60)

            # Close connections
            logger.info("Closing Kafka producer...")
            self.kafka_producer.close()

            logger.info("Graceful shutdown complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            sys.exit(1)

# Update main() function
def main():
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    kafka_producer = RedditKafkaProducer(config)
    reddit_stream = RedditStream(config, kafka_producer)

    # Setup graceful shutdown
    shutdown_handler = GracefulShutdownHandler(kafka_producer, reddit_stream)
    shutdown_handler.register_handlers()

    logger.info("Starting Reddit Producer...")

    try:
        # Start streams...
        submission_thread = Thread(target=reddit_stream.stream_submissions, daemon=True)
        comment_thread = Thread(target=reddit_stream.stream_comments, daemon=True)

        submission_thread.start()
        comment_thread.start()

        # Wait for shutdown signal
        shutdown_event.wait()

        # Give threads time to finish current work
        logger.info("Waiting for threads to finish...")
        submission_thread.join(timeout=10)
        comment_thread.join(timeout=10)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
```

---

### Subtask 011.6: Correlation ID Tracking

**Estimate:** 45 minutes

**Description:**
- Add correlation IDs to all log messages
- Track message lifecycle
- Enable distributed tracing

**Acceptance Criteria:**
- All logs include correlation ID
- Messages traceable end-to-end
- Logging context maintained

**Files to Create:**
- `producers/reddit_producer/utils/logging_context.py`

**Implementation:**
```python
import logging
import contextvars
import uuid

# Context variable for correlation ID
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)

class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to log records"""

    def filter(self, record):
        correlation_id = correlation_id_var.get()
        if correlation_id:
            record.correlation_id = correlation_id
        else:
            record.correlation_id = "N/A"
        return True

def get_correlation_id():
    """Get current correlation ID"""
    return correlation_id_var.get()

def set_correlation_id(correlation_id=None):
    """Set correlation ID for current context"""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id

def clear_correlation_id():
    """Clear correlation ID"""
    correlation_id_var.set(None)

# Update logging configuration to include correlation ID
# In config/logging.yaml, update format:
# format: '%(asctime)s - %(name)s - [%(correlation_id)s] - %(levelname)s - %(message)s'
```

---

### Subtask 011.7: Error Metrics Collection

**Estimate:** 1 hour

**Description:**
- Implement error metrics for monitoring
- Track error rates by type
- Expose metrics via Prometheus

**Acceptance Criteria:**
- Error metrics collected
- Metrics exposed in Prometheus format
- Error rates calculated

**Files to Update:**
- `producers/reddit_producer/health_server.py`

**Enhanced Metrics:**
```python
from prometheus_client import Counter, Gauge, Histogram

# Error metrics
errors_total = Counter(
    'reddit_producer_errors_total',
    'Total errors by type',
    ['error_type', 'is_retryable']
)

retry_attempts = Counter(
    'reddit_producer_retry_attempts_total',
    'Total retry attempts',
    ['error_type']
)

circuit_breaker_state = Gauge(
    'reddit_producer_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)'
)

dlq_messages_total = Counter(
    'reddit_producer_dlq_messages_total',
    'Total messages sent to DLQ',
    ['error_type']
)

# Update error handler to record metrics
def handle_error_with_metrics(error, context="unknown"):
    error_type, is_retryable = classify_error(error)

    errors_total.labels(
        error_type=error_type.value,
        is_retryable=str(is_retryable)
    ).inc()

    logger.error(f"Error in {context}: {error_type.value} - {error}")
```

---

### Subtask 011.8: Retry Configuration

**Estimate:** 30 minutes

**Description:**
- Add retry configuration to config file
- Make retry behavior configurable
- Document retry settings

**Acceptance Criteria:**
- Retry settings in config
- Settings applied correctly
- Configuration documented

**Files to Update:**
- `producers/reddit_producer/config/config.yaml`

**Add Configuration:**
```yaml
error_handling:
  retry:
    max_attempts: 5
    base_delay_seconds: 1.0
    max_delay_seconds: 60.0
    jitter_factor: 0.5

  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 60
    success_threshold: 2

  dlq:
    enabled: true
    write_local_fallback: true
    local_fallback_dir: logs/dlq_fallback
```

---

### Subtask 011.9: Integration with Reddit Stream

**Estimate:** 1 hour

**Description:**
- Integrate error handling into Reddit stream
- Apply retry logic to API calls
- Add circuit breaker protection

**Acceptance Criteria:**
- Stream handles errors gracefully
- Retries work automatically
- Circuit breaker prevents cascading failures

**Files to Update:**
- `producers/reddit_producer/reddit_stream.py`

**Enhanced Implementation:**
```python
from utils.backoff import ExponentialBackoff
from utils.circuit_breaker import CircuitBreaker
from utils.errors import RetryableError, PermanentError, classify_error
from utils.logging_context import set_correlation_id, clear_correlation_id

class EnhancedRedditStream(RedditStream):
    def __init__(self, config, kafka_producer):
        super().__init__(config, kafka_producer)

        # Initialize error handling components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config['error_handling']['circuit_breaker']['failure_threshold'],
            recovery_timeout=config['error_handling']['circuit_breaker']['recovery_timeout_seconds'],
            success_threshold=config['error_handling']['circuit_breaker']['success_threshold']
        )

    def stream_submissions_with_retry(self):
        """Stream submissions with retry logic"""
        backoff = ExponentialBackoff(
            base_delay=self.config['error_handling']['retry']['base_delay_seconds'],
            max_delay=self.config['error_handling']['retry']['max_delay_seconds'],
            max_attempts=self.config['error_handling']['retry']['max_attempts']
        )

        while not shutdown_event.is_set():
            try:
                # Use circuit breaker to protect API calls
                self.circuit_breaker.call(self._stream_submissions_batch)
                backoff.reset()  # Reset on success

            except PermanentError as e:
                logger.error(f"Permanent error, stopping: {e}")
                break

            except Exception as e:
                error_type, is_retryable = classify_error(e)

                if not is_retryable:
                    logger.error(f"Non-retryable error: {e}")
                    break

                backoff.increment()
                if backoff.should_retry():
                    logger.warning(f"Stream error, retrying: {e}")
                    backoff.wait()
                else:
                    logger.error(f"Max retries exceeded, stopping stream")
                    break

    def _stream_submissions_batch(self):
        """Process a batch of submissions"""
        for submission in self.subreddit.stream.submissions(skip_existing=True):
            # Set correlation ID for tracing
            correlation_id = set_correlation_id()

            try:
                self.rate_limiter.wait_if_needed()
                post_data = transform_submission(submission)
                post_data['correlation_id'] = correlation_id

                if validate_post(post_data):
                    self.kafka_producer.send_message(
                        message=post_data,
                        key=post_data['post_id'],
                        correlation_id=correlation_id
                    )
                    self.post_count += 1

            except Exception as e:
                logger.error(f"Error processing submission {submission.id}: {e}")
                self.kafka_producer.send_to_dlq(post_data, e, correlation_id)

            finally:
                clear_correlation_id()

            # Check for shutdown
            if shutdown_event.is_set():
                break
```

---

### Subtask 011.10: Error Logging Enhancement

**Estimate:** 30 minutes

**Description:**
- Enhance error logging with context
- Add stack traces for debugging
- Implement structured error logs

**Acceptance Criteria:**
- Error logs include full context
- Stack traces captured
- Logs parseable by log aggregation tools

**Implementation:**
```python
import traceback
import json

def log_error_with_context(logger, error, context):
    """
    Log error with full context and stack trace
    """
    error_type, is_retryable = classify_error(error)

    error_info = {
        "error_type": error_type.value,
        "error_message": str(error),
        "is_retryable": is_retryable,
        "exception_class": error.__class__.__name__,
        "context": context,
        "stack_trace": traceback.format_exc()
    }

    logger.error(f"Error occurred: {json.dumps(error_info, indent=2)}")
```

---

### Subtask 011.11: Unit Tests for Error Handling

**Estimate:** 2 hours

**Description:**
- Write comprehensive tests for error handling
- Test retry logic
- Test circuit breaker behavior
- Test DLQ routing

**Acceptance Criteria:**
- All error handling components tested
- Edge cases covered
- Tests pass consistently

**Files to Create:**
- `producers/reddit_producer/tests/test_error_handling.py`

**Test Implementation:**
```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from utils.backoff import ExponentialBackoff
from utils.circuit_breaker import CircuitBreaker, CircuitState
from utils.errors import classify_error, ErrorType, RetryableError, PermanentError
import prawcore

class TestExponentialBackoff(unittest.TestCase):
    def test_backoff_increases(self):
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=60.0)

        delays = []
        for i in range(5):
            backoff.increment()
            delays.append(backoff.get_delay())

        # Check delays are increasing
        for i in range(len(delays) - 1):
            self.assertLess(delays[i], delays[i+1] * 1.5)  # Account for jitter

    def test_max_delay_enforced(self):
        backoff = ExponentialBackoff(base_delay=10.0, max_delay=30.0)

        for i in range(10):
            backoff.increment()
            delay = backoff.get_delay()
            self.assertLessEqual(delay, 30.0)

    def test_should_retry(self):
        backoff = ExponentialBackoff(max_attempts=3)

        self.assertTrue(backoff.should_retry())
        backoff.increment()
        self.assertTrue(backoff.should_retry())
        backoff.increment()
        self.assertTrue(backoff.should_retry())
        backoff.increment()
        self.assertFalse(backoff.should_retry())

class TestCircuitBreaker(unittest.TestCase):
    def test_circuit_opens_after_failures(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        def failing_func():
            raise Exception("Test error")

        # Trigger failures
        for i in range(3):
            try:
                breaker.call(failing_func)
            except:
                pass

        # Circuit should be open
        self.assertEqual(breaker.get_state(), CircuitState.OPEN)

    def test_circuit_half_opens_after_timeout(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        def failing_func():
            raise Exception("Test error")

        # Trigger failures
        for i in range(2):
            try:
                breaker.call(failing_func)
            except:
                pass

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Next call should transition to half-open
        def success_func():
            return "success"

        result = breaker.call(success_func)
        self.assertEqual(result, "success")

    def test_circuit_closes_after_recovery(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1, success_threshold=2)

        def failing_func():
            raise Exception("Test error")

        # Open circuit
        for i in range(2):
            try:
                breaker.call(failing_func)
            except:
                pass

        # Wait and recover
        import time
        time.sleep(1.1)

        def success_func():
            return "success"

        # Successful calls to close circuit
        breaker.call(success_func)
        breaker.call(success_func)

        self.assertEqual(breaker.get_state(), CircuitState.CLOSED)

class TestErrorClassification(unittest.TestCase):
    def test_rate_limit_error(self):
        mock_response = Mock()
        mock_response.status_code = 429
        error = prawcore.exceptions.ResponseException(mock_response)

        error_type, is_retryable = classify_error(error)
        self.assertEqual(error_type, ErrorType.RATE_LIMIT)
        self.assertTrue(is_retryable)

    def test_authentication_error(self):
        mock_response = Mock()
        mock_response.status_code = 401
        error = prawcore.exceptions.ResponseException(mock_response)

        error_type, is_retryable = classify_error(error)
        self.assertEqual(error_type, ErrorType.AUTHENTICATION_ERROR)
        self.assertFalse(is_retryable)

if __name__ == '__main__':
    unittest.main()
```

---

### Subtask 011.12: Integration Testing

**Estimate:** 1 hour

**Description:**
- Test error handling in full producer
- Simulate various failure scenarios
- Verify recovery mechanisms
- **[USER TASK]** Manually verify error handling behavior

**Acceptance Criteria:**
- Producer recovers from transient failures
- DLQ receives malformed messages
- Circuit breaker prevents cascading failures
- Graceful shutdown works

**Test Scenarios:**
```bash
# Test 1: Rate limit handling
# Temporarily set very high request rate and verify backoff

# Test 2: Network interruption
# Disconnect network mid-stream and verify recovery

# Test 3: Malformed data
# Inject invalid data and verify DLQ routing

# Test 4: Graceful shutdown
# Send SIGTERM and verify clean shutdown
kill -TERM <pid>

# Test 5: Circuit breaker
# Simulate Kafka downtime and verify circuit opens
```

---

### Subtask 011.13: Documentation

**Estimate:** 1 hour

**Description:**
- Document error handling architecture
- Create troubleshooting guide
- Document configuration options

**Acceptance Criteria:**
- Architecture documented
- Troubleshooting guide complete
- Configuration examples provided

**Files to Create:**
- `producers/reddit_producer/docs/error_handling.md`

---

### Subtask 011.14: Monitoring Dashboard Setup

**Estimate:** 1 hour

**Description:**
- Create Grafana dashboard for error metrics
- Add alerts for high error rates
- Visualize retry attempts and DLQ messages

**Acceptance Criteria:**
- Error metrics visible in Grafana
- Alerts configured
- Dashboard provides actionable insights

**Dashboard Panels:**
- Error rate over time (by type)
- Retry attempts histogram
- Circuit breaker state
- DLQ message count
- Error type distribution (pie chart)

---

### Subtask 011.15: Final Verification

**Estimate:** 1 hour

**Description:**
- Run producer with error handling for 24 hours
- Verify all error scenarios handled correctly
- Check metrics and logs
- **[USER TASK]** Verify production readiness

**Acceptance Criteria:**
- Producer runs for 24+ hours without crashes
- All error types handled correctly
- Error rate <1%
- DLQ messages reviewable

---

## Rollback Plan

If error handling causes issues:

1. **Disable circuit breaker:**
   ```yaml
   # In config.yaml
   error_handling:
     circuit_breaker:
       failure_threshold: 999999  # Effectively disabled
   ```

2. **Reduce retry attempts:**
   ```yaml
   error_handling:
     retry:
       max_attempts: 1  # No retries
   ```

3. **Revert to previous version:**
   ```bash
   git checkout <previous-commit>
   docker-compose restart reddit-producer
   ```

---

## Testing Checklist

- [ ] Error classification works correctly
- [ ] Exponential backoff delays increase properly
- [ ] Circuit breaker opens after threshold
- [ ] Circuit breaker recovers automatically
- [ ] DLQ receives malformed messages
- [ ] Correlation IDs tracked throughout
- [ ] Graceful shutdown works without data loss
- [ ] Error metrics collected correctly
- [ ] Retry logic prevents repeated failures
- [ ] Non-retryable errors stop immediately
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-009: Reddit producer operational
- TASK-001: Kafka with DLQ topic

**Blocks:**
- TASK-024: Producer Metrics & Health Checks
- TASK-030: Load Testing & Stress Testing

---

## Notes

- Always use correlation IDs for debugging
- Monitor circuit breaker state in production
- Review DLQ messages regularly
- Tune retry parameters based on observed behavior
- Consider implementing rate limit prediction to avoid 429 errors
- Test error handling under various failure scenarios

---

## Estimated Completion

**Total Time:** 15-16 hours (1 day)

**Breakdown:**
- Error Classification & Retry Logic: 4 hours
- Circuit Breaker & DLQ: 4 hours
- Graceful Shutdown & Logging: 3 hours
- Testing & Verification: 3 hours
- Documentation: 2 hours
