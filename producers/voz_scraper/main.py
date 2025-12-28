#!/usr/bin/env python3
"""
Vozforums.com Scraper - Main Application

Scrapes posts directly from vozforums.com and sends to Kafka
"""
import signal
import sys
import logging
import logging.config
from pathlib import Path
import argparse
from threading import Event
import json

from voz_scraper import VozScraper

# Global shutdown event
shutdown_event = Event()

# Setup logging
def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('voz_scraper.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Vozforums Scraper - Scrape posts from vozforums.com'
    )

    parser.add_argument(
        '--target-posts',
        type=int,
        default=10000,
        help='Number of posts to collect (default: 10000)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='data/voz_posts.json',
        help='Output JSON file path (default: data/voz_posts.json)'
    )

    parser.add_argument(
        '--existing-files',
        type=str,
        nargs='+',
        help='Existing JSON files to check for duplicates'
    )

    parser.add_argument(
        '--kafka',
        action='store_true',
        help='Send posts to Kafka (requires Kafka running)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Number of parallel workers (default: 5)'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
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
    logger.info("Vozforums.com Scraper Starting")
    logger.info("=" * 80)
    logger.info(f"Target posts: {args.target_posts}")
    logger.info(f"Output file: {args.output}")
    logger.info(f"Kafka enabled: {args.kafka}")
    logger.info(f"Max workers: {args.max_workers}")
    logger.info(f"Delay between requests: {args.delay}s")
    logger.info("=" * 80)

    try:
        # Initialize Kafka producer if enabled
        kafka_producer = None
        if args.kafka:
            logger.info("Initializing Kafka producer...")
            
            try:
                import yaml
                # Add parent directory to path for imports
                sys.path.insert(0, str(Path(__file__).parent.parent / 'reddit_producer'))
                from utils.kafka_producer import RedditKafkaProducer
                
                # Load Kafka config
                kafka_config_path = Path(__file__).parent.parent / 'reddit_producer' / 'config' / 'config.yaml'
                with open(kafka_config_path, 'r') as f:
                    kafka_config = yaml.safe_load(f)
                
                kafka_producer = RedditKafkaProducer(kafka_config)
                logger.info("✓ Kafka producer initialized")
            except ImportError as e:
                logger.error(f"Failed to initialize Kafka: {e}")
                logger.error("Install dependencies: pip install pyyaml kafka-python")
                sys.exit(1)

        # Initialize scraper
        scraper_config = {
            'scraper': {
                'max_workers': args.max_workers,
                'delay_seconds': args.delay
            }
        }
        
        logger.info("Initializing Voz scraper...")
        scraper = VozScraper(scraper_config, kafka_producer)

        # Load existing URLs to avoid duplicates
        if args.existing_files:
            logger.info(f"Loading existing URLs from {len(args.existing_files)} files...")
            existing_urls = set()
            for filepath in args.existing_files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        existing_posts = json.load(f)
                        urls = {post.get('url') for post in existing_posts if post.get('url')}
                        existing_urls.update(urls)
                        logger.info(f"  Loaded {len(urls)} URLs from {filepath}")
                except Exception as e:
                    logger.warning(f"  Failed to load {filepath}: {e}")
            
            scraper.processed_threads = existing_urls
            logger.info(f"✓ Total {len(existing_urls)} existing URLs loaded (will skip these)")

        # Start scraping
        logger.info("=" * 80)
        logger.info("Starting scraping process...")
        logger.info("=" * 80)

        posts = scraper.scrape_vozforums(target_posts=args.target_posts)

        # Save to file
        if posts:
            logger.info(f"Saving {len(posts)} posts to {args.output}...")
            scraper.save_to_file(posts, args.output)
            logger.info("✓ Posts saved successfully")
        else:
            logger.warning("No posts collected!")

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_event.set()

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

    finally:
        logger.info("=" * 80)
        logger.info("Shutting Down Voz Scraper")
        logger.info("=" * 80)

        try:
            # Flush and close Kafka producer
            if kafka_producer:
                logger.info("Flushing Kafka messages...")
                kafka_producer.flush(timeout=30)
                kafka_producer.close()
                logger.info("✓ Kafka producer closed")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

        logger.info("=" * 80)
        logger.info("Voz Scraper Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
