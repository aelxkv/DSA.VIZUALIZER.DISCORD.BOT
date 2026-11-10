import dataclasses

import pytest

import config
from core.errors import AlgoLimitError
from core.runner import execute, select_frames
from core.spec import RunSpec
from core.steps import Step


def _steps(pattern: str) -> list[Step]:
    """'K' = key step, '.' = fine step."""
    return [Step(n=i + 1, is_key=(c == "K")) for i, c in enumerate(pattern)]


def test_select_frames_returns_everything_when_small():
    steps = _steps("K..K")
    assert select_frames(steps, 10) == steps


def test_select_frames_drops_non_key_steps_first():
    steps = _steps("K" + "." * 50 + "K" + "." * 50 + "K")
    chosen = select_frames(steps, 20)
    assert len(chosen) == 20
    assert all(s in chosen for s in steps if s.is_key)
    assert [s.n for s in chosen] == sorted(s.n for s in chosen)


def test_select_frames_thins_keys_but_keeps_ends():
    steps = _steps("K" * 100)
    chosen = select_frames(steps, 10)
    assert len(chosen) == 10
    assert chosen[0] is steps[0] and chosen[-1] is steps[-1]


@pytest.mark.parametrize("total,limit", [(121, 120), (500, 120), (3, 2), (1000, 7)])
def test_select_frames_never_exceeds_limit(total, limit):
    steps = _steps("K" + "." * (total - 2) + "K")
    chosen = select_frames(steps, limit)
    assert len(chosen) <= limit
    assert chosen[0] is steps[0] and chosen[-1] is steps[-1]


def test_select_frames_rejects_tiny_budget():
    with pytest.raises(ValueError):
        select_frames(_steps("KK"), 1)


def test_execute_numbers_steps_and_flags_ends():
    run = execute(RunSpec(algo="bubble", values=(3, 1, 2)))
    assert [s.n for s in run.steps] == list(range(1, len(run.steps) + 1))
    assert run.steps[0].is_key and run.steps[-1].is_key


def test_execute_enforces_step_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_STEPS", 5)
    with pytest.raises(AlgoLimitError):
        execute(RunSpec(algo="bubble", values=(5, 4, 3, 2, 1)))


def test_worst_cases_stay_under_step_cap():
    worst = {
        "bubble": tuple(range(20, 0, -1)),
        "insertion": tuple(range(20, 0, -1)),
        "selection": tuple(range(20, 0, -1)),
        "quick": tuple(range(1, 21)),  # last-element pivot on sorted input
        "heap": tuple(range(1, 21)),
        "merge": tuple(range(20, 0, -1)),
        "radix": tuple(range(80, 100)),
    }
    for key, values in worst.items():
        run = execute(RunSpec(algo=key, values=values))
        assert len(run.steps) < config.MAX_STEPS, (key, len(run.steps))


def test_steps_are_frozen():
    run = execute(RunSpec(algo="bubble", values=(2, 1)))
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.steps[0].data = (1, 2)  # type: ignore[misc]
