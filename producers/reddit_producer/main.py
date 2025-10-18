#!/usr/bin/env python3
"""
Reddit Producer - Main Application

Streams live Reddit data from mental health subreddits to Kafka
"""
import signal
import sys
import logging
import logging.config
import yaml
from threading import Thread, Event
from pathlib import Path
import argparse

from reddit_stream import RedditStream
from utils.kafka_producer import RedditKafkaProducer
from config.config import Config

# Global shutdown event
shutdown_event = Event()

# Setup logging
def setup_logging():
    """Configure logging from YAML file"""
    logging_config_path = Path(__file__).parent / 'config' / 'logging.yaml'

    if logging_config_path.exists():
        with open(logging_config_path, 'r') as f:
            config = yaml.safe_load(f)
            logging.config.dictConfig(config)
    else:
        # Fallback to basic config
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    return logging.getLogger(__name__)


logger = setup_logging()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    _ = frame  # Unused but required by signal handler signature
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Reddit Producer - Stream Reddit data to Kafka'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--stream-type',
        type=str,
        choices=['both', 'submissions', 'comments'],
        default='submissions',
        help='Type of content to stream (default: submissions)'
    )

    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Run in test mode (limited duration)'
    )

    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Duration to run in test mode (seconds, default: 60)'
    )

    return parser.parse_args()


def main():
    """Main application entry point"""
    # Parse arguments
    args = parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 80)
    logger.info("Reddit Producer Starting")
    logger.info("=" * 80)

    try:
        # Load configuration
        config = Config(args.config)
        logger.info(f"Configuration loaded from: {args.config}")
        logger.info(f"Target subreddits: {config['reddit']['subreddits']}")
        logger.info(f"Kafka topic: {config['kafka']['topic']}")
        logger.info(f"Stream type: {args.stream_type}")

        if args.test_mode:
            logger.info(f"Running in TEST MODE for {args.duration} seconds")

        # Initialize Kafka producer
        logger.info("Initializing Kafka producer...")
        kafka_producer = RedditKafkaProducer(config.to_dict())

        # Initialize Reddit stream
        logger.info("Initializing Reddit stream...")
        reddit_stream = RedditStream(config.to_dict(), kafka_producer)

        # Start stream threads
        threads = []

        if args.stream_type in ['both', 'submissions']:
            logger.info("Starting submission stream thread...")
            submission_thread = Thread(
                target=reddit_stream.stream_submissions,
                name='SubmissionStream',
                daemon=True
            )
            submission_thread.start()
            threads.append(submission_thread)

        if args.stream_type in ['both', 'comments']:
            logger.info("Starting comment stream thread...")
            comment_thread = Thread(
                target=reddit_stream.stream_comments,
                name='CommentStream',
                daemon=True
            )
            comment_thread.start()
            threads.append(comment_thread)

        logger.info("=" * 80)
        logger.info("Reddit Producer Running")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)

        # Keep main thread alive
        if args.test_mode:
            # Run for specified duration in test mode
            import time
            time.sleep(args.duration)
            logger.info(f"Test mode completed ({args.duration}s), shutting down...")
            shutdown_event.set()
        else:
            # Run indefinitely
            while not shutdown_event.is_set():
                for thread in threads:
                    thread.join(timeout=1)

                    # Check if thread died unexpectedly
                    if not thread.is_alive() and not shutdown_event.is_set():
                        logger.error(f"Thread {thread.name} died unexpectedly!")
                        shutdown_event.set()
                        break

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_event.set()

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        shutdown_event.set()
        sys.exit(1)

    finally:
        logger.info("=" * 80)
        logger.info("Shutting Down Reddit Producer")
        logger.info("=" * 80)

        try:
            # Get final stats
            if 'reddit_stream' in locals():
                stats = reddit_stream.get_stats()
                logger.info("Final Statistics:")
                logger.info(f"  Posts processed: {stats['posts_processed']}")
                logger.info(f"  Submissions: {stats['submissions_processed']}")
                logger.info(f"  Comments: {stats['comments_processed']}")
                logger.info(f"  Kafka messages sent: {stats['kafka_messages_sent']}")
                logger.info(f"  Kafka errors: {stats['kafka_errors']}")
                logger.info(f"  DLQ messages: {stats['kafka_dlq_messages']}")
                logger.info(f"  Success rate: {stats['kafka_success_rate']:.2f}%")

            # Flush and close Kafka producer
            if 'kafka_producer' in locals():
                logger.info("Flushing remaining messages...")
                kafka_producer.flush(timeout=30)
                kafka_producer.close()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

        logger.info("=" * 80)
        logger.info("Reddit Producer Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
