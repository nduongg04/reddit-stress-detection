#!/usr/bin/env python3
"""
DLQ Monitor - Monitor and analyze Dead Letter Queue messages

Provides CLI interface for viewing, analyzing, and managing DLQ messages.
"""

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DLQMonitor:
    """Monitor and analyze messages in the Dead Letter Queue."""

    def __init__(
        self,
        bootstrap_servers: str = 'localhost:9092',
        dlq_topic: str = 'reddit.posts.dlq.v1',
        group_id: str = 'dlq-monitor'
    ):
        """
        Initialize DLQ monitor.

        Args:
            bootstrap_servers: Kafka broker address
            dlq_topic: DLQ topic name
            group_id: Consumer group ID
        """
        self.bootstrap_servers = bootstrap_servers
        self.dlq_topic = dlq_topic
        self.group_id = group_id

        try:
            self.consumer = KafkaConsumer(
                dlq_topic,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',
                enable_auto_commit=True
            )
            logger.info(f"DLQ Monitor connected to {dlq_topic}")
        except Exception as e:
            logger.error(f"Failed to initialize DLQ monitor: {e}")
            raise

    def consume_messages(self, max_messages: Optional[int] = None, timeout_ms: int = 10000):
        """
        Consume messages from DLQ.

        Args:
            max_messages: Maximum number of messages to consume (None = all)
            timeout_ms: Consumer poll timeout

        Yields:
            DLQ messages as dictionaries
        """
        count = 0
        no_message_count = 0
        max_empty_polls = 3  # Stop after 3 empty polls

        try:
            while True:
                message_batch = self.consumer.poll(timeout_ms=timeout_ms, max_records=100)

                if not message_batch:
                    no_message_count += 1
                    if no_message_count >= max_empty_polls:
                        break
                    continue

                no_message_count = 0  # Reset on successful poll

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        yield message.value
                        count += 1

                        if max_messages and count >= max_messages:
                            return

        except KeyboardInterrupt:
            logger.info("Consumption interrupted by user")
        finally:
            logger.info(f"Consumed {count} messages from DLQ")

    def analyze(self, max_messages: Optional[int] = 100):
        """
        Analyze DLQ messages and display summary.

        Args:
            max_messages: Maximum messages to analyze
        """
        print(f"\n{'='*60}")
        print(f"DLQ Analysis Report")
        print(f"{'='*60}\n")

        # Give consumer time to stabilize after partition assignment
        import time
        time.sleep(2)

        messages = list(self.consume_messages(max_messages=max_messages))

        if not messages:
            print("No messages found in DLQ")
            return

        # Statistics
        total = len(messages)
        error_types = Counter(msg.get('error_type', 'unknown') for msg in messages)
        severities = Counter(msg.get('severity', 'unknown') for msg in messages)
        producers = Counter(msg.get('producer_id', 'unknown') for msg in messages)
        topics = Counter(msg.get('original_topic', 'unknown') for msg in messages)

        # Top error messages
        error_messages = Counter(msg.get('error_message', '')[:100] for msg in messages)

        # Print summary
        print(f"Total DLQ Messages: {total}")
        print()

        print("Error Types:")
        print("-" * 40)
        for error_type, count in error_types.most_common():
            percentage = (count / total) * 100
            print(f"  {error_type:30} {count:5} ({percentage:5.1f}%)")
        print()

        print("Severity Levels:")
        print("-" * 40)
        for severity, count in severities.most_common():
            percentage = (count / total) * 100
            print(f"  {severity:30} {count:5} ({percentage:5.1f}%)")
        print()

        print("Source Topics:")
        print("-" * 40)
        for topic, count in topics.most_common():
            percentage = (count / total) * 100
            print(f"  {topic:30} {count:5} ({percentage:5.1f}%)")
        print()

        print("Producers:")
        print("-" * 40)
        for producer, count in producers.most_common(5):
            percentage = (count / total) * 100
            print(f"  {producer:30} {count:5} ({percentage:5.1f}%)")
        print()

        print("Top Error Messages:")
        print("-" * 40)
        for error_msg, count in error_messages.most_common(5):
            print(f"  [{count}x] {error_msg}")
        print()

        print(f"{'='*60}\n")

    def display_recent(self, count: int = 10):
        """
        Display most recent DLQ messages.

        Args:
            count: Number of messages to display
        """
        print(f"\n{'='*60}")
        print(f"Recent DLQ Messages (last {count})")
        print(f"{'='*60}\n")

        for i, msg in enumerate(self.consume_messages(max_messages=count), 1):
            print(f"Message {i}:")
            print(f"  Error ID: {msg.get('error_id', 'N/A')}")
            print(f"  Type: {msg.get('error_type', 'N/A')}")
            print(f"  Severity: {msg.get('severity', 'N/A')}")
            print(f"  Topic: {msg.get('original_topic', 'N/A')}")
            print(f"  Producer: {msg.get('producer_id', 'N/A')}")
            print(f"  Timestamp: {msg.get('timestamp', 'N/A')}")
            print(f"  Error: {msg.get('error_message', 'N/A')[:100]}")
            print(f"  Payload: {msg.get('original_payload', 'N/A')[:100]}...")
            print()

    def save_to_file(self, output_file: str, max_messages: Optional[int] = None):
        """
        Save DLQ messages to file for analysis.

        Args:
            output_file: Output file path
            max_messages: Maximum messages to save
        """
        print(f"Saving DLQ messages to {output_file}...")

        count = 0
        with open(output_file, 'w') as f:
            for msg in self.consume_messages(max_messages=max_messages):
                f.write(json.dumps(msg) + '\n')
                count += 1

        print(f"Saved {count} messages to {output_file}")

    def close(self):
        """Close the consumer."""
        if self.consumer:
            self.consumer.close()
            logger.info("DLQ Monitor closed")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='DLQ Monitor - Analyze Dead Letter Queue messages',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--bootstrap-servers',
        default='localhost:9092',
        help='Kafka bootstrap servers'
    )

    parser.add_argument(
        '--topic',
        default='reddit.posts.dlq.v1',
        help='DLQ topic name'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze DLQ messages')
    analyze_parser.add_argument(
        '--max-messages',
        type=int,
        default=100,
        help='Maximum messages to analyze'
    )

    # Recent command
    recent_parser = subparsers.add_parser('recent', help='Show recent DLQ messages')
    recent_parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of messages to display'
    )

    # Save command
    save_parser = subparsers.add_parser('save', help='Save DLQ messages to file')
    save_parser.add_argument(
        '--output',
        required=True,
        help='Output file path'
    )
    save_parser.add_argument(
        '--max-messages',
        type=int,
        default=None,
        help='Maximum messages to save'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # For analyze command, use unique consumer group to always read from beginning
        if args.command == 'analyze':
            import time
            group_id = f'dlq-monitor-analyze-{int(time.time())}'
        else:
            group_id = 'dlq-monitor'

        monitor = DLQMonitor(
            bootstrap_servers=args.bootstrap_servers,
            dlq_topic=args.topic,
            group_id=group_id
        )

        if args.command == 'analyze':
            monitor.analyze(max_messages=args.max_messages)
        elif args.command == 'recent':
            monitor.display_recent(count=args.count)
        elif args.command == 'save':
            monitor.save_to_file(args.output, max_messages=args.max_messages)

        monitor.close()
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
