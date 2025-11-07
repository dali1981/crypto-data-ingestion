#!/usr/bin/env python3
"""
Download aggregate trades data for 100 liquid crypto pairs.

This script downloads individual trade executions (aggregate trades) from Binance
for 100 liquid cryptocurrency pairs starting from October 1, 2025.

Output: Delta Lake format in MinIO S3
"""

import logging
from datetime import datetime
from typing import Annotated

import dlt
import typer
from dlt.destinations import filesystem

from binance_tick_data.sources.rest_api import binance_historical_data, BinanceConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 100 liquid cryptocurrency pairs
AVAILABLE_SYMBOLS = [
    'AAVEUSDT', 'ADAUSDT', 'ALGOUSDT', 'ANKRUSDT', 'APEUSDT',
    'APTUSDT', 'ARBUSDT', 'ARUSDT', 'ATOMUSDT', 'AVAXUSDT',
    'AXSUSDT', 'BALUSDT', 'BANDUSDT', 'BATUSDT', 'BCHUSDT',
    'BEAMXUSDT', 'BNBUSDT', 'BONKUSDT', 'BTCUSDT', 'CAKEUSDT',
    'CELOUSDT', 'CHZUSDT', 'COMPUSDT', 'CRVUSDT', 'DASHUSDT',
    'DGBUSDT', 'DOGEUSDT', 'DOTUSDT', 'DYDXUSDT', 'EGLDUSDT',
    'ENJUSDT', 'EOSUSDT', 'ETCUSDT', 'ETHUSDT', 'FILUSDT',
    'FLOKIUSDT', 'FLOWUSDT', 'FLUXUSDT', 'FTMUSDT', 'GALAUSDT',
    'GMXUSDT', 'GRTUSDT', 'HBARUSDT', 'ICPUSDT', 'ICXUSDT',
    'IMXUSDT', 'INJUSDT', 'IOTAUSDT', 'KNCUSDT', 'KSMUSDT',
    'LDOUSDT', 'LINKUSDT', 'LSKUSDT', 'LTCUSDT', 'MANAUSDT',
    'MANTAUSDT', 'METISUSDT', 'MKRUSDT', 'NEARUSDT', 'NEOUSDT',
    'ONEUSDT', 'ONTUSDT', 'OPUSDT', 'ORDIUSDT', 'PENDLEUSDT',
    'PEPEUSDT', 'POLYXUSDT', 'QNTUSDT', 'QTUMUSDT', 'RDNTUSDT',
    'RENDERUSDT', 'RLCUSDT', 'ROSEUSDT', 'RUNEUSDT', 'RVNUSDT',
    'SANDUSDT', 'SCRTUSDT', 'SCUSDT', 'SHIBUSDT', 'SKLUSDT',
    'SNXUSDT', 'SOLUSDT', 'STRKUSDT', 'STXUSDT', 'SUIUSDT',
    'SUSHIUSDT', 'THETAUSDT', 'TONUSDT', 'TRXUSDT', 'UNIUSDT',
    'VETUSDT', 'WANUSDT', 'WAXPUSDT', 'WIFUSDT', 'XLMUSDT',
    'XRPUSDT', 'YFIUSDT', 'ZECUSDT', 'ZILUSDT', 'ZRXUSDT',
]

# Create Typer app
app = typer.Typer(
    help="Download aggregate trades for 100 liquid crypto pairs",
    no_args_is_help=False,
)


@app.command()
def main(
    start_date: Annotated[
        str,
        typer.Option(help="Start date in YYYY-MM-DD format")
    ] = "2025-10-01",
    test: Annotated[
        bool,
        typer.Option(help="Test mode: download only first 5 pairs")
    ] = False,
    dataset: Annotated[
        str,
        typer.Option(help="Dataset name")
    ] = "liquid_100_trades",
    batch_size: Annotated[
        int,
        typer.Option(help="Number of symbols to process per batch")
    ] = 10,
):
    """
    Download aggregate trades data for 100 liquid cryptocurrency pairs.

    This will fetch individual trade executions from Binance starting from
    the specified start date until ~1 hour before current time.

    Data is stored in Delta Lake format in MinIO S3.
    """
    config = BinanceConfig()

    # Select pairs (test mode or all)
    if test:
        symbols = AVAILABLE_SYMBOLS[:5]
        logger.info(f"🧪 TEST MODE: Downloading first 5 pairs only")
    else:
        symbols = AVAILABLE_SYMBOLS
        logger.info(f"📊 PRODUCTION MODE: Downloading all 100 pairs")

    logger.info(f"Start date: {start_date}")
    logger.info(f"Dataset: {dataset}")
    logger.info(f"Output format: Delta Lake")
    logger.info(f"Number of symbols: {len(symbols)}")
    logger.info(f"Batch size: {batch_size}")
    logger.info("=" * 80)

    # Configure Delta Lake destination
    dest = filesystem(bucket_url="s3://binance-data/warehouse")

    # Create pipeline
    pipeline = dlt.pipeline(
        pipeline_name="liquid_100_trades_pipeline",
        destination=dest,
        dataset_name=dataset,
        progress="log",
    )

    # Process in batches to avoid overwhelming the system
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
            source = binance_historical_data(
                config=config,
                symbols=batch_symbols,
                start_date=start_date,
            )

            # Run pipeline
            batch_start_time = datetime.now()

            # Run pipeline with Delta Lake table format
            info = pipeline.run(
                source,
                table_format="delta",
            )

            batch_duration = datetime.now() - batch_start_time

            # Log results
            logger.info(f"\n{'=' * 80}")
            logger.info(f"BATCH {batch_num + 1} COMPLETED")
            logger.info(f"Duration: {batch_duration}")
            logger.info(f"{'=' * 80}")

            if info.has_failed_jobs:
                logger.error(f"⚠️  Some jobs failed in batch {batch_num + 1}:")
                for job in info.failed_jobs:
                    logger.error(f"  - {job}")
                    failed += 1
            else:
                logger.info(f"✓ Batch {batch_num + 1} completed successfully")
                successful += len(batch_symbols)

            # Log load info
            logger.info(f"\nLoad packages: {len(info.load_packages)}")
            for pkg in info.load_packages:
                logger.info(f"  - {pkg.dataset_name}")

        except Exception as e:
            logger.error(f"✗ Error processing batch {batch_num + 1}: {e}")
            logger.exception(e)
            failed += len(batch_symbols)
            continue

    # Final summary
    overall_duration = datetime.now() - overall_start

    logger.info(f"\n{'=' * 80}")
    logger.info("DOWNLOAD COMPLETE")
    logger.info(f"{'=' * 80}")
    logger.info(f"\nTotal duration: {overall_duration}")
    logger.info(f"Successful symbols: {successful}/{len(symbols)}")
    logger.info(f"Failed symbols: {failed}/{len(symbols)}")

    if failed > 0:
        logger.warning(f"\n⚠️  {failed} symbols failed. Check logs for details.")
    else:
        logger.info(f"\n✓ All {len(symbols)} symbols downloaded successfully!")

    logger.info(f"\nData location: s3://binance-data/warehouse/{dataset}")
    logger.info(f"Format: Delta Lake")
    logger.info(f"Start date: {start_date}")
    logger.info(f"Symbols: {len(symbols)}")


if __name__ == "__main__":
    app()
