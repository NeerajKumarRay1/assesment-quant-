"""Example demonstrating async market data feed with replay data."""

import asyncio
from pathlib import Path
from src.market_data.replay_market_data import ReplayMarketData
from src.market_data.async_feed import AsyncMarketDataFeed
from src.core.tick import Tick


async def main():
    print("="*70)
    print("ASYNC MARKET DATA FEED DEMONSTRATION")
    print("="*70)
    
    # Load replay data
    csv_path = Path("data/sample_ticks.csv")
    replay_feed = ReplayMarketData(csv_path)
    
    print(f"\nStep 1: Loaded replay data from {csv_path}")
    instruments = replay_feed.get_instruments()
    print(f"  ✓ Instruments: {', '.join(sorted(instruments))}")
    
    # Create tick handler
    tick_count = {}
    total_volume = {}
    
    async def handle_tick(tick: Tick) -> None:
        """Process each tick - this is where strategy logic would go."""
        if tick.instrument not in tick_count:
            tick_count[tick.instrument] = 0
            total_volume[tick.instrument] = 0
        
        tick_count[tick.instrument] += 1
        total_volume[tick.instrument] += tick.volume
        
        # Print first few ticks
        if tick_count[tick.instrument] <= 3:
            print(f"  Received: {tick.instrument} @ ₹{tick.price:.2f}, vol={tick.volume}")
    
    print("\nStep 2: Setting up async feed pipeline...")
    print("  ✓ Bounded queue (maxsize=100) for back-pressure")
    print("  ✓ Producer: reads from replay CSV")
    print("  ✓ Consumer: processes ticks via handler")
    
    # Create async feed for NIFTY
    feed = AsyncMarketDataFeed(
        tick_source=list(replay_feed.stream_ticks("NIFTY")),
        handler=handle_tick,
        max_queue_size=100,
        delay_seconds=0.001  # Small delay to simulate realistic timing
    )
    
    print("\nStep 3: Starting async feed...")
    await feed.start()
    
    # Let it run for a bit
    await asyncio.sleep(0.1)
    
    print(f"\n  Queue depth during processing: {feed.queue_size()}")
    
    print("\nStep 4: Graceful shutdown...")
    await feed.stop()
    print("  ✓ Producer stopped")
    print("  ✓ Queue drained")
    print("  ✓ Consumer stopped")
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    for instrument in sorted(tick_count.keys()):
        print(f"\n{instrument}:")
        print(f"  Ticks processed: {tick_count[instrument]}")
        print(f"  Total volume: {total_volume[instrument]:,}")
    
    print("\n" + "="*70)
    print("ARCHITECTURE NOTES")
    print("="*70)
    print("""
This demonstrates the async market data pipeline:

1. ReplayMarketData: Deterministic CSV-based tick source
2. AsyncTickProducer: Publishes ticks to bounded queue
3. asyncio.Queue: Provides back-pressure (blocks when full)
4. AsyncTickConsumer: Processes ticks via async handler
5. Graceful shutdown: Waits for queue to drain

In production, ReplayMarketData would be replaced by:
- WebSocket feed from Zerodha Kite Connect
- Direct market data vendor connection
- Any async tick source

The rest of the pipeline remains unchanged - this is the
boundary where live/mock data sources plug in.
""")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
