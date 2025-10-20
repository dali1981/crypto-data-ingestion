"""
Inspect raw WebSocket messages from Binance to understand exact format.
Run with: uv run python inspect_websocket_messages.py
"""

import asyncio
import json
from binance import AsyncClient, BinanceSocketManager


async def inspect_messages():
    """Capture and display raw WebSocket messages."""
    print("\n" + "="*80)
    print("WebSocket Message Inspector")
    print("="*80 + "\n")

    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)

    stream = bm.trade_socket('BTCUSDT')

    print("Connecting to BTCUSDT trade stream...")
    print("Will capture 3 messages and display their structure.\n")

    async with stream as ts:
        for i in range(3):
            msg = await ts.recv()

            print(f"\n{'='*80}")
            print(f"Message {i+1}:")
            print(f"{'='*80}")

            # Pretty print the message
            print("\nRaw message structure:")
            print(json.dumps(msg, indent=2))

            # Show field types
            print("\nField types:")
            for key, value in msg.items():
                print(f"  {key:20s} = {str(value):30s} (type: {type(value).__name__})")

            print()

    await client.close_connection()

    print("\n" + "="*80)
    print("✅ Inspection complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(inspect_messages())
