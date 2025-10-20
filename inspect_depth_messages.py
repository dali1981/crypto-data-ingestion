"""Inspect raw depth messages from Binance."""

import asyncio
import json
from binance import AsyncClient, BinanceSocketManager


async def inspect_depth():
    """Capture and display raw depth messages."""
    print("\n" + "="*80)
    print("Depth Message Inspector")
    print("="*80 + "\n")

    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)

    stream = bm.depth_socket('BTCUSDT', depth='20')

    print("Connecting to BTCUSDT depth stream...")
    print("Will capture 3 messages and display their structure.\n")

    async with stream as ds:
        for i in range(3):
            msg = await ds.recv()

            print(f"\n{'='*80}")
            print(f"Message {i+1}:")
            print(f"{'='*80}")

            # Pretty print the message
            print("\nRaw message structure:")
            print(json.dumps(msg, indent=2))

            # Show keys
            print(f"\nMessage keys: {list(msg.keys())}")

            if "b" in msg:
                print(f"  Bids ('b'): {len(msg['b'])} levels")
                if msg['b']:
                    print(f"    First bid: {msg['b'][0]}")
            if "a" in msg:
                print(f"  Asks ('a'): {len(msg['a'])} levels")
                if msg['a']:
                    print(f"    First ask: {msg['a'][0]}")

            print()

    await client.close_connection()

    print("\n" + "="*80)
    print("✅ Inspection complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(inspect_depth())
