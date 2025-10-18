"""
Kafka producer for Reddit data with error handling and DLQ support
"""
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram
from .errors import classify_error, ErrorType
from .logging_context import get_correlation_id

logger = logging.getLogger(__name__)

# Prometheus metrics
messages_sent_counter = Counter(
    'reddit_producer_messages_sent_total',
    'Total messages sent to Kafka',
    ['topic', 'status']
)

message_size_histogram = Histogram(
    'reddit_producer_message_size_bytes',
    'Message size in bytes'
)

send_latency_histogram = Histogram(
    'reddit_producer_send_latency_seconds',
    'Time to send message to Kafka'
)


class RedditKafkaProducer:
    """
    Kafka producer for Reddit posts with retry logic and DLQ support
    """

    def __init__(self, config):
        """
        Initialize Kafka producer

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.topic = config['kafka']['topic']
        self.dlq_topic = config['kafka']['dlq_topic']

        self.producer = KafkaProducer(
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas to acknowledge
            retries=config['producer']['max_retries'],
            max_in_flight_requests_per_connection=1,  # Ensure ordering
            compression_type='gzip',
            request_timeout_ms=config['producer']['request_timeout_ms'],
            api_version=(2, 0, 0)
        )

        self.message_count = 0
        self.error_count = 0
        self.dlq_count = 0
        self.dlq_stats = {
            'total_dlq_messages': 0,
            'by_error_type': {}
        }

        logger.info(
            f"Kafka producer initialized: topic={self.topic}, "
            f"bootstrap_servers={config['kafka']['bootstrap_servers']}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def send_message(self, message, key=None):
        """
        Send message to Kafka with retry logic

        Args:
            message: Message dictionary
            key: Message key (optional)

        Raises:
            Exception: If message cannot be sent after retries
        """
        try:
            # Track message size
            message_json = json.dumps(message)
            message_size_histogram.observe(len(message_json))

            # Send to Kafka
            future = self.producer.send(
                self.topic,
                value=message,
                key=key
            )

            # Add callbacks
            future.add_callback(self.on_success)
            future.add_errback(self.on_error, message, key)

            # Wait for send to complete (with timeout)
            metadata = future.get(timeout=30)

            self.message_count += 1
            messages_sent_counter.labels(topic=self.topic, status='success').inc()

            return metadata

        except KafkaError as e:
            logger.error(f"Kafka error sending message: {e}")
            self.send_to_dlq(message, str(e), 'kafka_error')
            self.error_count += 1
            messages_sent_counter.labels(topic=self.topic, status='error').inc()
            raise

        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            self.send_to_dlq(message, str(e), 'unknown_error')
            self.error_count += 1
            messages_sent_counter.labels(topic=self.topic, status='error').inc()
            raise

    def on_success(self, metadata):
        """
        Callback for successful message send

        Args:
            metadata: Kafka RecordMetadata
        """
        logger.debug(
            f"Message sent successfully: topic={metadata.topic}, "
            f"partition={metadata.partition}, offset={metadata.offset}"
        )

    def on_error(self, exception, message, key):
        """
        Callback for failed message send

        Args:
            exception: Exception that occurred
            message: Original message
            key: Message key
        """
        logger.error(f"Error in send callback: {exception}")
        self.send_to_dlq(message, str(exception), 'send_callback_error')
        self.error_count += 1

    def send_to_dlq(self, message, error, correlation_id=None):
        """
        Send failed message to DLQ with enhanced metadata

        Args:
            message: Original message
            error: Exception or error message
            correlation_id: Optional correlation ID for tracing
        """
        if correlation_id is None:
            correlation_id = get_correlation_id() or str(uuid.uuid4())

        # Classify error
        error_type, is_retryable = classify_error(error) if isinstance(error, Exception) else (ErrorType.SCHEMA_VALIDATION, False)

        dlq_message = {
            "correlation_id": correlation_id,
            "original_message": message,
            "error_metadata": {
                "error_type": error_type.value if isinstance(error_type, ErrorType) else str(error_type),
                "error_message": str(error),
                "is_retryable": is_retryable,
                "exception_class": error.__class__.__name__ if isinstance(error, Exception) else "Unknown",
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
            self.dlq_count += 1
            self.dlq_stats['total_dlq_messages'] += 1
            error_type_str = error_type.value if isinstance(error_type, ErrorType) else str(error_type)
            self.dlq_stats['by_error_type'][error_type_str] = \
                self.dlq_stats['by_error_type'].get(error_type_str, 0) + 1

            logger.error(f"Message sent to DLQ. Correlation ID: {correlation_id}, "
                        f"Error Type: {error_type_str}")

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

    def flush(self, timeout=60):
        """
        Flush pending messages

        Args:
            timeout: Timeout in seconds
        """
        logger.info("Flushing pending messages...")
        try:
            self.producer.flush(timeout=timeout)
            logger.info("Flush completed successfully")
        except Exception as e:
            logger.error(f"Error flushing messages: {e}")

    def close(self):
        """Close the Kafka producer"""
        logger.info("Closing Kafka producer...")
        try:
            self.producer.close(timeout=30)
            logger.info(
                f"Kafka producer closed. Stats: "
                f"sent={self.message_count}, errors={self.error_count}, dlq={self.dlq_count}"
            )
        except Exception as e:
            logger.error(f"Error closing producer: {e}")

    def get_stats(self):
        """
        Get producer statistics

        Returns:
            dict: Statistics
        """
        return {
            'messages_sent': self.message_count,
            'errors': self.error_count,
            'dlq_messages': self.dlq_count,
            'success_rate': (self.message_count / max(self.message_count + self.error_count, 1)) * 100
        }
