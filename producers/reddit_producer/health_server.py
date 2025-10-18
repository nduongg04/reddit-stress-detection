"""
Health check HTTP server for monitoring
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
from threading import Thread
import logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks and metrics"""

    # Class variables shared across all instances
    start_time = time.time()
    reddit_stream = None
    kafka_producer = None

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self._handle_health()
        elif self.path == '/metrics':
            self._handle_metrics()
        elif self.path == '/stats':
            self._handle_stats()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Not found",
                "available_endpoints": ["/health", "/metrics", "/stats"]
            }).encode())

    def _handle_health(self):
        """Return health status"""
        try:
            uptime = time.time() - self.start_time
            health_data = {
                "status": "healthy",
                "uptime_seconds": uptime,
                "uptime_formatted": self._format_uptime(uptime),
                "timestamp": time.time()
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_data, indent=2).encode())

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "unhealthy",
                "error": str(e)
            }).encode())

    def _handle_metrics(self):
        """Return Prometheus metrics"""
        try:
            self.send_response(200)
            self.send_header('Content-type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())

        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            self.send_response(500)
            self.end_headers()

    def _handle_stats(self):
        """Return detailed statistics"""
        try:
            stats = {
                "uptime_seconds": time.time() - self.start_time,
                "timestamp": time.time()
            }

            # Add Reddit stream stats if available
            if self.reddit_stream:
                stream_stats = self.reddit_stream.get_stats()
                stats['stream'] = stream_stats

            # Add Kafka producer stats if available
            if self.kafka_producer:
                producer_stats = self.kafka_producer.get_stats()
                stats['kafka'] = producer_stats

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats, indent=2).encode())

        except Exception as e:
            logger.error(f"Error generating stats: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": str(e)
            }).encode())

    def _format_uptime(self, seconds):
        """Format uptime in human-readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")

        return " ".join(parts)

    def log_message(self, format, *args):
        """Override to suppress request logging"""
        # Only log errors
        if args[1][0] in ['4', '5']:
            logger.warning(f"HTTP {args[1]} - {args[0]}")


class HealthServer:
    """Health check HTTP server"""

    def __init__(self, port=8080, reddit_stream=None, kafka_producer=None):
        """
        Initialize health server

        Args:
            port: Port to listen on
            reddit_stream: RedditStream instance (optional)
            kafka_producer: RedditKafkaProducer instance (optional)
        """
        self.port = port
        self.server = None
        self.thread = None

        # Set class variables for handler
        HealthHandler.reddit_stream = reddit_stream
        HealthHandler.kafka_producer = kafka_producer

        logger.info(f"Health server configured on port {port}")

    def start(self):
        """Start the health server in a background thread"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthHandler)

            self.thread = Thread(
                target=self.server.serve_forever,
                name='HealthServer',
                daemon=True
            )
            self.thread.start()

            logger.info(f"Health server started on http://0.0.0.0:{self.port}")
            logger.info(f"  - Health check: http://0.0.0.0:{self.port}/health")
            logger.info(f"  - Metrics: http://0.0.0.0:{self.port}/metrics")
            logger.info(f"  - Stats: http://0.0.0.0:{self.port}/stats")

        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
            raise

    def stop(self):
        """Stop the health server"""
        if self.server:
            logger.info("Stopping health server...")
            self.server.shutdown()
            self.server.server_close()
            logger.info("Health server stopped")


def start_health_server(port=8080, reddit_stream=None, kafka_producer=None):
    """
    Convenience function to start health server

    Args:
        port: Port to listen on
        reddit_stream: RedditStream instance (optional)
        kafka_producer: RedditKafkaProducer instance (optional)

    Returns:
        HealthServer instance
    """
    server = HealthServer(port, reddit_stream, kafka_producer)
    server.start()
    return server
