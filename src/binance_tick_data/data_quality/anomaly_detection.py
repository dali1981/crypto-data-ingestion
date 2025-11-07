"""
Price anomaly detection for cryptocurrency data.

Detects:
- Price spikes (>X% change in single candle)
- Statistical outliers (beyond N standard deviations)
- Isolated anomalies (symbol-specific vs market-wide)
- Volume anomalies
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceAnomaly:
    """Represents a detected price anomaly."""
    symbol: str
    timestamp: datetime
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    change_pct: float
    volume: float
    anomaly_type: str  # 'spike', 'outlier', 'isolated'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str


def detect_price_spikes(
    df: pd.DataFrame,
    threshold_pct: float = 10.0,
    price_col: str = 'close',
    open_col: str = 'open',
) -> pd.DataFrame:
    """
    Detect price spikes where price changes more than threshold% in a single candle.

    Args:
        df: DataFrame with OHLCV data
        threshold_pct: Percentage change threshold (default: 10%)
        price_col: Column name for closing price
        open_col: Column name for opening price

    Returns:
        DataFrame containing rows with price spikes
    """
    df = df.copy()

    # Calculate price change percentage
    df['price_change_pct'] = ((df[price_col] - df[open_col]) / df[open_col] * 100).abs()

    # Detect spikes
    spikes = df[df['price_change_pct'] > threshold_pct].copy()

    # Add severity classification
    spikes['severity'] = spikes['price_change_pct'].apply(_classify_severity)

    return spikes


def detect_statistical_outliers(
    df: pd.DataFrame,
    column: str = 'close',
    window: int = 20,
    std_devs: float = 3.0,
) -> pd.DataFrame:
    """
    Detect statistical outliers using rolling z-score analysis.

    Args:
        df: DataFrame with price data
        column: Column to analyze
        window: Rolling window size for mean/std calculation
        std_devs: Number of standard deviations for outlier threshold

    Returns:
        DataFrame containing outlier rows
    """
    df = df.copy()

    # Convert to float if needed
    df[column] = df[column].astype(float)

    # Calculate rolling statistics
    df['rolling_mean'] = df[column].rolling(window=window, min_periods=1).mean()
    df['rolling_std'] = df[column].rolling(window=window, min_periods=1).std()

    # Calculate z-score
    df['z_score'] = ((df[column] - df['rolling_mean']) / df['rolling_std']).abs()

    # Detect outliers
    outliers = df[df['z_score'] > std_devs].copy()

    # Add severity based on z-score
    outliers['severity'] = outliers['z_score'].apply(_classify_z_score_severity)

    return outliers


def detect_isolated_anomalies(
    data_dict: Dict[str, pd.DataFrame],
    timestamp: datetime,
    threshold_pct: float = 5.0,
) -> Tuple[List[str], bool]:
    """
    Check if an anomaly at a specific timestamp is isolated to few symbols or market-wide.

    Args:
        data_dict: Dictionary mapping symbol -> DataFrame with OHLCV data
        timestamp: Timestamp to check
        threshold_pct: Price change threshold to consider as affected

    Returns:
        Tuple of (affected_symbols, is_market_wide)
        is_market_wide is True if >50% of symbols are affected
    """
    affected_symbols = []
    total_symbols = len(data_dict)

    for symbol, df in data_dict.items():
        # Filter for timestamp (allow ±5 minute window)
        time_window = df[
            (df['open_time_dt'] >= timestamp - pd.Timedelta(minutes=5)) &
            (df['open_time_dt'] <= timestamp + pd.Timedelta(minutes=5))
        ]

        if time_window.empty:
            continue

        # Check for large price changes
        time_window = time_window.copy()
        time_window['price_change_pct'] = (
            (time_window['close'].astype(float) - time_window['open'].astype(float)) /
            time_window['open'].astype(float) * 100
        ).abs()

        if time_window['price_change_pct'].max() > threshold_pct:
            affected_symbols.append(symbol)

    # Consider market-wide if >50% of symbols affected
    is_market_wide = len(affected_symbols) > (total_symbols * 0.5)

    return affected_symbols, is_market_wide


def _classify_severity(change_pct: float) -> str:
    """Classify anomaly severity based on price change percentage."""
    abs_change = abs(change_pct)
    if abs_change > 20:
        return 'critical'
    elif abs_change > 15:
        return 'high'
    elif abs_change > 10:
        return 'medium'
    else:
        return 'low'


def _classify_z_score_severity(z_score: float) -> str:
    """Classify anomaly severity based on z-score."""
    if z_score > 5:
        return 'critical'
    elif z_score > 4:
        return 'high'
    elif z_score > 3:
        return 'medium'
    else:
        return 'low'


class PriceAnomalyDetector:
    """
    Comprehensive price anomaly detector for cryptocurrency data.

    Usage:
        detector = PriceAnomalyDetector()
        anomalies = detector.detect_all(df, symbol='BTCUSDT')
    """

    def __init__(
        self,
        spike_threshold_pct: float = 10.0,
        outlier_std_devs: float = 3.0,
        outlier_window: int = 20,
    ):
        """
        Initialize anomaly detector.

        Args:
            spike_threshold_pct: Threshold for price spike detection (%)
            outlier_std_devs: Standard deviations for outlier detection
            outlier_window: Rolling window for outlier calculation
        """
        self.spike_threshold_pct = spike_threshold_pct
        self.outlier_std_devs = outlier_std_devs
        self.outlier_window = outlier_window

    def detect_all(
        self,
        df: pd.DataFrame,
        symbol: str,
        include_low_severity: bool = False,
    ) -> List[PriceAnomaly]:
        """
        Run all anomaly detection methods and return results.

        Args:
            df: DataFrame with OHLCV data (must have columns: open, high, low, close, volume)
            symbol: Symbol name
            include_low_severity: Whether to include low-severity anomalies

        Returns:
            List of detected PriceAnomaly objects
        """
        anomalies = []

        # Ensure timestamp column
        if 'open_time_dt' not in df.columns and 'open_time' in df.columns:
            df['open_time_dt'] = pd.to_datetime(df['open_time'], unit='ms')

        # Detect price spikes
        spikes = detect_price_spikes(
            df,
            threshold_pct=self.spike_threshold_pct,
        )

        for _, row in spikes.iterrows():
            if not include_low_severity and row['severity'] == 'low':
                continue

            anomalies.append(PriceAnomaly(
                symbol=symbol,
                timestamp=row.get('open_time_dt', row.name),
                open_price=float(row['open']),
                close_price=float(row['close']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                change_pct=float(row['price_change_pct']),
                volume=float(row.get('volume', 0)),
                anomaly_type='spike',
                severity=row['severity'],
                message=f"Price spike: {row['price_change_pct']:.2f}% change in single candle",
            ))

        # Detect statistical outliers
        outliers = detect_statistical_outliers(
            df,
            column='close',
            window=self.outlier_window,
            std_devs=self.outlier_std_devs,
        )

        for _, row in outliers.iterrows():
            if not include_low_severity and row['severity'] == 'low':
                continue

            # Avoid duplicates (spike + outlier)
            timestamp = row.get('open_time_dt', row.name)
            if any(a.timestamp == timestamp and a.anomaly_type == 'spike' for a in anomalies):
                continue

            anomalies.append(PriceAnomaly(
                symbol=symbol,
                timestamp=timestamp,
                open_price=float(row['open']),
                close_price=float(row['close']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                change_pct=float(row.get('price_change_pct', 0)),
                volume=float(row.get('volume', 0)),
                anomaly_type='outlier',
                severity=row['severity'],
                message=f"Statistical outlier: z-score={row['z_score']:.2f}",
            ))

        return anomalies

    def generate_report(self, anomalies: List[PriceAnomaly]) -> str:
        """Generate a human-readable report of detected anomalies."""
        if not anomalies:
            return "No anomalies detected."

        report = []
        report.append("=" * 70)
        report.append("PRICE ANOMALY DETECTION REPORT")
        report.append("=" * 70)
        report.append(f"\nTotal anomalies detected: {len(anomalies)}")

        # Group by severity
        by_severity = {}
        for anomaly in anomalies:
            by_severity.setdefault(anomaly.severity, []).append(anomaly)

        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                report.append(f"\n{severity.upper()}: {len(by_severity[severity])} anomalies")

        # Detailed anomalies
        report.append("\n" + "=" * 70)
        report.append("DETAILED ANOMALIES")
        report.append("=" * 70)

        for anomaly in sorted(anomalies, key=lambda x: x.timestamp):
            report.append(f"\n[{anomaly.severity.upper()}] {anomaly.symbol} - {anomaly.timestamp}")
            report.append(f"  Type: {anomaly.anomaly_type}")
            report.append(f"  Open: ${anomaly.open_price:.2f} | Close: ${anomaly.close_price:.2f}")
            report.append(f"  High: ${anomaly.high_price:.2f} | Low: ${anomaly.low_price:.2f}")
            report.append(f"  Change: {anomaly.change_pct:.2f}%")
            report.append(f"  Volume: {anomaly.volume:.2f}")
            report.append(f"  Message: {anomaly.message}")

        return "\n".join(report)
