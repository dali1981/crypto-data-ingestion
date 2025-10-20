"""Binance WebSocket source for real-time data."""

import dlt
from typing import Iterator, List, Optional
import asyncio
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException
import json
from datetime import datetime
from ..config import BinanceConfig


@dlt.source
def binance_realtime_data(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
):
    """
    DLT source for real-time Binance data via WebSocket.

    Args:
        config: BinanceConfig instance
        symbols: List of symbols to stream (defaults to config.symbols)

    Returns:
        DLT source with multiple streaming resources
    """
    symbols = symbols or config.symbols

    return (
        realtime_trades(config, symbols),
        realtime_agg_trades(config, symbols),
        realtime_depth(config, symbols),
    )


@dlt.resource(
    name="realtime_trades",
    write_disposition="append",
    primary_key="trade_id",
)
def realtime_trades(
    config: BinanceConfig,
    symbols: List[str],
) -> Iterator[dict]:
    """
    Stream real-time trade data for specified symbols.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols

    Yields:
        Real-time trade records
    """

    async def stream_trades():
        """Async function to handle WebSocket streaming."""
        client = await AsyncClient.create(config.api_key, config.api_secret)
        bsm = BinanceSocketManager(client)

        # Create multi-socket stream for all symbols
        streams = [f"{symbol.lower()}@trade" for symbol in symbols]

        async with bsm.multiplex_socket(streams) as stream:
            buffer = []
            print(f"Streaming real-time trades for {', '.join(symbols)}...")

            while True:
                try:
                    msg = await stream.recv()

                    if "data" in msg:
                        data = msg["data"]

                        trade_record = {
                            "event_type": data["e"],
                            "event_time": data["E"],
                            "symbol": data["s"],
                            "trade_id": data["t"],
                            "price": data["p"],
                            "quantity": data["q"],
                            "buyer_order_id": data["b"],
                            "seller_order_id": data["a"],
                            "trade_time": data["T"],
                            "is_buyer_maker": data["m"],
                        }

                        buffer.append(trade_record)

                        # Flush buffer when it reaches configured size
                        if len(buffer) >= config.stream_buffer_size:
                            yield buffer
                            buffer = []

                except Exception as e:
                    print(f"Error in trade stream: {e}")
                    await asyncio.sleep(config.reconnect_delay)
                    continue

        await client.close_connection()

    # Run the async stream
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = stream_trades()
        while True:
            try:
                batch = loop.run_until_complete(async_gen.__anext__())
                yield from batch
            except StopAsyncIteration:
                break
    finally:
        loop.close()


@dlt.resource(
    name="realtime_agg_trades",
    write_disposition="append",
    primary_key="agg_trade_id",
)
def realtime_agg_trades(
    config: BinanceConfig,
    symbols: List[str],
) -> Iterator[dict]:
    """
    Stream real-time aggregated trade data for specified symbols.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols

    Yields:
        Real-time aggregated trade records
    """

    async def stream_agg_trades():
        """Async function to handle WebSocket streaming."""
        client = await AsyncClient.create(config.api_key, config.api_secret)
        bsm = BinanceSocketManager(client)

        # Create multi-socket stream for all symbols
        streams = [f"{symbol.lower()}@aggTrade" for symbol in symbols]

        async with bsm.multiplex_socket(streams) as stream:
            buffer = []
            print(f"Streaming aggregated trades for {', '.join(symbols)}...")

            while True:
                try:
                    msg = await stream.recv()

                    if "data" in msg:
                        data = msg["data"]

                        agg_trade_record = {
                            "event_type": data["e"],
                            "event_time": data["E"],
                            "symbol": data["s"],
                            "agg_trade_id": data["a"],
                            "price": data["p"],
                            "quantity": data["q"],
                            "first_trade_id": data["f"],
                            "last_trade_id": data["l"],
                            "trade_time": data["T"],
                            "is_buyer_maker": data["m"],
                        }

                        buffer.append(agg_trade_record)

                        # Flush buffer when it reaches configured size
                        if len(buffer) >= config.stream_buffer_size:
                            yield buffer
                            buffer = []

                except Exception as e:
                    print(f"Error in aggregated trade stream: {e}")
                    await asyncio.sleep(config.reconnect_delay)
                    continue

        await client.close_connection()

    # Run the async stream
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = stream_agg_trades()
        while True:
            try:
                batch = loop.run_until_complete(async_gen.__anext__())
                yield from batch
            except StopAsyncIteration:
                break
    finally:
        loop.close()


@dlt.resource(
    name="realtime_depth",
    write_disposition="append",
)
def realtime_depth(
    config: BinanceConfig,
    symbols: List[str],
    update_speed: str = "100ms",  # or "1000ms"
) -> Iterator[dict]:
    """
    Stream real-time order book depth updates for specified symbols.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols
        update_speed: Update speed - "100ms" or "1000ms"

    Yields:
        Real-time depth update records
    """

    async def stream_depth():
        """Async function to handle WebSocket streaming."""
        client = await AsyncClient.create(config.api_key, config.api_secret)
        bsm = BinanceSocketManager(client)

        # Create multi-socket stream for all symbols
        speed_suffix = "" if update_speed == "1000ms" else "@100ms"
        streams = [f"{symbol.lower()}@depth{speed_suffix}" for symbol in symbols]

        async with bsm.multiplex_socket(streams) as stream:
            buffer = []
            print(f"Streaming order book depth for {', '.join(symbols)}...")

            while True:
                try:
                    msg = await stream.recv()

                    if "data" in msg:
                        data = msg["data"]

                        depth_record = {
                            "event_type": data["e"],
                            "event_time": data["E"],
                            "symbol": data["s"],
                            "first_update_id": data["U"],
                            "final_update_id": data["u"],
                            "bids": data["b"],  # List of [price, quantity]
                            "asks": data["a"],  # List of [price, quantity]
                        }

                        buffer.append(depth_record)

                        # Flush buffer when it reaches configured size
                        if len(buffer) >= config.stream_buffer_size:
                            yield buffer
                            buffer = []

                except Exception as e:
                    print(f"Error in depth stream: {e}")
                    await asyncio.sleep(config.reconnect_delay)
                    continue

        await client.close_connection()

    # Run the async stream
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = stream_depth()
        while True:
            try:
                batch = loop.run_until_complete(async_gen.__anext__())
                yield from batch
            except StopAsyncIteration:
                break
    finally:
        loop.close()
