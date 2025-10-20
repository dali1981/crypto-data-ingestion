"""Binance REST API source for historical data."""

import dlt
from typing import Iterator, Optional, List
from datetime import datetime, timedelta
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from ..config import BinanceConfig


@dlt.source
def binance_historical_data(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """
    DLT source for historical Binance data.

    Args:
        config: BinanceConfig instance
        symbols: List of symbols to fetch (defaults to config.symbols)
        start_date: Start date in YYYY-MM-DD format (defaults to config.historical_start_date)

    Returns:
        DLT source with multiple resources
    """
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    return (
        historical_trades(config, symbols, start_date),
        aggregated_trades(config, symbols, start_date),
        order_book_snapshots(config, symbols),
    )


@dlt.resource(
    name="trades",
    write_disposition="append",
    primary_key="id",
)
def historical_trades(
    config: BinanceConfig,
    symbols: List[str],
    start_date: str,
) -> Iterator[dict]:
    """
    Fetch historical trade data for specified symbols.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols
        start_date: Start date in YYYY-MM-DD format

    Yields:
        Trade records with symbol, price, quantity, timestamp, etc.
    """
    client = Client(config.api_key, config.api_secret)
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)

    for symbol in symbols:
        print(f"Fetching historical trades for {symbol}...")

        try:
            # Get trades starting from start_date
            from_id = None
            batch_count = 0

            while True:
                # Binance allows fetching 1000 trades per request
                if from_id:
                    trades = client.get_historical_trades(
                        symbol=symbol,
                        limit=1000,
                        fromId=from_id
                    )
                else:
                    # Get recent trades to start
                    trades = client.get_recent_trades(symbol=symbol, limit=1000)

                if not trades:
                    break

                # Filter trades by start_date
                filtered_trades = [
                    {
                        "id": int(trade["id"]),
                        "price": trade["price"],
                        "qty": trade["qty"],
                        "quoteQty": trade["quoteQty"],
                        "time": int(trade["time"]),
                        "isBuyerMaker": trade["isBuyerMaker"],
                        "isBestMatch": trade["isBestMatch"],
                        "symbol": symbol,
                    }
                    for trade in trades
                    if int(trade["time"]) >= start_ts
                ]

                if filtered_trades:
                    yield from filtered_trades
                    batch_count += len(filtered_trades)
                    print(f"  Fetched {batch_count} trades for {symbol}...")

                # Get next batch
                from_id = trades[-1]["id"] + 1

                # Rate limiting: respect Binance API limits
                time.sleep(0.1)  # 10 requests per second max

                # Stop if we've reached current time
                if trades[-1]["time"] >= int(time.time() * 1000):
                    break

        except BinanceAPIException as e:
            print(f"Error fetching trades for {symbol}: {e}")
            continue


@dlt.resource(
    name="agg_trades",
    write_disposition="append",
    primary_key="agg_trade_id",
)
def aggregated_trades(
    config: BinanceConfig,
    symbols: List[str],
    start_date: str,
) -> Iterator[dict]:
    """
    Fetch aggregated trade data for specified symbols.

    Aggregated trades are more efficient than individual trades
    and suitable for most analysis purposes.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols
        start_date: Start date in YYYY-MM-DD format

    Yields:
        Aggregated trade records
    """
    client = Client(config.api_key, config.api_secret)
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)

    for symbol in symbols:
        print(f"Fetching aggregated trades for {symbol}...")

        try:
            from_id = None
            batch_count = 0

            while True:
                if from_id:
                    trades = client.get_aggregate_trades(
                        symbol=symbol,
                        limit=1000,
                        fromId=from_id
                    )
                else:
                    trades = client.get_aggregate_trades(
                        symbol=symbol,
                        limit=1000,
                        startTime=start_ts
                    )

                if not trades:
                    break

                # Transform to match schema
                transformed_trades = [
                    {
                        "agg_trade_id": trade["a"],
                        "price": trade["p"],
                        "quantity": trade["q"],
                        "first_trade_id": trade["f"],
                        "last_trade_id": trade["l"],
                        "timestamp": trade["T"],
                        "is_buyer_maker": trade["m"],
                        "is_best_match": trade["M"],
                        "symbol": symbol,
                    }
                    for trade in trades
                ]

                # Yield in smaller chunks to enable incremental loading
                yield transformed_trades  # Yield as list, not individual items
                batch_count += len(transformed_trades)
                print(f"  Fetched {batch_count} aggregated trades for {symbol}...")

                # Check if we've hit the max records limit
                if config.historical_max_records and batch_count >= config.historical_max_records:
                    print(f"  Reached max records limit ({config.historical_max_records})")
                    break

                # Get next batch
                from_id = trades[-1]["a"] + 1

                # Rate limiting
                time.sleep(0.1)

                # Stop if we've reached current time
                if trades[-1]["T"] >= int(time.time() * 1000):
                    break

        except BinanceAPIException as e:
            print(f"Error fetching aggregated trades for {symbol}: {e}")
            continue


@dlt.resource(
    name="order_book_snapshots",
    write_disposition="append",
)
def order_book_snapshots(
    config: BinanceConfig,
    symbols: List[str],
    depth: int = 20,
) -> Iterator[dict]:
    """
    Fetch current order book snapshots for specified symbols.

    Args:
        config: BinanceConfig instance
        symbols: List of trading symbols
        depth: Order book depth (5, 10, 20, 50, 100, 500, 1000, 5000)

    Yields:
        Order book snapshot records
    """
    client = Client(config.api_key, config.api_secret)

    for symbol in symbols:
        print(f"Fetching order book snapshot for {symbol}...")

        try:
            depth_data = client.get_order_book(symbol=symbol, limit=depth)

            yield {
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
                "last_update_id": depth_data["lastUpdateId"],
                "bids": depth_data["bids"],
                "asks": depth_data["asks"],
            }

        except BinanceAPIException as e:
            print(f"Error fetching order book for {symbol}: {e}")
            continue

        # Rate limiting
        time.sleep(0.1)
