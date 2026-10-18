"""Deferred session events: run a callback on the session's update tick once a future completes.

This is how database work (which runs on a worker thread) hands its result back to the
network session, so that all session state is only ever touched from the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Protocol

log = logging.getLogger("TaskEvent")


class Event(Protocol):
    def can_execute(self) -> bool: ...

    def execute(self) -> None: ...


class TaskEvent:
    """Executes ``callback`` after the future completes, regardless of its outcome."""

    def __init__(self, future: asyncio.Future, callback: Callable[[], None]):
        self._future = future
        self._callback = callback

    def can_execute(self) -> bool:
        return self._future.done()

    def execute(self) -> None:
        if not self._future.cancelled() and self._future.exception() is not None:
            log.error("Task failed before its callback ran", exc_info=self._future.exception())
        self._callback()


class TaskGenericEvent:
    """Executes ``callback(result)`` after the future completes; a failed future raises here."""

    def __init__(self, future: asyncio.Future, callback: Callable[[Any], None]):
        self._future = future
        self._callback = callback

    def can_execute(self) -> bool:
        return self._future.done()

    def execute(self) -> None:
        self._callback(self._future.result())
