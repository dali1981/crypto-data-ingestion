"""
Base analyzer interface for market microstructure analysis.

Provides abstract base class that all analyzers must implement.
Supports windowed analysis with configurable time periods.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from ..sources.schemas import AggTrade, Trade


class BaseAnalyzer(ABC):
    """
    Abstract base class for market microstructure analyzers.

    Analyzers process streaming trade data and compute metrics over
    configurable time windows. They can operate in two modes:

    1. Per-trade: Process each trade individually (on_trade)
    2. Window-based: Compute aggregated metrics when window closes (on_window_close)

    Subclasses must implement the abstract methods to define custom analysis logic.

    Examples:
        >>> class MyAnalyzer(BaseAnalyzer):
        ...     def __init__(self, window_size: int = 60):
        ...         super().__init__(name="my_analyzer", window_size=window_size)
        ...         self.trade_count = 0
        ...
        ...     async def on_trade(self, trade: Trade) -> Optional[Dict]:
        ...         self.trade_count += 1
        ...         return None  # No per-trade metrics
        ...
        ...     async def on_window_close(self, window_end: datetime) -> Dict:
        ...         metrics = {"trade_count": self.trade_count}
        ...         self.trade_count = 0  # Reset for next window
        ...         return metrics
        ...
        ...     def get_current_metrics(self) -> Dict:
        ...         return {"trade_count": self.trade_count}
    """

    def __init__(self, name: str, window_size: int = 60, enabled: bool = True):
        """
        Initialize base analyzer.

        Args:
            name: Unique identifier for this analyzer
            window_size: Analysis window size in seconds (default: 60)
            enabled: Whether analyzer is active (default: True)
        """
        self.name = name
        self.window_size = window_size
        self.enabled = enabled
        self._window_start: Optional[datetime] = None
        self._window_end: Optional[datetime] = None

    @abstractmethod
    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """
        Process a single trade.

        Called for each trade received from the stream. Can return metrics
        immediately or accumulate for window-based aggregation.

        Args:
            trade: Individual trade object

        Returns:
            Optional dictionary of metrics. Return None if no per-trade metrics.

        Examples:
            >>> async def on_trade(self, trade: Trade) -> Optional[Dict]:
            ...     # Accumulate for window-based metrics
            ...     self.trades.append(trade)
            ...     return None
            ...
            >>> async def on_trade(self, trade: Trade) -> Optional[Dict]:
            ...     # Immediate per-trade metric
            ...     return {"trade_size_usd": trade.price * trade.quantity}
        """
        pass

    async def on_agg_trade(self, agg_trade: AggTrade) -> Optional[Dict[str, Any]]:
        """
        Process an aggregated trade.

        Default implementation converts to Trade and calls on_trade().
        Override if you need special handling for aggregated trades.

        Args:
            agg_trade: Aggregated trade object

        Returns:
            Optional dictionary of metrics
        """
        # Convert AggTrade to Trade for compatibility
        trade = Trade(
            id=agg_trade.agg_trade_id,
            price=agg_trade.price,
            qty=agg_trade.quantity,
            time=agg_trade.timestamp,
            isBuyerMaker=agg_trade.is_buyer_maker,
            isBestMatch=agg_trade.is_best_match,
        )
        return await self.on_trade(trade)

    @abstractmethod
    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """
        Compute metrics when time window closes.

        Called when the current analysis window completes. Should return
        aggregated metrics for the window and reset internal state for
        the next window.

        Args:
            window_end: End timestamp of the window

        Returns:
            Dictionary of computed metrics for the window

        Examples:
            >>> async def on_window_close(self, window_end: datetime) -> Dict:
            ...     total_volume = sum(t.quantity for t in self.trades)
            ...     avg_price = sum(t.price for t in self.trades) / len(self.trades)
            ...
            ...     metrics = {
            ...         "total_volume": total_volume,
            ...         "avg_price": avg_price,
            ...         "trade_count": len(self.trades),
            ...     }
            ...
            ...     # Reset for next window
            ...     self.trades.clear()
            ...
            ...     return metrics
        """
        pass

    @abstractmethod
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current state of metrics without closing the window.

        Useful for querying analyzer state mid-window or for real-time
        dashboards that need immediate feedback.

        Returns:
            Dictionary of current metric values

        Examples:
            >>> def get_current_metrics(self) -> Dict:
            ...     return {
            ...         "trade_count": len(self.trades),
            ...         "current_vwap": self._compute_vwap(),
            ...         "buy_sell_ratio": self._compute_ratio(),
            ...     }
        """
        pass

    def reset(self) -> None:
        """
        Reset analyzer state.

        Called when starting a new analysis session or when errors occur.
        Subclasses should override to clear their internal state.

        Examples:
            >>> def reset(self) -> None:
            ...     super().reset()
            ...     self.trades.clear()
            ...     self.buy_volume = 0
            ...     self.sell_volume = 0
        """
        self._window_start = None
        self._window_end = None

    def set_window(self, start: datetime, end: datetime) -> None:
        """
        Set the current analysis window.

        Args:
            start: Window start timestamp
            end: Window end timestamp
        """
        self._window_start = start
        self._window_end = end

    @property
    def window_start(self) -> Optional[datetime]:
        """Get current window start time."""
        return self._window_start

    @property
    def window_end(self) -> Optional[datetime]:
        """Get current window end time."""
        return self._window_end

    def __repr__(self) -> str:
        """String representation of analyzer."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"window_size={self.window_size}s, "
            f"enabled={self.enabled})"
        )


class SimpleAnalyzer(BaseAnalyzer):
    """
    Example implementation of a simple analyzer.

    Counts trades and computes basic statistics within each window.
    Useful as a template for creating custom analyzers.
    """

    def __init__(self, window_size: int = 60):
        """Initialize simple analyzer."""
        super().__init__(name="simple", window_size=window_size)
        self.trade_count = 0
        self.total_volume = 0.0
        self.buy_count = 0
        self.sell_count = 0

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process individual trade."""
        self.trade_count += 1
        self.total_volume += trade.qty

        if not trade.isBuyerMaker:
            self.buy_count += 1
        else:
            self.sell_count += 1

        return None  # No per-trade metrics

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Compute window metrics."""
        metrics = {
            "trade_count": self.trade_count,
            "total_volume": self.total_volume,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "buy_sell_ratio": (
                self.buy_count / self.sell_count if self.sell_count > 0 else float("inf")
            ),
        }

        # Reset for next window
        self.trade_count = 0
        self.total_volume = 0.0
        self.buy_count = 0
        self.sell_count = 0

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metric values."""
        return {
            "trade_count": self.trade_count,
            "total_volume": self.total_volume,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
        }
