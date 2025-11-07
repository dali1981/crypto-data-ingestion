"""
Investigation script for BNB/XRP data quality issue on October 10, 2025 at 21:15 UTC
Reported crashes:
- BNB: -20.95% ($1,114 → $881)
- XRP: -21.34% ($2.28 → $1.80)
"""

import duckdb
from datetime import datetime, timezone
import pandas as pd

# Convert the timestamp to milliseconds
# October 10, 2025 21:15 UTC
crash_time = datetime(2025, 10, 10, 21, 15, tzinfo=timezone.utc)
crash_timestamp_ms = int(crash_time.timestamp() * 1000)

print(f"Investigating crash at: {crash_time} (UTC)")
print(f"Timestamp in ms: {crash_timestamp_ms}")
print("=" * 80)

def investigate_database(db_path, db_name):
    """Investigate a single database for the crash data"""
    print(f"\n{'='*80}")
    print(f"INVESTIGATING: {db_name}")
    print(f"Database: {db_path}")
    print(f"{'='*80}\n")
    
    try:
        conn = duckdb.connect(db_path, read_only=True)
        
        # List all tables
        print("📋 TABLES IN DATABASE:")
        tables = conn.execute("SHOW TABLES").fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        print()
        
        # For each table, check schema and look for data
        for table_tuple in tables:
            table_name = table_tuple[0]
            print(f"\n🔍 Analyzing table: {table_name}")
            print("-" * 80)
            
            # Get schema
            schema = conn.execute(f"DESCRIBE {table_name}").fetchdf()
            print(f"Schema:\n{schema.to_string()}\n")
            
            # Get row count
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"Total rows: {row_count:,}")
            
            if row_count == 0:
                print("⚠️  Table is empty, skipping...")
                continue
            
            # Check if table has symbol and timestamp columns
            columns = [col.lower() for col in schema['column_name'].tolist()]
            
            # Try to identify timestamp column
            timestamp_col = None
            for col in ['open_time', 'timestamp', 'time', 'open_time_ms', 'close_time']:
                if col in columns:
                    timestamp_col = col
                    break
            
            # Try to identify symbol column
            symbol_col = None
            for col in ['symbol', 'pair', 'trading_pair']:
                if col in columns:
                    symbol_col = col
                    break
            
            if not timestamp_col or not symbol_col:
                print(f"⚠️  Cannot find timestamp or symbol column, skipping detailed analysis")
                # Show sample data anyway
                sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchdf()
                print(f"\nSample data:\n{sample.to_string()}\n")
                continue
            
            print(f"Using timestamp column: '{timestamp_col}', symbol column: '{symbol_col}'")
            
            # Check if BNB or XRP data exists
            symbols_in_table = conn.execute(f"""
                SELECT DISTINCT {symbol_col} 
                FROM {table_name} 
                WHERE {symbol_col} IN ('BNBUSDT', 'XRPUSDT')
            """).fetchall()
            
            if not symbols_in_table:
                print("⚠️  No BNB or XRP data in this table")
                continue
            
            print(f"Found symbols: {[s[0] for s in symbols_in_table]}")
            
            # Search for data around the crash time
            # Look for data within ±1 hour of the crash
            time_window_start = crash_timestamp_ms - (3600 * 1000)  # 1 hour before
            time_window_end = crash_timestamp_ms + (3600 * 1000)    # 1 hour after
            
            for symbol in ['BNBUSDT', 'XRPUSDT']:
                print(f"\n{'─'*80}")
                print(f"🔎 Searching for {symbol} around crash time...")
                print(f"{'─'*80}")
                
                # Get data around the crash time
                query = f"""
                    SELECT * 
                    FROM {table_name}
                    WHERE {symbol_col} = '{symbol}'
                    AND {timestamp_col} BETWEEN {time_window_start} AND {time_window_end}
                    ORDER BY {timestamp_col}
                """
                
                try:
                    crash_window_data = conn.execute(query).fetchdf()
                    
                    if len(crash_window_data) == 0:
                        print(f"⚠️  No data found for {symbol} in the time window")
                        continue
                    
                    print(f"\n✅ Found {len(crash_window_data)} rows for {symbol} in time window")
                    print(f"\nData around crash time:")
                    print(crash_window_data.to_string())
                    
                    # Check for specific price values mentioned
                    if symbol == 'BNBUSDT':
                        # Look for prices around 1114, 881
                        price_cols = [col for col in crash_window_data.columns if 'price' in col.lower() or col.lower() in ['open', 'high', 'low', 'close']]
                        if price_cols:
                            for col in price_cols:
                                mask = ((crash_window_data[col] > 850) & (crash_window_data[col] < 1150))
                                if mask.any():
                                    print(f"\n🎯 Found BNB prices in crash range (850-1150) in column '{col}':")
                                    print(crash_window_data[mask][[symbol_col, timestamp_col, col] + [c for c in crash_window_data.columns if c not in [symbol_col, timestamp_col, col]]].to_string())
                    
                    elif symbol == 'XRPUSDT':
                        # Look for prices around 2.28, 1.80
                        price_cols = [col for col in crash_window_data.columns if 'price' in col.lower() or col.lower() in ['open', 'high', 'low', 'close']]
                        if price_cols:
                            for col in price_cols:
                                mask = ((crash_window_data[col] > 1.7) & (crash_window_data[col] < 2.4))
                                if mask.any():
                                    print(f"\n🎯 Found XRP prices in crash range (1.7-2.4) in column '{col}':")
                                    print(crash_window_data[mask][[symbol_col, timestamp_col, col] + [c for c in crash_window_data.columns if c not in [symbol_col, timestamp_col, col]]].to_string())
                    
                    # Calculate price changes
                    if 'close' in [c.lower() for c in crash_window_data.columns]:
                        close_col = [c for c in crash_window_data.columns if c.lower() == 'close'][0]
                        crash_window_data['pct_change'] = crash_window_data[close_col].pct_change() * 100
                        
                        # Look for large price drops (> 15%)
                        large_drops = crash_window_data[crash_window_data['pct_change'] < -15]
                        if len(large_drops) > 0:
                            print(f"\n⚠️  FOUND LARGE PRICE DROPS (>15%) for {symbol}:")
                            print(large_drops.to_string())
                    
                except Exception as e:
                    print(f"Error querying {symbol}: {e}")
            
            # Check for market-wide issues at the crash timestamp
            print(f"\n{'─'*80}")
            print(f"🌐 Checking for market-wide issues at crash time...")
            print(f"{'─'*80}")
            
            try:
                # Get data for all symbols at the crash time (within ±5 minutes)
                crash_window_narrow = 5 * 60 * 1000  # 5 minutes
                market_query = f"""
                    SELECT {symbol_col}, {timestamp_col}, *
                    FROM {table_name}
                    WHERE {timestamp_col} BETWEEN {crash_timestamp_ms - crash_window_narrow} 
                        AND {crash_timestamp_ms + crash_window_narrow}
                    ORDER BY {timestamp_col}, {symbol_col}
                """
                
                market_data = conn.execute(market_query).fetchdf()
                
                if len(market_data) > 0:
                    print(f"\n✅ Found {len(market_data)} rows for all symbols near crash time")
                    print(f"Symbols affected: {market_data[symbol_col].unique().tolist()}")
                    print(f"\nMarket data sample:")
                    print(market_data.head(20).to_string())
                else:
                    print("⚠️  No data found for any symbol at crash time")
                    
            except Exception as e:
                print(f"Error checking market-wide data: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error investigating {db_name}: {e}")
        import traceback
        traceback.print_exc()

# Investigate both databases
investigate_database('/Users/mohamedali/trading_project/dlt-starter/binance_pipeline.duckdb', 'binance_pipeline.duckdb')
investigate_database('/Users/mohamedali/trading_project/dlt-starter/binance_gap_filler.duckdb', 'binance_gap_filler.duckdb')

print(f"\n{'='*80}")
print("INVESTIGATION COMPLETE")
print(f"{'='*80}")
