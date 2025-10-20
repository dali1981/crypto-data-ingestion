"""Data schemas for Binance tick data."""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Trade(BaseModel):
    """Individual trade tick schema."""

    id: int = Field(..., description="Trade ID")
    price: str = Field(..., description="Trade price")
    qty: str = Field(..., alias="qty", description="Trade quantity")
    quote_qty: str = Field(..., alias="quoteQty", description="Quote asset quantity")
    time: int = Field(..., description="Trade timestamp (milliseconds)")
    is_buyer_maker: bool = Field(..., alias="isBuyerMaker", description="Whether buyer is maker")
    is_best_match: bool = Field(..., alias="isBestMatch", description="Whether trade is best price match")
    symbol: str = Field(..., description="Trading symbol")

    class Config:
        populate_by_name = True


class AggTrade(BaseModel):
    """Aggregated trade schema."""

    agg_trade_id: int = Field(..., alias="a", description="Aggregate trade ID")
    price: str = Field(..., alias="p", description="Price")
    quantity: str = Field(..., alias="q", description="Quantity")
    first_trade_id: int = Field(..., alias="f", description="First trade ID")
    last_trade_id: int = Field(..., alias="l", description="Last trade ID")
    timestamp: int = Field(..., alias="T", description="Timestamp")
    is_buyer_maker: bool = Field(..., alias="m", description="Is buyer maker")
    is_best_match: bool = Field(..., alias="M", description="Is best price match")
    symbol: str = Field(..., description="Trading symbol")

    class Config:
        populate_by_name = True


class OrderBookSnapshot(BaseModel):
    """Order book snapshot schema."""

    symbol: str = Field(..., description="Trading symbol")
    timestamp: int = Field(..., description="Snapshot timestamp (milliseconds)")
    last_update_id: int = Field(..., description="Last update ID")
    bids: list = Field(..., description="List of [price, quantity] bid levels")
    asks: list = Field(..., description="List of [price, quantity] ask levels")


class StreamTrade(BaseModel):
    """WebSocket trade stream schema."""

    event_type: str = Field(..., alias="e", description="Event type")
    event_time: int = Field(..., alias="E", description="Event time")
    symbol: str = Field(..., alias="s", description="Symbol")
    trade_id: int = Field(..., alias="t", description="Trade ID")
    price: str = Field(..., alias="p", description="Price")
    quantity: str = Field(..., alias="q", description="Quantity")
    buyer_order_id: int = Field(..., alias="b", description="Buyer order ID")
    seller_order_id: int = Field(..., alias="a", description="Seller order ID")
    trade_time: int = Field(..., alias="T", description="Trade time")
    is_buyer_maker: bool = Field(..., alias="m", description="Is buyer maker")

    class Config:
        populate_by_name = True


class StreamAggTrade(BaseModel):
    """WebSocket aggregated trade stream schema."""

    event_type: str = Field(..., alias="e", description="Event type")
    event_time: int = Field(..., alias="E", description="Event time")
    symbol: str = Field(..., alias="s", description="Symbol")
    agg_trade_id: int = Field(..., alias="a", description="Aggregate trade ID")
    price: str = Field(..., alias="p", description="Price")
    quantity: str = Field(..., alias="q", description="Quantity")
    first_trade_id: int = Field(..., alias="f", description="First trade ID")
    last_trade_id: int = Field(..., alias="l", description="Last trade ID")
    trade_time: int = Field(..., alias="T", description="Trade time")
    is_buyer_maker: bool = Field(..., alias="m", description="Is buyer maker")

    class Config:
        populate_by_name = True


class StreamDepth(BaseModel):
    """WebSocket order book depth update schema."""

    event_type: str = Field(..., alias="e", description="Event type")
    event_time: int = Field(..., alias="E", description="Event time")
    symbol: str = Field(..., alias="s", description="Symbol")
    first_update_id: int = Field(..., alias="U", description="First update ID")
    final_update_id: int = Field(..., alias="u", description="Final update ID")
    bids: list = Field(..., alias="b", description="Bids to be updated")
    asks: list = Field(..., alias="a", description="Asks to be updated")

    class Config:
        populate_by_name = True
