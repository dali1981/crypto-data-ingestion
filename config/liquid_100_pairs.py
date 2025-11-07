"""
100 Well-Established Liquid Cryptocurrency Pairs for Binance

This list represents a comprehensive selection of liquid trading pairs based on:
- Market capitalization
- Trading volume
- Project establishment and longevity
- Order book depth and liquidity
- Ecosystem diversity

Generated: 2025-10-31
For use with: Intraday data pipeline (5m, 1h, 1d candles)
"""

from typing import List

# Complete list of 100 liquid crypto pairs
LIQUID_100_PAIRS: List[str] = [
    # ============================================
    # TIER 1: MAJOR CRYPTOCURRENCIES (Top 10)
    # ============================================
    "BTCUSDT",      # Bitcoin - The original
    "ETHUSDT",      # Ethereum - Smart contracts king
    "BNBUSDT",      # Binance Coin - Exchange token
    "SOLUSDT",      # Solana - Fast L1
    "XRPUSDT",      # Ripple - Payments
    "ADAUSDT",      # Cardano - Academic blockchain
    "DOGEUSDT",     # Dogecoin - OG meme coin
    "TRXUSDT",      # Tron - Justin Sun's chain
    "TONUSDT",      # Toncoin - Telegram blockchain
    "LINKUSDT",     # Chainlink - Oracle network

    # ============================================
    # TIER 2: LARGE CAP LAYER 1 BLOCKCHAINS (20)
    # ============================================
    "AVAXUSDT",     # Avalanche - Fast finality
    "MATICUSDT",    # Polygon - Ethereum scaling
    "DOTUSDT",      # Polkadot - Multi-chain
    "ATOMUSDT",     # Cosmos - Internet of blockchains
    "LTCUSDT",      # Litecoin - Silver to Bitcoin's gold
    "NEARUSDT",     # NEAR Protocol - Sharded L1
    "APTUSDT",      # Aptos - Move language
    "SUIUSDT",      # Sui - Also Move language
    "ALGOUSDT",     # Algorand - Pure PoS
    "HBARUSDT",     # Hedera - Hashgraph
    "ICPUSDT",      # Internet Computer
    "VETUSDT",      # VeChain - Supply chain
    "FTMUSDT",      # Fantom - Opera chain
    "XLMUSDT",      # Stellar - Payments
    "INJUSDT",      # Injective - DeFi L1
    "EOSUSDT",      # EOS - OG smart contracts
    "THETAUSDT",    # Theta - Video streaming
    "QNTUSDT",      # Quant - Interoperability
    "FILUSDT",      # Filecoin - Storage
    "EGLDUSDT",     # MultiversX (Elrond)

    # ============================================
    # TIER 3: ETHEREUM LAYER 2 & SCALING (10)
    # ============================================
    "ARBUSDT",      # Arbitrum - Optimistic rollup
    "OPUSDT",       # Optimism - Optimistic rollup
    "STRKUSDT",     # Starknet - ZK rollup
    "IMXUSDT",      # Immutable X - Gaming L2
    "MANTAUSDT",    # Manta - Privacy L2
    "METISUSDT",    # Metis - Optimistic rollup
    "LDOUSDT",      # Lido DAO - Liquid staking
    "POLYXUSDT",    # Polymesh - Security tokens
    "ROSEUSDT",     # Oasis Network - Privacy
    "SKLUSDT",      # SKALE - Elastic sidechains

    # ============================================
    # TIER 4: DEFI PROTOCOLS (15)
    # ============================================
    "UNIUSDT",      # Uniswap - DEX king
    "AAVEUSDT",     # Aave - Lending
    "MKRUSDT",      # Maker - DAI stablecoin
    "COMPUSDT",     # Compound - Lending
    "CRVUSDT",      # Curve - Stablecoin DEX
    "SNXUSDT",      # Synthetix - Synthetic assets
    "SUSHIUSDT",    # SushiSwap - DEX
    "BALUSDT",      # Balancer - AMM
    "YFIUSDT",      # Yearn Finance - Yield aggregator
    "1INCHUSDT",    # 1inch - DEX aggregator
    "DYDXUSDT",     # dYdX - Derivatives DEX
    "GMXUSDT",      # GMX - Perpetuals DEX
    "PENDLEUSDT",   # Pendle - Yield trading
    "CAKEUSDT",     # PancakeSwap - BSC DEX
    "RDNTUSDT",     # Radiant Capital - Omnichain lending

    # ============================================
    # TIER 5: INFRASTRUCTURE & ORACLES (10)
    # ============================================
    "GRTUSDT",      # The Graph - Indexing
    "RENDERUSDT",   # Render - GPU rendering
    "ARUSDT",       # Arweave - Permanent storage
    "FLUXUSDT",     # Flux - Decentralized cloud
    "BANDUSDT",     # Band Protocol - Oracle
    "IOTAUSDT",     # IOTA - IoT
    "KNCUSDT",      # Kyber Network - Liquidity
    "ZILUSDT",      # Zilliqa - Sharding
    "RLCUSDT",      # iExec - Cloud computing
    "OCEANUSDT",    # Ocean Protocol - Data marketplace

    # ============================================
    # TIER 6: GAMING & METAVERSE (10)
    # ============================================
    "AXSUSDT",      # Axie Infinity
    "SANDUSDT",     # The Sandbox
    "MANAUSDT",     # Decentraland
    "ENJUSDT",      # Enjin Coin
    "GALAUSDT",     # Gala Games
    "FLOWUSDT",     # Flow - NBA Top Shot
    "APEUSDT",      # ApeCoin - BAYC
    "CHZUSDT",      # Chiliz - Sports fan tokens
    "WAXPUSDT",     # WAX - NFT blockchain
    "BEAMXUSDT",    # Beam - Gaming

    # ============================================
    # TIER 7: PRIVACY & SECURITY (5)
    # ============================================
    "XMRUSDT",      # Monero - Privacy
    "ZECUSDT",      # Zcash - Zero knowledge
    "DASHUSDT",     # Dash - Private transactions
    "SCRTUSDT",     # Secret Network - Privacy smart contracts
    "HORNETUSDT",   # Hornet - Privacy (if available)

    # ============================================
    # TIER 8: MEME & COMMUNITY COINS (8)
    # ============================================
    "SHIBUSDT",     # Shiba Inu - Doge killer
    "PEPEUSDT",     # Pepe - Meme coin 2023
    "FLOKIUSDT",    # Floki - Elon's dog
    "BONKUSDT",     # Bonk - Solana meme
    "WIFUSDT",      # Dogwifhat - Solana meme
    "SATSUSDT",     # SATS - Bitcoin ordinals
    "RATSUSDT",     # RATS - Bitcoin ordinals
    "ORDIUSDT",     # Ordinals - BTC ordinals

    # ============================================
    # TIER 9: CROSS-CHAIN & BRIDGES (5)
    # ============================================
    "RUNEUSDT",     # THORChain - Cross-chain DEX
    "ANKRUSDT",     # Ankr - Web3 infrastructure
    "CELOUSDT",     # Celo - Mobile payments
    "WANUSDT",      # Wanchain - Cross-chain
    "QTUMUSDT",     # Qtum - Hybrid blockchain

    # ============================================
    # TIER 10: ESTABLISHED ALTCOINS (17)
    # ============================================
    "ETCUSDT",      # Ethereum Classic
    "BCHUSDT",      # Bitcoin Cash
    "BSVUSDT",      # Bitcoin SV
    "NEOUSDT",      # NEO - Chinese Ethereum
    "ONTUSDT",      # Ontology
    "WAVESUSDT",    # Waves
    "LSKUSDT",      # Lisk
    "RVNUSDT",      # Ravencoin
    "ZRXUSDT",      # 0x Protocol
    "BATUSDT",      # Basic Attention Token
    "OMGUSDT",      # OMG Network
    "ICXUSDT",      # ICON
    "SCUSDT",       # Siacoin
    "DGBUSDT",      # DigiByte
    "STXUSDT",      # Stacks - Bitcoin L2
    "KSMUSDT",      # Kusama - Polkadot canary
    "ONEUSDT",      # Harmony
]

# Tier breakdown for reference
TIER_BREAKDOWN = {
    "Tier 1: Major Cryptocurrencies": 10,
    "Tier 2: Large Cap L1s": 20,
    "Tier 3: L2 & Scaling": 10,
    "Tier 4: DeFi Protocols": 15,
    "Tier 5: Infrastructure": 10,
    "Tier 6: Gaming & Metaverse": 10,
    "Tier 7: Privacy & Security": 5,
    "Tier 8: Meme & Community": 8,
    "Tier 9: Cross-Chain": 5,
    "Tier 10: Established Alts": 17,
}

def get_liquid_pairs() -> List[str]:
    """Return the list of 100 liquid crypto pairs."""
    return LIQUID_100_PAIRS.copy()

def get_tier_count() -> int:
    """Return total number of pairs."""
    return len(LIQUID_100_PAIRS)

if __name__ == "__main__":
    print(f"Total liquid pairs: {len(LIQUID_100_PAIRS)}")
    print(f"\nTier Breakdown:")
    for tier, count in TIER_BREAKDOWN.items():
        print(f"  {tier}: {count}")
    print(f"\nFirst 10 pairs:")
    for pair in LIQUID_100_PAIRS[:10]:
        print(f"  - {pair}")
