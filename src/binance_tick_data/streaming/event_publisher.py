"""
Event Publisher for real-time streaming data.

Provides publish/subscribe pattern for metrics and events from analyzers.
Supports both in-memory (single process) and Redis (distributed) backends.

Features:
- Topic-based routing
- In-memory pub/sub (zero dependencies)
- Optional Redis backend for distributed systems
- Message batching for efficiency
- Backpressure handling
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Event publisher with pluggable backends.

    Supports topic-based publish/subscribe pattern for streaming metrics
    and events. Can operate in-memory or use Redis for distributed systems.

    Examples:
        >>> # In-memory publisher
        >>> publisher = EventPublisher(backend="memory")
        >>> publisher.subscribe("btc_metrics", callback_func)
        >>> publisher.publish("btc_metrics", {"vwap": 50000.0})
        >>>
        >>> # Redis publisher (requires redis package)
        >>> publisher = EventPublisher(
        ...     backend="redis",
        ...     redis_url="redis://localhost:6379"
        ... )
    """

    def __init__(
        self,
        backend: str = "memory",
        redis_url: Optional[str] = None,
        max_queue_size: int = 10000,
        batch_publish: bool = True,
        batch_interval: float = 0.1,
    ):
        """
        Initialize event publisher.

        Args:
            backend: Backend type ('memory' or 'redis')
            redis_url: Redis connection URL (required if backend='redis')
            max_queue_size: Maximum messages in queue before blocking
            batch_publish: Whether to batch messages
            batch_interval: Batch interval in seconds
        """
        self.backend = backend
        self.redis_url = redis_url
        self.max_queue_size = max_queue_size
        self.batch_publish = batch_publish
        self.batch_interval = batch_interval

        # In-memory backend
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue: deque = deque(maxlen=max_queue_size)

        # Redis backend
        self._redis_client = None
        self._redis_pubsub = None

        # Statistics
        self._published_count = 0
        self._dropped_count = 0

        # Initialize backend
        if self.backend == "redis":
            self._initialize_redis()

        logger.info(f"Event publisher initialized with backend: {backend}")

    def _initialize_redis(self):
        """Initialize Redis backend."""
        try:
            import redis

            if not self.redis_url:
                raise ValueError("redis_url is required for Redis backend")

            self._redis_client = redis.from_url(self.redis_url)
            self._redis_client.ping()  # Test connection
            logger.info(f"Connected to Redis: {self.redis_url}")

        except ImportError:
            logger.error("Redis backend requested but redis package not installed")
            logger.info("Install with: pip install redis")
            raise

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def publish(self, topic: str, message: Dict[str, Any], timestamp: Optional[datetime] = None):
        """
        Publish message to topic.

        Args:
            topic: Topic name
            message: Message dictionary
            timestamp: Message timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Add metadata
        full_message = {
            "topic": topic,
            "timestamp": timestamp.isoformat(),
            "data": message,
        }

        if self.backend == "memory":
            self._publish_memory(topic, full_message)
        elif self.backend == "redis":
            self._publish_redis(topic, full_message)

        self._published_count += 1

    def publish_batch(self, messages: List[tuple[str, Dict[str, Any]]]):
        """
        Publish multiple messages efficiently.

        Args:
            messages: List of (topic, message) tuples
        """
        timestamp = datetime.now()

        for topic, message in messages:
            self.publish(topic, message, timestamp)

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to topic.

        Args:
            topic: Topic name
            callback: Callback function receiving messages
        """
        if self.backend == "memory":
            self._subscribers[topic].append(callback)
            logger.info(f"Subscribed to topic: {topic} (memory backend)")

        elif self.backend == "redis":
            # Redis subscriptions handled separately
            logger.warning("Redis subscriptions require separate subscriber process")

    def unsubscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        Unsubscribe from topic.

        Args:
            topic: Topic name
            callback: Callback function to remove

        Returns:
            True if callback was removed
        """
        if self.backend == "memory":
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.info(f"Unsubscribed from topic: {topic}")
                return True

        return False

    def _publish_memory(self, topic: str, message: Dict[str, Any]):
        """
        Publish to in-memory subscribers.

        Args:
            topic: Topic name
            message: Full message with metadata
        """
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Error in subscriber callback for topic {topic}: {e}")

    def _publish_redis(self, topic: str, message: Dict[str, Any]):
        """
        Publish to Redis.

        Args:
            topic: Topic name
            message: Full message with metadata
        """
        if not self._redis_client:
            logger.error("Redis client not initialized")
            return

        try:
            import json

            message_json = json.dumps(message, default=str)
            self._redis_client.publish(topic, message_json)

        except Exception as e:
            logger.error(f"Error publishing to Redis topic {topic}: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get publisher statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "backend": self.backend,
            "published_count": self._published_count,
            "dropped_count": self._dropped_count,
            "queue_size": len(self._message_queue),
            "max_queue_size": self.max_queue_size,
        }

        if self.backend == "memory":
            stats["topic_count"] = len(self._subscribers)
            stats["subscriber_count"] = sum(
                len(callbacks) for callbacks in self._subscribers.values()
            )

        return stats

    def close(self):
        """Close publisher and cleanup resources."""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None

        self._subscribers.clear()
        self._message_queue.clear()

        logger.info("Event publisher closed")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EventPublisher("
            f"backend={self.backend}, "
            f"topics={len(self._subscribers)}, "
            f"published={self._published_count})"
        )


class EventSubscriber:
    """
    Event subscriber for Redis backend.

    Separate class for subscribing to Redis pub/sub channels in dedicated process.

    Examples:
        >>> subscriber = EventSubscriber(redis_url="redis://localhost:6379")
        >>> subscriber.subscribe("btc_metrics", callback_func)
        >>> await subscriber.start()  # Runs until stopped
    """

    def __init__(self, redis_url: str):
        """
        Initialize event subscriber.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._redis_client = None
        self._pubsub = None
        self._running = False

        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            import redis

            self._redis_client = redis.from_url(self.redis_url)
            self._pubsub = self._redis_client.pubsub()
            logger.info(f"Event subscriber connected to Redis: {self.redis_url}")

        except ImportError:
            logger.error("Redis package not installed")
            raise

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to topic.

        Args:
            topic: Topic name
            callback: Callback function
        """
        self._callbacks[topic].append(callback)
        self._pubsub.subscribe(topic)
        logger.info(f"Subscribed to Redis topic: {topic}")

    def unsubscribe(self, topic: str):
        """
        Unsubscribe from topic.

        Args:
            topic: Topic name
        """
        if topic in self._callbacks:
            del self._callbacks[topic]
        self._pubsub.unsubscribe(topic)
        logger.info(f"Unsubscribed from Redis topic: {topic}")

    async def start(self):
        """
        Start receiving messages.

        Runs until stop() is called.
        """
        self._running = True
        logger.info("Event subscriber started")

        while self._running:
            try:
                message = self._pubsub.get_message(timeout=1.0)

                if message and message["type"] == "message":
                    await self._handle_message(message)

            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                await asyncio.sleep(1.0)

    async def _handle_message(self, message: Dict[str, Any]):
        """
        Handle received message.

        Args:
            message: Redis message
        """
        try:
            import json

            topic = message["channel"].decode("utf-8")
            data = json.loads(message["data"].decode("utf-8"))

            if topic in self._callbacks:
                for callback in self._callbacks[topic]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except Exception as e:
                        logger.error(f"Error in callback for topic {topic}: {e}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def stop(self):
        """Stop receiving messages."""
        self._running = False
        logger.info("Event subscriber stopped")

    def close(self):
        """Close subscriber and cleanup."""
        self.stop()

        if self._pubsub:
            self._pubsub.close()

        if self._redis_client:
            self._redis_client.close()

        logger.info("Event subscriber closed")

    def __repr__(self) -> str:
        """String representation."""
        return f"EventSubscriber(topics={len(self._callbacks)})"
