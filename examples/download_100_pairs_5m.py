"""
Download 5-minute candlestick data for 100 liquid crypto pairs.

This script fetches 5-minute OHLCV data for all 100 liquid pairs
starting from 2025-01-01.

Usage:
    uv run python examples/download_100_pairs_5m.py

    # With custom date
    uv run python examples/download_100_pairs_5m.py --start-date 2024-01-01

    # Test with first 5 pairs only
    uv run python examples/download_100_pairs_5m.py --test
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import typer
from typing_extensions import Annotated

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import dlt
from dlt.destinations import filesystem

from binance_tick_data.config import BinanceConfig
from binance_tick_data.sources.rest_api import binance_intraday_candles
from config.liquid_100_pairs import LIQUID_100_PAIRS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    help="Download 5-minute bars for 100 liquid crypto pairs",
    no_args_is_help=False,
)


@app.command()
def main(
    start_date: Annotated[
        str,
        typer.Option(help="Start date in YYYY-MM-DD format")
    ] = "2025-01-01",
    test: Annotated[
        bool,
        typer.Option(help="Test mode: download only first 5 pairs")
    ] = False,
    delta: Annotated[
        bool,
        typer.Option(help="Use Delta Lake format (requires MinIO)")
    ] = False,
    dataset: Annotated[
        str,
        typer.Option(help="Dataset name")
    ] = "liquid_100_5m",
):
    """
    Download 5-minute candlestick data for 100 liquid crypto pairs.

    This will fetch historical 5-minute OHLCV data for all pairs
    and store them in separate tables.
    """
    config = BinanceConfig()

    # Select pairs (test mode or all)
    if test:
        symbols = LIQUID_100_PAIRS[:5]
        logger.info(f"🧪 TEST MODE: Downloading first 5 pairs only")
    else:
        symbols = LIQUID_100_PAIRS
        logger.info(f"📊 PRODUCTION MODE: Downloading all 100 pairs")

    logger.info(f"Start date: {start_date}")
    logger.info(f"Interval: 5m (5-minute candles)")
    logger.info(f"Dataset: {dataset}")
    logger.info(f"Table format: {'Delta Lake' if delta else 'Parquet'}")
    logger.info(f"Number of symbols: {len(symbols)}")
    logger.info("=" * 80)

    # Configure destination
    if delta:
        dest = filesystem(bucket_url="s3://binance-data/warehouse")
    else:
        dest = filesystem(
            layout="{table_name}/{YYYY}-{MM}-{DD}/{load_id}.{file_id}.{ext}"
        )

    # Create pipeline
    pipeline = dlt.pipeline(
        pipeline_name="liquid_100_intraday_5m_pipeline",
        destination=dest,
        dataset_name=dataset,
        progress="log",
    )

    # Process in batches of 10 to avoid overwhelming the system
    batch_size = 10
    total_batches = (len(symbols) + batch_size - 1) // batch_size

    logger.info(f"Processing in {total_batches} batches of {batch_size} symbols each")
    logger.info("=" * 80)

    overall_start = datetime.now()
    successful = 0
    failed = 0

    for batch_num in range(total_batches):
        batch_start_idx = batch_num * batch_size
        batch_end_idx = min(batch_start_idx + batch_size, len(symbols))
        batch_symbols = symbols[batch_start_idx:batch_end_idx]

        logger.info(f"\n{'=' * 80}")
        logger.info(f"BATCH {batch_num + 1}/{total_batches}")
        logger.info(f"Symbols: {', '.join(batch_symbols)}")
        logger.info(f"{'=' * 80}")

        try:
            # Create source for this batch
            source = binance_intraday_candles(
                config=config,
                interval="5m",
                symbols=batch_symbols,
                start_date=start_date,
            )

            # Run pipeline
            batch_start_time = datetime.now()

            if delta:
                load_info = pipeline.run(
                    source,
                    table_format="delta",
                )
            else:
                load_info = pipeline.run(
                    source,
                    loader_file_format="parquet",
                )

            batch_elapsed = datetime.now() - batch_start_time

            logger.info(f"\n✅ Batch {batch_num + 1} completed successfully")
            logger.info(f"   Elapsed time: {batch_elapsed}")
            logger.info(f"   Symbols processed: {len(batch_symbols)}")

            successful += len(batch_symbols)

        except Exception as e:
            batch_elapsed = datetime.now() - batch_start_time
            logger.error(f"\n❌ Batch {batch_num + 1} failed after {batch_elapsed}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Symbols in batch: {', '.join(batch_symbols)}")
            failed += len(batch_symbols)

    # Final summary
    overall_elapsed = datetime.now() - overall_start

    logger.info("\n" + "=" * 80)
    logger.info("📊 FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total symbols attempted: {len(symbols)}")
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Success rate: {(successful/len(symbols)*100):.1f}%")
    logger.info(f"Total elapsed time: {overall_elapsed}")
    logger.info(f"Average time per symbol: {overall_elapsed.total_seconds() / len(symbols):.2f}s")
    logger.info("=" * 80)

    # Print data location
    if not delta:
        data_location = Path("dev/data") / dataset
        logger.info(f"\n📁 Data saved to: {data_location}")
        logger.info(f"\nTo query your data:")
        logger.info(f"  import duckdb")
        logger.info(f"  con = duckdb.connect()")
        logger.info(f"  df = con.execute('''")
        logger.info(f"      SELECT * FROM read_parquet('{data_location}/btcusdt_5m/**/*.parquet')")
        logger.info(f"      LIMIT 10")
        logger.info(f"  ''').df()")
        logger.info(f"  print(df)")
    else:
        logger.info(f"\n📁 Data saved to MinIO: s3://binance-data/warehouse/{dataset}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    app()
