"""
Error metrics collection for monitoring
"""
import logging
from prometheus_client import Counter, Gauge, Histogram
from .errors import classify_error

logger = logging.getLogger(__name__)

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

backoff_duration = Histogram(
    'reddit_producer_backoff_duration_seconds',
    'Duration of backoff delays'
)


def record_error(error, context="unknown"):
    """
    Record error metrics

    Args:
        error: Exception or error object
        context: Context where error occurred
    """
    error_type, is_retryable = classify_error(error)

    errors_total.labels(
        error_type=error_type.value,
        is_retryable=str(is_retryable)
    ).inc()

    logger.error(f"Error in {context}: {error_type.value} - {error}")


def record_retry(error_type):
    """Record retry attempt"""
    retry_attempts.labels(error_type=error_type.value).inc()


def record_dlq(error_type):
    """Record DLQ message"""
    dlq_messages_total.labels(error_type=error_type.value).inc()


def record_backoff(duration):
    """Record backoff duration"""
    backoff_duration.observe(duration)


def update_circuit_breaker_state(state):
    """
    Update circuit breaker state metric

    Args:
        state: CircuitState enum (CLOSED=0, HALF_OPEN=1, OPEN=2)
    """
    state_values = {
        'CLOSED': 0,
        'HALF_OPEN': 1,
        'OPEN': 2
    }
    state_value = state_values.get(state.name if hasattr(state, 'name') else str(state), 0)
    circuit_breaker_state.set(state_value)
