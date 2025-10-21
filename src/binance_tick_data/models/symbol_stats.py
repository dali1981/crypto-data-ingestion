"""
Symbol statistics model with rich display capabilities.

This model encapsulates trading statistics for a symbol with proper
type safety, validation, and human-readable display methods.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, computed_field


class SymbolStats(BaseModel):
    """
    Trading statistics for a symbol.

    This model provides a structured representation of symbol statistics
    with automatic formatting and display capabilities.
    """

    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    trade_count: int = Field(..., description="Total number of trades")

    # Price statistics
    min_price: Optional[float] = Field(None, description="Minimum price")
    max_price: Optional[float] = Field(None, description="Maximum price")
    avg_price: Optional[float] = Field(None, description="Average price")

    # Volume statistics
    total_volume: Optional[float] = Field(None, description="Total volume traded")

    # Order flow
    sell_count: int = Field(0, description="Number of sell orders")
    buy_count: int = Field(0, description="Number of buy orders")
    buy_sell_ratio: Optional[float] = Field(None, description="Buy/Sell ratio")

    # Time range
    first_trade_time: Optional[datetime] = Field(None, description="First trade timestamp")
    last_trade_time: Optional[datetime] = Field(None, description="Last trade timestamp")

    @computed_field
    @property
    def price_range(self) -> Optional[float]:
        """Calculate price range (max - min)."""
        if self.min_price is not None and self.max_price is not None:
            return self.max_price - self.min_price
        return None

    @computed_field
    @property
    def price_change_pct(self) -> Optional[float]:
        """Calculate price change percentage."""
        if self.min_price is not None and self.max_price is not None and self.min_price > 0:
            return ((self.max_price - self.min_price) / self.min_price) * 100
        return None

    @computed_field
    @property
    def net_order_flow(self) -> int:
        """Calculate net order flow (buy - sell)."""
        return self.buy_count - self.sell_count

    @computed_field
    @property
    def order_imbalance(self) -> Optional[float]:
        """Calculate order imbalance ratio (-1 to 1)."""
        total = self.buy_count + self.sell_count
        if total > 0:
            return (self.buy_count - self.sell_count) / total
        return None

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"Symbol Statistics: {self.symbol}",
            "=" * 60,
            "",
            "Trading Activity:",
            f"  Total trades: {self.trade_count:,}",
            f"  Buy orders: {self.buy_count:,}",
            f"  Sell orders: {self.sell_count:,}",
            f"  Buy/Sell ratio: {self.buy_sell_ratio:.4f}" if self.buy_sell_ratio is not None else "  Buy/Sell ratio: N/A",
            f"  Order imbalance: {self.order_imbalance:+.4f}" if self.order_imbalance is not None else "  Order imbalance: N/A",
            "",
            "Price Statistics:",
            f"  Min: ${self.min_price:,.2f}" if self.min_price is not None else "  Min: N/A",
            f"  Max: ${self.max_price:,.2f}" if self.max_price is not None else "  Max: N/A",
            f"  Avg: ${self.avg_price:,.2f}" if self.avg_price is not None else "  Avg: N/A",
            f"  Range: ${self.price_range:,.2f}" if self.price_range is not None else "  Range: N/A",
            f"  Change: {self.price_change_pct:+.2f}%" if self.price_change_pct is not None else "  Change: N/A",
            "",
            "Volume:",
            f"  Total: {self.total_volume:,.4f}" if self.total_volume is not None else "  Total: N/A",
            "",
            "Time Range:",
            f"  First trade: {self.first_trade_time}" if self.first_trade_time is not None else "  First trade: N/A",
            f"  Last trade: {self.last_trade_time}" if self.last_trade_time is not None else "  Last trade: N/A",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"SymbolStats(symbol={self.symbol!r}, trades={self.trade_count:,}, "
            f"price_range=${self.min_price:.2f}-${self.max_price:.2f})"
            if self.min_price is not None and self.max_price is not None
            else f"SymbolStats(symbol={self.symbol!r}, trades={self.trade_count:,})"
        )

    def _repr_html_(self) -> str:
        """
        Jupyter notebook HTML representation.

        This enables rich display in Jupyter notebooks automatically.
        """
        def format_value(value, value_type="number"):
            """Format value for HTML display."""
            if value is None:
                return '<span style="color: #999;">N/A</span>'

            if value_type == "price":
                return f'<span style="color: #2e7d32; font-weight: bold;">${value:,.2f}</span>'
            elif value_type == "volume":
                return f'<span style="color: #1976d2; font-weight: bold;">{value:,.4f}</span>'
            elif value_type == "count":
                return f'<span style="font-weight: bold;">{value:,}</span>'
            elif value_type == "ratio":
                color = "#2e7d32" if value > 0 else "#d32f2f"
                return f'<span style="color: {color}; font-weight: bold;">{value:+.4f}</span>'
            elif value_type == "pct":
                color = "#2e7d32" if value > 0 else "#d32f2f"
                return f'<span style="color: {color}; font-weight: bold;">{value:+.2f}%</span>'
            else:
                return str(value)

        html = f"""
        <div style="font-family: monospace; border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #f9f9f9;">
            <h3 style="margin-top: 0; color: #333;">📊 {self.symbol} Statistics</h3>

            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background-color: #e3f2fd;">
                    <td colspan="2" style="padding: 8px; font-weight: bold; border-bottom: 2px solid #90caf9;">
                        Trading Activity
                    </td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px; width: 40%;">Total Trades</td>
                    <td style="padding: 5px 8px;">{format_value(self.trade_count, "count")}</td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">Buy Orders</td>
                    <td style="padding: 5px 8px;">{format_value(self.buy_count, "count")}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Sell Orders</td>
                    <td style="padding: 5px 8px;">{format_value(self.sell_count, "count")}</td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">Buy/Sell Ratio</td>
                    <td style="padding: 5px 8px;">{format_value(self.buy_sell_ratio, "ratio")}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Order Imbalance</td>
                    <td style="padding: 5px 8px;">{format_value(self.order_imbalance, "ratio")}</td>
                </tr>

                <tr style="background-color: #e8f5e9;">
                    <td colspan="2" style="padding: 8px; font-weight: bold; border-bottom: 2px solid #a5d6a7; border-top: 2px solid #ddd;">
                        Price Statistics
                    </td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">Min Price</td>
                    <td style="padding: 5px 8px;">{format_value(self.min_price, "price")}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Max Price</td>
                    <td style="padding: 5px 8px;">{format_value(self.max_price, "price")}</td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">Avg Price</td>
                    <td style="padding: 5px 8px;">{format_value(self.avg_price, "price")}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Price Range</td>
                    <td style="padding: 5px 8px;">{format_value(self.price_range, "price")}</td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">Price Change %</td>
                    <td style="padding: 5px 8px;">{format_value(self.price_change_pct, "pct")}</td>
                </tr>

                <tr style="background-color: #e1f5fe;">
                    <td colspan="2" style="padding: 8px; font-weight: bold; border-bottom: 2px solid #81d4fa; border-top: 2px solid #ddd;">
                        Volume
                    </td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Total Volume</td>
                    <td style="padding: 5px 8px;">{format_value(self.total_volume, "volume")}</td>
                </tr>

                <tr style="background-color: #fff3e0;">
                    <td colspan="2" style="padding: 8px; font-weight: bold; border-bottom: 2px solid #ffcc80; border-top: 2px solid #ddd;">
                        Time Range
                    </td>
                </tr>
                <tr style="background-color: #fff;">
                    <td style="padding: 5px 8px;">First Trade</td>
                    <td style="padding: 5px 8px;">{format_value(self.first_trade_time)}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 8px;">Last Trade</td>
                    <td style="padding: 5px 8px;">{format_value(self.last_trade_time)}</td>
                </tr>
            </table>
        </div>
        """
        return html

    @classmethod
    def from_dict(cls, data: dict) -> "SymbolStats":
        """
        Create SymbolStats from dictionary.

        This is useful for converting repository results to model objects.

        Args:
            data: Dictionary with statistics data

        Returns:
            SymbolStats instance
        """
        return cls(**data)

    def to_dict(self) -> dict:
        """
        Convert to dictionary (including computed fields).

        Returns:
            Dictionary with all fields including computed ones
        """
        return {
            "symbol": self.symbol,
            "trade_count": self.trade_count,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "avg_price": self.avg_price,
            "total_volume": self.total_volume,
            "sell_count": self.sell_count,
            "buy_count": self.buy_count,
            "buy_sell_ratio": self.buy_sell_ratio,
            "first_trade_time": self.first_trade_time,
            "last_trade_time": self.last_trade_time,
            # Computed fields
            "price_range": self.price_range,
            "price_change_pct": self.price_change_pct,
            "net_order_flow": self.net_order_flow,
            "order_imbalance": self.order_imbalance,
        }
