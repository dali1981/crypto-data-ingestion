"""Simple WebSocket test - exits after 5 messages."""
import asyncio
from binance import AsyncClient, BinanceSocketManager

async def test():
    print("Connecting to Binance WebSocket...")
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)

    ts = bm.trade_socket('BTCUSDT')

    print("Receiving trades...")
    async with ts as tscm:
        for i in range(5):
            msg = await tscm.recv()
            print(f"✅ Trade {i+1}: Price=${msg['p']}, Qty={msg['q']}")

    await client.close_connection()
    print("\n✅ WebSocket test SUCCESS!")

if __name__ == "__main__":
    asyncio.run(test())
