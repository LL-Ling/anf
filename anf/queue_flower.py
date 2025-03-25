import asyncio
from asyncio import Queue
from typing import Callable, Coroutine, Any


class AsyncProductionSystem:
    """
    Dev
    """
    def __init__(self, queue_size: int = 10):
        self.queue = Queue(maxsize=queue_size)
        self.producers = []
        self.consumers = []
        self.running = True

    async def start(
        self,
        num_producers: int,
        num_consumers: int,
        producer_fn: Callable[[], Coroutine[Any, Any, Any]],
        consumer_fn: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        self.running = True

        producer_Tasks = [
            asyncio.create_task(self._producer_loop(producer_fn))
            for _ in range(num_producers)
        ]

        consumer_Tasks = [
            asyncio.create_task(self._consumer_loop(consumer_fn))
            for _ in range(num_consumers)
        ]

        await asyncio.gather(*producer_Tasks, *consumer_Tasks)

    async def _producer_loop(self, producer_fn):
        while self.running:
            try:
                item = await producer_fn()
                await self.queue.put(item)
            except Exception as e:
                print(f"producer error: {e}")
                break

    async def _consumer_loop(self, consumer_fn):
        while self.running:
            try:
                item = await self.queue.get()
                await consumer_fn(item)
                self.queue.task_done()

            except Exception as e:
                print(f"consumer error: {e}")
                break

    def stop(self):
        self.running = False
