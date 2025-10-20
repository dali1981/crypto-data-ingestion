"""
Real-Time Market Monitoring - CLI Dashboard

Terminal-based dashboard for monitoring real-time market microstructure metrics.

Features:
- Multi-symbol monitoring
- Color-coded metrics display
- Auto-refreshing dashboard
- Live trade feed
- Summary statistics panel

Usage:
    # Single symbol
    uv run python examples/realtime_monitoring.py --symbols BTCUSDT

    # Multiple symbols
    uv run python examples/realtime_monitoring.py --symbols BTCUSDT ETHUSDT BNBUSDT

    # Custom refresh rate
    uv run python examples/realtime_monitoring.py --symbols BTCUSDT --refresh 2

Requirements:
    pip install rich
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List
import sys

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich import box
except ImportError:
    print("Error: 'rich' package not installed")
    print("Install with: uv add rich")
    sys.exit(1)

from binance_tick_data.consumers import RealtimeConsumer, ConsumerConfig
from binance_tick_data.analyzers import (
    OrderFlowAnalyzer,
    LiquidityAnalyzer,
    VolumeProfileAnalyzer,
)

# Suppress logging except errors
logging.basicConfig(level=logging.ERROR)


class MarketMonitor:
    """Real-time market monitoring dashboard."""

    def __init__(self, symbols: List[str], refresh_rate: float = 1.0):
        """
        Initialize market monitor.

        Args:
            symbols: List of trading symbols to monitor
            refresh_rate: Dashboard refresh rate in seconds
        """
        self.symbols = symbols
        self.refresh_rate = refresh_rate
        self.console = Console()

        # Consumer and analyzers
        self.consumer = None
        self.analyzers: Dict[str, Dict] = {}

        # Recent trades buffer for display
        self.recent_trades: Dict[str, List] = {symbol: [] for symbol in symbols}
        self.max_trades_display = 5

        # Statistics
        self.start_time = datetime.now()

    async def initialize(self):
        """Initialize consumer and analyzers."""
        # Create consumer
        config = ConsumerConfig(
            symbols=self.symbols,
            buffer_size=10000,
            update_interval=0.1,
        )
        self.consumer = RealtimeConsumer(config)

        # Create analyzers for each symbol
        for symbol in self.symbols:
            self.analyzers[symbol] = {
                'order_flow': OrderFlowAnalyzer(window_size=60),
                'liquidity': LiquidityAnalyzer(window_size=60),
                'volume_profile': VolumeProfileAnalyzer(window_size=60, price_bins=50),
            }

            # Register analyzers
            for analyzer in self.analyzers[symbol].values():
                self.consumer.register_analyzer(analyzer)

        # Subscribe to trades for display
        def trade_callback(symbol: str, trade):
            side = "BUY" if not trade.isBuyerMaker else "SELL"
            self.recent_trades[symbol].append({
                'time': datetime.fromtimestamp(trade.time / 1000),
                'side': side,
                'price': float(trade.price),
                'qty': float(trade.qty),
            })
            # Keep only recent trades
            if len(self.recent_trades[symbol]) > self.max_trades_display:
                self.recent_trades[symbol].pop(0)

        self.consumer.subscribe_to_trades(trade_callback)

    def create_header(self) -> Panel:
        """Create dashboard header."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        header_text = Text()
        header_text.append("🚀 Real-Time Market Monitor ", style="bold cyan")
        header_text.append(f"| Uptime: {uptime:.0f}s ", style="dim")
        header_text.append(f"| Symbols: {', '.join(self.symbols)} ", style="yellow")
        header_text.append(f"| Refresh: {self.refresh_rate}s", style="dim")

        return Panel(header_text, box=box.ROUNDED, style="cyan")

    def create_metrics_table(self, symbol: str) -> Table:
        """Create metrics table for a symbol."""
        table = Table(
            title=f"[bold cyan]{symbol}[/bold cyan] Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", justify="right", style="yellow", width=20)
        table.add_column("Status", justify="center", width=10)

        if symbol not in self.analyzers:
            table.add_row("No data", "-", "⚠️")
            return table

        # Order flow metrics
        of_metrics = self.analyzers[symbol]['order_flow'].get_current_metrics()
        if of_metrics.get('total_trades', 0) > 0:
            # Buy/Sell counts
            buy_count = of_metrics.get('buy_count', 0)
            sell_count = of_metrics.get('sell_count', 0)
            table.add_row(
                "Buy / Sell Trades",
                f"{buy_count:,} / {sell_count:,}",
                self._get_status_emoji(buy_count > sell_count)
            )

            # Order imbalance
            imbalance = of_metrics.get('order_imbalance', 0)
            imbalance_pct = imbalance * 100
            color = "green" if imbalance > 0 else "red" if imbalance < 0 else "white"
            table.add_row(
                "Order Imbalance",
                f"[{color}]{imbalance_pct:+.2f}%[/{color}]",
                self._get_imbalance_emoji(imbalance)
            )

            # Volume
            buy_vol = of_metrics.get('buy_volume', 0)
            sell_vol = of_metrics.get('sell_volume', 0)
            table.add_row(
                "Buy / Sell Volume",
                f"{buy_vol:.2f} / {sell_vol:.2f}",
                "📊"
            )

        # Liquidity metrics
        liq_metrics = self.analyzers[symbol]['liquidity'].get_current_metrics()
        if liq_metrics.get('trade_count', 0) > 0:
            avg_price = liq_metrics.get('avg_price', 0)
            price_std = liq_metrics.get('price_std', 0)
            table.add_row(
                "Avg Price ± Std",
                f"{avg_price:.2f} ± {price_std:.2f}",
                "💰"
            )

        # Volume profile metrics
        vp_metrics = self.analyzers[symbol]['volume_profile'].get_current_metrics()
        if vp_metrics.get('trade_count', 0) > 0:
            vwap = vp_metrics.get('vwap', 0)
            table.add_row("VWAP", f"{vwap:.2f}", "📈")

            volume_delta = vp_metrics.get('volume_delta', 0)
            delta_color = "green" if volume_delta > 0 else "red" if volume_delta < 0 else "white"
            table.add_row(
                "Volume Delta",
                f"[{delta_color}]{volume_delta:+.4f}[/{delta_color}]",
                "⚖️"
            )

        # Consumer stats
        stats = self.consumer.get_statistics()
        if symbol in stats['symbols_data']:
            symbol_stats = stats['symbols_data'][symbol]
            table.add_row(
                "Total Trades",
                f"{symbol_stats['total_trades']:,}",
                "✅"
            )
            table.add_row(
                "Buffer Usage",
                f"{symbol_stats['utilization']:.1%}",
                "📦"
            )

        return table

    def create_trades_table(self, symbol: str) -> Table:
        """Create recent trades table."""
        table = Table(
            title=f"[bold cyan]{symbol}[/bold cyan] Recent Trades",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold blue",
        )

        table.add_column("Time", style="dim", width=12)
        table.add_column("Side", width=6)
        table.add_column("Price", justify="right", width=12)
        table.add_column("Qty", justify="right", width=10)

        if symbol in self.recent_trades:
            for trade in self.recent_trades[symbol][-self.max_trades_display:]:
                time_str = trade['time'].strftime("%H:%M:%S")
                side_color = "green" if trade['side'] == "BUY" else "red"
                table.add_row(
                    time_str,
                    f"[{side_color}]{trade['side']}[/{side_color}]",
                    f"{trade['price']:.2f}",
                    f"{trade['qty']:.6f}"
                )

        if not self.recent_trades.get(symbol):
            table.add_row("-", "-", "-", "-")

        return table

    def create_dashboard(self) -> Layout:
        """Create complete dashboard layout."""
        layout = Layout()

        # Header
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        layout["header"].update(self.create_header())

        # Body - split by symbols
        if len(self.symbols) == 1:
            symbol = self.symbols[0]
            layout["body"].split_row(
                Layout(self.create_metrics_table(symbol), name="metrics"),
                Layout(self.create_trades_table(symbol), name="trades"),
            )
        else:
            # Multiple symbols - create grid
            rows = []
            for symbol in self.symbols:
                row_layout = Layout()
                row_layout.split_row(
                    Layout(self.create_metrics_table(symbol)),
                    Layout(self.create_trades_table(symbol)),
                )
                rows.append(row_layout)

            layout["body"].split_column(*rows)

        return layout

    @staticmethod
    def _get_status_emoji(is_positive: bool) -> str:
        """Get status emoji."""
        return "🟢" if is_positive else "🔴"

    @staticmethod
    def _get_imbalance_emoji(imbalance: float) -> str:
        """Get imbalance status emoji."""
        if abs(imbalance) < 0.05:
            return "⚪"  # Neutral
        elif imbalance > 0:
            return "🟢"  # Buy pressure
        else:
            return "🔴"  # Sell pressure

    async def run(self):
        """Run the monitoring dashboard."""
        try:
            # Initialize
            await self.initialize()

            # Start consumer
            await self.consumer.start()

            # Display dashboard with live updates
            with Live(self.create_dashboard(), refresh_per_second=1/self.refresh_rate, console=self.console) as live:
                try:
                    while True:
                        await asyncio.sleep(self.refresh_rate)
                        live.update(self.create_dashboard())

                except KeyboardInterrupt:
                    pass

        finally:
            # Cleanup
            if self.consumer:
                await self.consumer.stop()

            # Show final summary
            self.console.print("\n[bold green]✓ Monitoring session complete![/bold green]\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Real-time market monitoring dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor single symbol
  %(prog)s --symbols BTCUSDT

  # Monitor multiple symbols
  %(prog)s --symbols BTCUSDT ETHUSDT BNBUSDT

  # Custom refresh rate (every 2 seconds)
  %(prog)s --symbols BTCUSDT --refresh 2
        """
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['BTCUSDT'],
        help='Trading symbols to monitor (default: BTCUSDT)'
    )

    parser.add_argument(
        '--refresh',
        type=float,
        default=1.0,
        help='Dashboard refresh rate in seconds (default: 1.0)'
    )

    args = parser.parse_args()

    # Create and run monitor
    monitor = MarketMonitor(symbols=args.symbols, refresh_rate=args.refresh)

    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")


if __name__ == "__main__":
    main()
