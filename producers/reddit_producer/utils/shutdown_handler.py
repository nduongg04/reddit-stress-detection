"""
Graceful shutdown handler with cleanup
"""
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
            logger.info(f"  Posts processed: {stats.get('posts_processed', 0)}")
            logger.info(f"  Messages sent: {stats.get('kafka_messages_sent', 0)}")
            logger.info(f"  Errors: {stats.get('kafka_errors', 0)}")
            logger.info(f"  DLQ messages: {dlq_stats['total_dlq_messages']}")
            logger.info("=" * 60)

            # Close connections
            logger.info("Closing Kafka producer...")
            self.kafka_producer.close()

            logger.info("Graceful shutdown complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            sys.exit(1)
