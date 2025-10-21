"""Configuration for Dagster pipeline."""

from typing import List, Dict

# Trading pairs configuration
SYMBOLS: List[str] = [
    "ETHUSDT",
    "BTCUSDT",
    "FLOKIUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "FFUSDT",
    "SUIUSDT",
    "ZECUSDT",
    "2ZUSDT",
    "AVNTUSDT",
    "PAXGUSDT",
    "AAVEUSDT",
    "HBARUSDT",
    "ADAUSDT",
    "FORMUSDT",
    "LTCUSDT",
    "WALUSDT",
    "TAOUSDT",
]

# Dollar bars thresholds per symbol
DOLLAR_BARS_THRESHOLDS: Dict[str, float] = {
    "ETHUSDT": 14684000.0,
    "BTCUSDT": 24908000.0,
    "FLOKIUSDT": 319000.0,
    "SOLUSDT": 5594000.0,
    "BNBUSDT": 3709000.0,
    "XRPUSDT": 2242000.0,
    "DOGEUSDT": 1805000.0,
    "FFUSDT": 300000.0,
    "SUIUSDT": 915000.0,
    "ZECUSDT": 1538000.0,
    "2ZUSDT": 159000.0,
    "AVNTUSDT": 733000.0,
    "PAXGUSDT": 650000.0,
    "AAVEUSDT": 205000.0,
    "HBARUSDT": 173000.0,
    "ADAUSDT": 627000.0,
    "FORMUSDT": 139000.0,
    "LTCUSDT": 346000.0,
    "WALUSDT": 1737000.0,
    "TAOUSDT": 668000.0,
}

# Volume bars thresholds per symbol
VOLUME_BARS_THRESHOLDS: Dict[str, float] = {
    "ETHUSDT": 3708.2,
    "BTCUSDT": 225.03,
    "FLOKIUSDT": 4150347726.5,
    "SOLUSDT": 29447.42,
    "BNBUSDT": 3415.94,
    "XRPUSDT": 911078.89,
    "DOGEUSDT": 9086277.96,
    "FFUSDT": 2015487.61,
    "SUIUSDT": 355934.34,
    "ZECUSDT": 5568.68,
    "2ZUSDT": 617913.11,
    "AVNTUSDT": 1118859.13,
    "PAXGUSDT": 154.36,
    "AAVEUSDT": 903.46,
    "HBARUSDT": 985006.89,
    "ADAUSDT": 949578.04,
    "FORMUSDT": 176487.61,
    "LTCUSDT": 3664.53,
    "WALUSDT": 7215133.53,
    "TAOUSDT": 1620.16,
}

# Tick bars thresholds per symbol
TICK_BARS_THRESHOLDS: Dict[str, int] = {
    "ETHUSDT": 43835,
    "BTCUSDT": 36679,
    "FLOKIUSDT": 41562,
    "SOLUSDT": 18756,
    "BNBUSDT": 17637,
    "XRPUSDT": 10509,
    "DOGEUSDT": 10495,
    "FFUSDT": 6162,
    "SUIUSDT": 5012,
    "ZECUSDT": 5467,
    "2ZUSDT": 3391,
    "AVNTUSDT": 4582,
    "PAXGUSDT": 1547,
    "AAVEUSDT": 2067,
    "HBARUSDT": 1915,
    "ADAUSDT": 2816,
    "FORMUSDT": 2645,
    "LTCUSDT": 2191,
    "WALUSDT": 5480,
    "TAOUSDT": 3291,
}

# Data quality thresholds
DUPLICATE_THRESHOLD = 1000  # Trigger cleanup if duplicates > 1000
GAP_THRESHOLD_HOURS = 6.0  # Trigger fill if gap > 6 hours
FRESHNESS_THRESHOLD_HOURS = 2.0  # Trigger fetch if data > 2 hours old

# Historical data settings
HISTORICAL_START_DATE = "2024-10-01"
MAX_RECORDS_PER_CHUNK = 50000

# Database configuration
DB_PATH = "binance_pipeline.duckdb"
DATASET_NAME = "binance_data"

# Order book configuration
ORDER_BOOK_DEPTH = 20  # Number of levels per side
