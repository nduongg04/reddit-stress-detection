"""
Error classification and custom exceptions for Reddit producer
"""
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
