"""The world tick: calls ``update(seconds_since_last_tick)`` continuously on the event loop."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

log = logging.getLogger("ThreadManager")


class UpdateLoop:
    def __init__(self, interval: float = 0.001):
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._shutdown_requested = False

    def initialise(self, update_action: Callable[[float], None]) -> None:
        self._shutdown_requested = False
        self._task = asyncio.get_running_loop().create_task(self._run(update_action))

    async def _run(self, update_action: Callable[[float], None]) -> None:
        last_tick = 0.0
        while not self._shutdown_requested:
            started = time.perf_counter()
            try:
                update_action(last_tick)
            except Exception:
                log.exception("Update tick failed")
            await asyncio.sleep(self._interval)
            last_tick = time.perf_counter() - started

    async def shutdown(self) -> None:
        self._shutdown_requested = True
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
