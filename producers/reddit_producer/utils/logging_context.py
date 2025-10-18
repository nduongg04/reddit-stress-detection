"""
Correlation ID tracking for distributed tracing
"""
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
