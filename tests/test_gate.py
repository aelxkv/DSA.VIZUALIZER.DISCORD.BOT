import asyncio
import threading
import time

import pytest

from core.errors import RenderError
from core.gate import RenderGate


def test_only_one_job_runs_at_a_time_and_pending_drains():
    gate = RenderGate(max_waiting=5, timeout_s=5)
    lock, state = threading.Lock(), {"now": 0, "max": 0}

    def job(i):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.02)
        with lock:
            state["now"] -= 1
        return i

    async def main():
        results = await asyncio.gather(*(gate.run(job, i) for i in range(5)))
        await asyncio.sleep(0.01)
        return results

    assert sorted(asyncio.run(main())) == list(range(5))
    assert state["max"] == 1
    assert not gate.busy and gate._pending == 0


def test_busy_when_queue_is_full():
    gate = RenderGate(max_waiting=1, timeout_s=5)

    async def main():
        tasks = [asyncio.create_task(gate.run(time.sleep, 0.05)) for _ in range(2)]
        await asyncio.sleep(0.01)
        assert gate.busy  # 1 running + 1 waiting == full
        await asyncio.gather(*tasks)
        assert not gate.busy

    asyncio.run(main())


def test_timeout_keeps_slot_until_thread_finishes():
    gate = RenderGate(max_waiting=1, timeout_s=0.05)

    async def main():
        with pytest.raises(RenderError):
            await gate.run(time.sleep, 0.3)
        # Waiter gave up, but the worker thread is still running:
        assert gate._pending == 1
        await asyncio.sleep(0.4)
        assert gate._pending == 0

    asyncio.run(main())


def test_errors_propagate_and_release_the_slot():
    gate = RenderGate(max_waiting=1, timeout_s=5)

    def boom():
        raise ValueError("nope")

    async def main():
        with pytest.raises(ValueError):
            await gate.run(boom)
        await asyncio.sleep(0.01)
        assert gate._pending == 0
        assert await gate.run(lambda: 42) == 42

    asyncio.run(main())


def test_cancelled_waiter_does_not_leak_pending():
    gate = RenderGate(max_waiting=3, timeout_s=5)

    async def main():
        first = asyncio.create_task(gate.run(time.sleep, 0.1))
        await asyncio.sleep(0.01)
        second = asyncio.create_task(gate.run(time.sleep, 0.01))
        await asyncio.sleep(0.01)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        await first
        await asyncio.sleep(0.01)
        assert gate._pending == 0

    asyncio.run(main())
