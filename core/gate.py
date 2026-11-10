"""Render gate: one CPU-heavy job at a time, a short queue, no event-loop stalls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from core.errors import RenderError

log = logging.getLogger(__name__)
T = TypeVar("T")


class RenderGate:
    """Runs blocking work in a thread, one job at a time.

    * `busy` turns true when the queue is full so callers can refuse early.
    * A timeout stops the *waiting*, but the slot is only freed when the worker
      thread really finishes (threads cannot be killed), so we never run more
      than one render at once even after a timeout.
    """

    def __init__(self, max_waiting: int, timeout_s: float) -> None:
        self._sem = asyncio.Semaphore(1)
        self._max_waiting = max_waiting
        self._timeout_s = timeout_s
        self._pending = 0  # running + queued

    @property
    def busy(self) -> bool:
        return self._pending >= 1 + self._max_waiting

    async def run(self, func: Callable[..., T], *args: Any) -> T:
        self._pending += 1
        try:
            await self._sem.acquire()
        except BaseException:
            self._pending -= 1
            raise
        task = asyncio.ensure_future(asyncio.to_thread(func, *args))
        task.add_done_callback(self._release)
        try:
            return await asyncio.wait_for(asyncio.shield(task), self._timeout_s)
        except asyncio.TimeoutError:
            log.warning("render timed out after %.0fs", self._timeout_s)
            raise RenderError("That took too long to render. Try a smaller input.") from None

    def _release(self, task: asyncio.Future[Any]) -> None:
        self._pending -= 1
        self._sem.release()
        if not task.cancelled():
            task.exception()  # mark retrieved so asyncio does not warn
