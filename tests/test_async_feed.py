"""Tests for async market data feed."""

import asyncio
from datetime import datetime, UTC
from src.core.tick import Tick
from src.market_data.async_feed import (
    AsyncTickProducer,
    AsyncTickConsumer,
    AsyncMarketDataFeed,
    async_tick_iterator,
)


def _sample_ticks() -> list[Tick]:
    """Create sample ticks for testing."""
    return [
        Tick("NIFTY", datetime(2026, 1, 15, 9, 15, 1, tzinfo=UTC), 25000.0, 100),
        Tick("NIFTY", datetime(2026, 1, 15, 9, 15, 2, tzinfo=UTC), 25001.0, 120),
        Tick("NIFTY", datetime(2026, 1, 15, 9, 15, 3, tzinfo=UTC), 25002.0, 90),
    ]


async def test_async_tick_iterator_from_list():
    """Should convert list to async iterator."""
    ticks = _sample_ticks()
    result = []
    
    async for tick in async_tick_iterator(ticks):
        result.append(tick)
    
    assert len(result) == 3
    assert result == ticks


async def test_producer_publishes_ticks_to_queue():
    """Producer should publish all ticks to the queue."""
    queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=10)
    ticks = _sample_ticks()
    
    producer = AsyncTickProducer(async_tick_iterator(ticks), queue)
    await producer.start()
    
    # Give producer time to publish
    await asyncio.sleep(0.05)
    await producer.stop()
    
    # Verify all ticks were published
    received = []
    try:
        while True:
            tick = queue.get_nowait()
            if tick is not None:
                received.append(tick)
            else:
                break  # Got sentinel
    except asyncio.QueueEmpty:
        pass
    
    assert len(received) == 3
    assert received[0].price == 25000.0


async def test_consumer_receives_all_ticks():
    """Consumer should invoke handler for each tick."""
    queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=10)
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
    
    consumer = AsyncTickConsumer(queue, handler)
    await consumer.start()
    
    # Publish ticks
    for tick in _sample_ticks():
        await queue.put(tick)
    await queue.put(None)  # Sentinel
    
    # Wait for processing
    await asyncio.sleep(0.05)
    await consumer.stop()
    
    assert len(received) == 3
    assert received[0].price == 25000.0


async def test_bounded_queue_provides_backpressure():
    """Producer should block when queue is full."""
    queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=2)  # Small queue
    ticks = _sample_ticks()
    
    producer = AsyncTickProducer(async_tick_iterator(ticks), queue)
    await producer.start()
    
    # Give producer time to fill queue
    await asyncio.sleep(0.05)
    
    # Queue should be full or nearly full
    assert queue.qsize() >= 2
    
    await producer.stop()


async def test_full_pipeline_end_to_end():
    """Complete pipeline: producer -> queue -> consumer."""
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
    
    feed = AsyncMarketDataFeed(
        tick_source=_sample_ticks(),
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    await asyncio.sleep(0.1)  # Let it process
    await feed.stop()
    
    assert len(received) == 3
    assert all(isinstance(t, Tick) for t in received)


async def test_graceful_shutdown():
    """Shutdown should complete without hanging."""
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
        await asyncio.sleep(0.01)  # Simulate processing time
    
    feed = AsyncMarketDataFeed(
        tick_source=_sample_ticks(),
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    await asyncio.sleep(0.05)
    
    # Shutdown should wait for queue to drain
    await asyncio.wait_for(feed.stop(), timeout=2.0)
    
    # All ticks should be processed
    assert len(received) == 3


async def test_consumer_handles_handler_errors_gracefully():
    """Consumer should continue processing even if handler raises."""
    queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=10)
    received = []
    
    async def failing_handler(tick: Tick) -> None:
        if tick.price == 25001.0:
            raise ValueError("Simulated error")
        received.append(tick)
    
    consumer = AsyncTickConsumer(queue, failing_handler)
    await consumer.start()
    
    # Publish ticks
    for tick in _sample_ticks():
        await queue.put(tick)
    await queue.put(None)
    
    await asyncio.sleep(0.1)
    await consumer.stop()
    
    # Should have processed ticks 1 and 3 (tick 2 failed)
    assert len(received) == 2
    assert received[0].price == 25000.0
    assert received[1].price == 25002.0


async def test_queue_size_monitoring():
    """Feed should expose queue size for monitoring."""
    async def handler(tick: Tick) -> None:
        await asyncio.sleep(0.05)  # Slow handler to fill queue
    
    feed = AsyncMarketDataFeed(
        tick_source=_sample_ticks(),
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    await asyncio.sleep(0.02)  # Let producer fill queue
    
    queue_size = feed.queue_size()
    assert queue_size >= 0  # Queue should have items or be processing
    
    await feed.stop()


async def test_producer_with_delay():
    """Producer should respect delay between ticks."""
    queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=10)
    ticks = _sample_ticks()
    
    producer = AsyncTickProducer(
        async_tick_iterator(ticks),
        queue,
        delay_seconds=0.03
    )
    
    await producer.start()
    await asyncio.sleep(0.05)  # Less than time for all 3 ticks with delay
    
    # Should have produced fewer than all ticks due to delay
    items_in_queue = queue.qsize()
    assert items_in_queue < 3
    
    await producer.stop()


async def test_finite_feed_completes_without_hanging():
    """Regression test: finite feed should complete without hanging.
    
    This tests the critical bug where queue.join() would wait forever
    because the consumer didn't call task_done() on the sentinel.
    """
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
    
    feed = AsyncMarketDataFeed(
        tick_source=_sample_ticks(),
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    
    # Give producer time to finish and send sentinel
    await asyncio.sleep(0.05)
    
    # This should NOT hang - it should complete quickly
    # If it hangs, the sentinel task_done() bug is back
    try:
        await asyncio.wait_for(feed.stop(), timeout=1.0)
    except asyncio.TimeoutError:
        assert False, "Feed stop() hung - sentinel task_done() not called?"
    
    assert len(received) == 3


async def test_empty_feed_completes():
    """Empty feed should complete without hanging."""
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
    
    feed = AsyncMarketDataFeed(
        tick_source=[],  # Empty list
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    await asyncio.sleep(0.05)
    
    try:
        await asyncio.wait_for(feed.stop(), timeout=1.0)
    except asyncio.TimeoutError:
        assert False, "Empty feed hung on stop()"
    
    assert len(received) == 0


async def test_single_tick_feed_completes():
    """Single tick feed should complete without hanging."""
    received = []
    
    async def handler(tick: Tick) -> None:
        received.append(tick)
    
    single_tick = [_sample_ticks()[0]]
    
    feed = AsyncMarketDataFeed(
        tick_source=single_tick,
        handler=handler,
        max_queue_size=10
    )
    
    await feed.start()
    await asyncio.sleep(0.05)
    
    try:
        await asyncio.wait_for(feed.stop(), timeout=1.0)
    except asyncio.TimeoutError:
        assert False, "Single tick feed hung on stop()"
    
    assert len(received) == 1
