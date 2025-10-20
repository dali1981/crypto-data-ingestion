"""
Real-time streaming consumer for Binance market data.

Provides high-throughput, low-latency access to live trade data via WebSocket.
Supports multiple symbols, pluggable analyzers, and efficient in-memory buffering.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from binance import AsyncClient, BinanceSocketManager

from ..analyzers.base_analyzer import BaseAnalyzer
from ..sources.schemas import Trade, StreamTrade, StreamDepth
from ..streaming.ring_buffer import RingBuffer
from .consumer_config import ConsumerConfig

logger = logging.getLogger(__name__)


class RealtimeConsumer:
    """
    Real-time consumer for streaming Binance trade data.

    Connects to Binance WebSocket streams, buffers trades in memory,
    and dispatches to registered analyzers for processing.

    Features:
    - Multi-symbol support with connection pooling
    - Efficient ring buffer for recent trades
    - Pluggable analyzer architecture
    - Automatic reconnection with exponential backoff
    - Async/await for non-blocking I/O

    Examples:
        >>> config = ConsumerConfig(symbols=["BTCUSDT", "ETHUSDT"])
        >>> consumer = RealtimeConsumer(config)
        >>>
        >>> # Register analyzers
        >>> consumer.register_analyzer(OrderFlowAnalyzer())
        >>> consumer.register_analyzer(LiquidityAnalyzer())
        >>>
        >>> # Start consuming
        >>> await consumer.start()
        >>> # ... let it run ...
        >>> await consumer.stop()
    """

    def __init__(self, config: ConsumerConfig):
        """
        Initialize real-time consumer.

        Args:
            config: Consumer configuration
        """
        self.config = config
        self._client: Optional[AsyncClient] = None
        self._socket_manager: Optional[BinanceSocketManager] = None

        # Per-symbol ring buffers
        self._buffers: Dict[str, RingBuffer[Trade]] = {}

        # Registered analyzers
        self._analyzers: List[BaseAnalyzer] = []

        # Event callbacks
        self._trade_callbacks: List[Callable[[str, Trade], None]] = []
        self._depth_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # Order book tracking (if enabled)
        self._orderbooks: Dict[str, Dict[str, Any]] = {}  # symbol -> {bids, asks, last_update}

        # Connection state
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Statistics
        self._trade_count: Dict[str, int] = {}
        self._depth_update_count: Dict[str, int] = {}
        self._start_time: Optional[datetime] = None

        logger.info(f"Initialized RealtimeConsumer for symbols: {config.symbols}")

    async def start(self) -> None:
        """
        Start consuming from WebSocket streams.

        Establishes connections for all configured symbols and begins
        processing trades.

        Raises:
            RuntimeError: If consumer is already running
        """
        if self._running:
            raise RuntimeError("Consumer is already running")

        logger.info("Starting realtime consumer...")
        self._running = True
        self._start_time = datetime.now()

        # Initialize Binance async client
        self._client = await AsyncClient.create()
        self._socket_manager = BinanceSocketManager(self._client)

        # Create buffers for each symbol
        for symbol in self.config.symbols:
            self._buffers[symbol] = RingBuffer[Trade](capacity=self.config.buffer_size)
            self._trade_count[symbol] = 0
            self._depth_update_count[symbol] = 0

            # Initialize order book if enabled
            if self.config.stream_orderbook:
                self._orderbooks[symbol] = {
                    "bids": [],
                    "asks": [],
                    "last_update_id": 0,
                    "last_update_time": None
                }

        # Start WebSocket streams for each symbol
        for symbol in self.config.symbols:
            # Start trade stream
            task = asyncio.create_task(self._consume_symbol(symbol))
            self._tasks.append(task)

            # Start order book depth stream if enabled
            if self.config.stream_orderbook:
                task = asyncio.create_task(self._consume_depth(symbol))
                self._tasks.append(task)

        stream_count = len(self._tasks)
        stream_types = ["trades"]
        if self.config.stream_orderbook:
            stream_types.append("depth")

        logger.info(f"Started {stream_count} WebSocket streams ({', '.join(stream_types)})")

    async def stop(self) -> None:
        """
        Stop consuming and cleanup resources.

        Gracefully shuts down all WebSocket connections and waits for
        pending tasks to complete.
        """
        if not self._running:
            return

        logger.info("Stopping realtime consumer...")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Close socket manager and client
        if self._socket_manager:
            # BinanceSocketManager doesn't have explicit close
            pass

        if self._client:
            await self._client.close_connection()
            self._client = None

        logger.info("Realtime consumer stopped")

    async def _consume_symbol(self, symbol: str) -> None:
        """
        Consume trades for a single symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
        """
        reconnect_count = 0

        while self._running:
            try:
                logger.info(f"Starting WebSocket stream for {symbol}")

                # Create trade stream
                stream = self._socket_manager.trade_socket(symbol)

                # Start the stream
                async with stream as ts:
                    reconnect_count = 0  # Reset on successful connection

                    while self._running:
                        msg = await ts.recv()

                        try:
                            await self._process_trade(symbol, msg)
                        except Exception as e:
                            logger.error(f"Error processing trade for {symbol}: {e}")

            except Exception as e:
                if not self._running:
                    break

                reconnect_count += 1
                logger.error(
                    f"WebSocket error for {symbol} (attempt {reconnect_count}): {e}"
                )

                # Check max reconnect attempts
                if (
                    self.config.max_reconnect_attempts > 0
                    and reconnect_count >= self.config.max_reconnect_attempts
                ):
                    logger.error(
                        f"Max reconnection attempts reached for {symbol}, stopping stream"
                    )
                    break

                # Exponential backoff
                delay = min(self.config.reconnect_delay * (2 ** (reconnect_count - 1)), 300)
                logger.info(f"Reconnecting {symbol} in {delay}s...")
                await asyncio.sleep(delay)

    async def _process_trade(self, symbol: str, msg: Dict[str, Any]) -> None:
        """
        Process a single trade message.

        Args:
            symbol: Trading pair
            msg: Trade message from WebSocket
        """
        # Parse WebSocket message using StreamTrade schema
        stream_trade = StreamTrade(**msg)

        # Convert to internal Trade format for analyzers
        # Note: WebSocket trades don't have quoteQty, calculate it
        quote_qty = str(float(stream_trade.price) * float(stream_trade.quantity))

        trade = Trade(
            id=stream_trade.trade_id,
            price=stream_trade.price,
            qty=stream_trade.quantity,
            quoteQty=quote_qty,
            time=stream_trade.trade_time,
            isBuyerMaker=stream_trade.is_buyer_maker,
            isBestMatch=stream_trade.is_best_match,
            symbol=stream_trade.symbol,
        )

        # Add to ring buffer
        self._buffers[symbol].append(trade)
        self._trade_count[symbol] += 1

        # Notify callbacks
        for callback in self._trade_callbacks:
            try:
                callback(symbol, trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")

        # Process with analyzers
        for analyzer in self._analyzers:
            if analyzer.enabled:
                try:
                    metrics = await analyzer.on_trade(trade)
                    if metrics:
                        logger.debug(f"{analyzer.name} metrics: {metrics}")
                except Exception as e:
                    logger.error(f"Error in analyzer {analyzer.name}: {e}")

    async def _consume_depth(self, symbol: str) -> None:
        """
        Consume order book depth updates for a single symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
        """
        reconnect_count = 0

        while self._running:
            try:
                logger.info(f"Starting depth stream for {symbol}")

                # Determine update speed suffix
                speed_suffix = "@100ms" if self.config.orderbook_update_speed == "100ms" else ""

                # Create depth socket with appropriate speed
                stream = self._socket_manager.depth_socket(symbol, depth=str(self.config.orderbook_depth_levels))

                # Start the stream
                async with stream as ds:
                    reconnect_count = 0  # Reset on successful connection

                    while self._running:
                        msg = await ds.recv()

                        try:
                            await self._process_depth(symbol, msg)
                        except Exception as e:
                            logger.error(f"Error processing depth for {symbol}: {e}")

            except Exception as e:
                if not self._running:
                    break

                reconnect_count += 1
                logger.error(
                    f"Depth stream error for {symbol} (attempt {reconnect_count}): {e}"
                )

                # Check max reconnect attempts
                if (
                    self.config.max_reconnect_attempts > 0
                    and reconnect_count >= self.config.max_reconnect_attempts
                ):
                    logger.error(
                        f"Max reconnection attempts reached for {symbol} depth stream, stopping"
                    )
                    break

                # Exponential backoff
                delay = min(self.config.reconnect_delay * (2 ** (reconnect_count - 1)), 300)
                logger.info(f"Reconnecting {symbol} depth in {delay}s...")
                await asyncio.sleep(delay)

    async def _process_depth(self, symbol: str, msg: Dict[str, Any]) -> None:
        """
        Process a single depth update message.

        Args:
            symbol: Trading pair
            msg: Depth message from WebSocket
        """
        # Parse depth update
        # Note: depth_socket sends full snapshots with "bids" and "asks" keys
        bids = [[float(price), float(qty)] for price, qty in msg.get("bids", [])]
        asks = [[float(price), float(qty)] for price, qty in msg.get("asks", [])]

        # Update local order book with full snapshot
        orderbook = self._orderbooks[symbol]
        orderbook["bids"] = bids  # Already sorted descending by Binance
        orderbook["asks"] = asks  # Already sorted ascending by Binance

        # Update metadata
        orderbook["last_update_id"] = msg.get("lastUpdateId", 0)
        orderbook["last_update_time"] = datetime.now()

        self._depth_update_count[symbol] += 1

        # Notify callbacks
        depth_data = {
            "symbol": symbol,
            "bids": orderbook["bids"],
            "asks": orderbook["asks"],
            "timestamp": orderbook["last_update_time"],
        }

        for callback in self._depth_callbacks:
            try:
                callback(symbol, depth_data)
            except Exception as e:
                logger.error(f"Error in depth callback: {e}")

        # Notify orderbook analyzers
        from ..analyzers.liquidity import OrderBookLiquidityAnalyzer

        for analyzer in self._analyzers:
            if isinstance(analyzer, OrderBookLiquidityAnalyzer) and analyzer.enabled:
                try:
                    analyzer.process_orderbook_snapshot(
                        timestamp=depth_data["timestamp"],
                        bids=[(b[0], b[1]) for b in depth_data["bids"]],
                        asks=[(a[0], a[1]) for a in depth_data["asks"]],
                    )
                except Exception as e:
                    logger.error(f"Error in orderbook analyzer {analyzer.name}: {e}")

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        """
        Register an analyzer to process trades.

        Args:
            analyzer: Analyzer instance

        Raises:
            ValueError: If analyzer with same name already registered
        """
        if any(a.name == analyzer.name for a in self._analyzers):
            raise ValueError(f"Analyzer '{analyzer.name}' already registered")

        self._analyzers.append(analyzer)
        logger.info(f"Registered analyzer: {analyzer.name}")

    def unregister_analyzer(self, name: str) -> bool:
        """
        Unregister an analyzer by name.

        Args:
            name: Analyzer name

        Returns:
            True if analyzer was removed, False if not found
        """
        for i, analyzer in enumerate(self._analyzers):
            if analyzer.name == name:
                self._analyzers.pop(i)
                logger.info(f"Unregistered analyzer: {name}")
                return True
        return False

    def subscribe_to_trades(self, callback: Callable[[str, Trade], None]) -> None:
        """
        Subscribe to trade events.

        Args:
            callback: Function called for each trade (symbol, trade)
        """
        self._trade_callbacks.append(callback)

    def subscribe_to_depth(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Subscribe to order book depth events.

        Args:
            callback: Function called for each depth update (symbol, depth_data)
                     depth_data contains: {symbol, bids, asks, timestamp}
        """
        self._depth_callbacks.append(callback)

    def get_recent_trades(self, symbol: str, n: int = 100) -> List[Trade]:
        """
        Get recent trades from buffer.

        Args:
            symbol: Trading pair
            n: Number of recent trades to retrieve

        Returns:
            List of recent trades (oldest to newest)

        Raises:
            KeyError: If symbol not being tracked
        """
        if symbol not in self._buffers:
            raise KeyError(f"Symbol {symbol} not being tracked")

        return self._buffers[symbol].get_recent(n)

    def get_all_trades(self, symbol: str) -> List[Trade]:
        """
        Get all trades from buffer.

        Args:
            symbol: Trading pair

        Returns:
            List of all buffered trades

        Raises:
            KeyError: If symbol not being tracked
        """
        if symbol not in self._buffers:
            raise KeyError(f"Symbol {symbol} not being tracked")

        return self._buffers[symbol].get_all()

    def get_trades_since(self, symbol: str, timestamp: datetime) -> List[Trade]:
        """
        Get trades since specified timestamp.

        Args:
            symbol: Trading pair
            timestamp: Cutoff timestamp

        Returns:
            List of trades after timestamp

        Raises:
            KeyError: If symbol not being tracked
        """
        if symbol not in self._buffers:
            raise KeyError(f"Symbol {symbol} not being tracked")

        return self._buffers[symbol].get_since_time(timestamp, time_field="time")

    def get_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current order book snapshot.

        Args:
            symbol: Trading pair

        Returns:
            Order book data or None if not available

        Raises:
            KeyError: If symbol not being tracked
            ValueError: If order book streaming not enabled
        """
        if symbol not in self.config.symbols:
            raise KeyError(f"Symbol {symbol} not being tracked")

        if not self.config.stream_orderbook:
            raise ValueError("Order book streaming is not enabled")

        return self._orderbooks.get(symbol)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get consumer statistics.

        Returns:
            Dictionary with statistics for each symbol
        """
        stats = {
            "running": self._running,
            "symbols": list(self.config.symbols),
            "analyzer_count": len(self._analyzers),
            "analyzers": [a.name for a in self._analyzers],
        }

        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
            stats["uptime_seconds"] = uptime

        # Per-symbol stats
        symbol_stats = {}
        for symbol in self.config.symbols:
            if symbol in self._buffers:
                buffer_stats = self._buffers[symbol].get_stats()
                symbol_stats[symbol] = {
                    **buffer_stats,
                    "total_trades": self._trade_count.get(symbol, 0),
                }

                # Add order book stats if enabled
                if self.config.stream_orderbook:
                    symbol_stats[symbol]["depth_updates"] = self._depth_update_count.get(symbol, 0)
                    orderbook = self._orderbooks.get(symbol, {})
                    symbol_stats[symbol]["orderbook_levels"] = {
                        "bids": len(orderbook.get("bids", [])),
                        "asks": len(orderbook.get("asks", [])),
                    }

        stats["symbols_data"] = symbol_stats

        return stats

    def __repr__(self) -> str:
        """String representation."""
        status = "running" if self._running else "stopped"
        return (
            f"RealtimeConsumer("
            f"symbols={self.config.symbols}, "
            f"analyzers={len(self._analyzers)}, "
            f"status={status})"
        )
