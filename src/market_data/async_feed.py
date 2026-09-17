"""Asynchronous market data producer/consumer architecture.

Demonstrates the boundary where a real WebSocket feed would be connected.
Uses asyncio.Queue for back-pressure and clean shutdown semantics.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Protocol
from src.core.tick import Tick


class TickSource(Protocol):
    """Protocol for any synchronous tick source that can be adapted to async."""
    
    def stream_ticks(self, instrument: str) -> AsyncIterator[Tick]:
        """Stream ticks for an instrument."""
        ...


class AsyncTickProducer:
    """Produces ticks asynchronously and publishes to a queue.
    
    This models the producer side of a WebSocket feed boundary. In production,
    this would be replaced by an actual WebSocket consumer that receives ticks
    from a broker and publishes them to the same queue interface.
    """

    def __init__(
        self,
        tick_source: AsyncIterator[Tick],
        queue: asyncio.Queue[Tick | None],
        delay_seconds: float = 0.0
    ) -> None:
        """Initialize producer.
        
        Args:
            tick_source: Async iterator of ticks to produce
            queue: Bounded queue to publish ticks into
            delay_seconds: Optional delay between ticks (for simulation)
        """
        self._tick_source = tick_source
        self._queue = queue
        self._delay_seconds = delay_seconds
        self._task: asyncio.Task | None = None
        self._stopped = False

    async def start(self) -> None:
        """Start producing ticks in the background."""
        if self._task is not None:
            raise RuntimeError("Producer already started")
        
        self._task = asyncio.create_task(self._produce())

    async def stop(self) -> None:
        """Stop producing and signal consumers by sending None sentinel."""
        if self._stopped:
            return
            
        self._stopped = True
        
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Send sentinel to signal end of stream
        try:
            await asyncio.wait_for(self._queue.put(None), timeout=1.0)
        except asyncio.TimeoutError:
            pass  # Queue might be full, but we're stopping anyway

    async def _produce(self) -> None:
        """Internal production loop."""
        try:
            async for tick in self._tick_source:
                if self._stopped:
                    break
                
                # Await queue.put() - this provides back-pressure
                # If queue is full, this will block until space is available
                await self._queue.put(tick)
                
                if self._delay_seconds > 0:
                    await asyncio.sleep(self._delay_seconds)
                    
        except asyncio.CancelledError:
            # Clean cancellation
            raise
        except Exception as e:
            # Log error but don't crash - sentinel sent in finally
            print(f"Producer error: {e}")
        finally:
            # Always send sentinel when production stops
            if not self._stopped:
                try:
                    await self._queue.put(None)
                except:
                    pass


class AsyncTickConsumer:
    """Consumes ticks from a queue and invokes a handler callback.
    
    This models the consumer side where strategy/indicator code would
    receive ticks from the feed.
    """

    def __init__(
        self,
        queue: asyncio.Queue[Tick | None],
        handler: Callable[[Tick], Awaitable[None]]
    ) -> None:
        """Initialize consumer.
        
        Args:
            queue: Queue to consume ticks from
            handler: Async callback invoked for each tick
        """
        self._queue = queue
        self._handler = handler
        self._task: asyncio.Task | None = None
        self._stopped = False

    async def start(self) -> None:
        """Start consuming ticks in the background."""
        if self._task is not None:
            raise RuntimeError("Consumer already started")
        
        self._task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        """Stop consuming and wait for current handler to complete."""
        self._stopped = True
        
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume(self) -> None:
        """Internal consumption loop."""
        try:
            while not self._stopped:
                tick = await self._queue.get()
                
                # None is sentinel value indicating end of stream
                if tick is None:
                    self._queue.task_done()  # Must mark sentinel as done
                    break
                
                try:
                    await self._handler(tick)
                except Exception as e:
                    # Log error but continue processing
                    print(f"Consumer handler error: {e}")
                finally:
                    self._queue.task_done()
                    
        except asyncio.CancelledError:
            # Clean cancellation
            pass


async def async_tick_iterator(
    tick_source: AsyncIterator[Tick] | list[Tick]
) -> AsyncIterator[Tick]:
    """Convert a sync tick list or async iterator to async iterator.
    
    Helper to adapt different tick sources to the async producer interface.
    """
    if isinstance(tick_source, list):
        for tick in tick_source:
            yield tick
            await asyncio.sleep(0)  # Yield control to allow cancellation
    else:
        async for tick in tick_source:
            yield tick


class AsyncMarketDataFeed:
    """Complete async market data pipeline with producer/consumer.
    
    Provides a clean interface for the common pattern of:
    1. Start producer publishing ticks to queue
    2. Start consumer processing ticks from queue
    3. Graceful shutdown of both
    
    Example usage:
        async def handle_tick(tick: Tick) -> None:
            print(f"Received: {tick}")
        
        feed = AsyncMarketDataFeed(
            tick_source=replay_feed.stream_ticks("NIFTY"),
            handler=handle_tick,
            max_queue_size=100
        )
        
        await feed.start()
        await asyncio.sleep(5)  # Run for 5 seconds
        await feed.stop()
    """

    def __init__(
        self,
        tick_source: AsyncIterator[Tick] | list[Tick],
        handler: Callable[[Tick], Awaitable[None]],
        max_queue_size: int = 100,
        delay_seconds: float = 0.0
    ) -> None:
        """Initialize feed pipeline.
        
        Args:
            tick_source: Source of ticks (async iterator or list)
            handler: Async callback for each tick
            max_queue_size: Bounded queue size (for back-pressure)
            delay_seconds: Optional delay between ticks
        """
        self._queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=max_queue_size)
        
        async_source = async_tick_iterator(tick_source)
        self._producer = AsyncTickProducer(async_source, self._queue, delay_seconds)
        self._consumer = AsyncTickConsumer(self._queue, handler)

    async def start(self) -> None:
        """Start both producer and consumer."""
        await self._producer.start()
        await self._consumer.start()

    async def stop(self) -> None:
        """Gracefully stop producer, drain queue, stop consumer."""
        # For finite feeds, wait for producer to finish naturally
        # This ensures sentinel is properly sent
        if self._producer._task and not self._producer._task.done():
            try:
                await asyncio.wait_for(self._producer._task, timeout=1.0)
            except asyncio.TimeoutError:
                # Producer didn't finish naturally, force stop
                await self._producer.stop()
        
        # Wait for queue to be fully processed (including sentinel)
        await self._queue.join()
        
        # Stop consumer
        await self._consumer.stop()

    def queue_size(self) -> int:
        """Return current queue depth (useful for monitoring back-pressure)."""
        return self._queue.qsize()
