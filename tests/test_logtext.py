import random

import config
from core.logtext import build_log, closing_message, info_message, thread_title
from core.runner import execute
from core.spec import RunSpec, build_spec, parse_line


def test_log_chunks_fit_discord_limit_in_worst_case():
    run = execute(RunSpec(algo="bubble", values=tuple(range(20, 0, -1))))
    for chunk in build_log(run):
        assert len(chunk) <= 2000


def test_log_is_truncated_with_hint(monkeypatch):
    monkeypatch.setattr(config, "MAX_LOG_MESSAGES", 1)
    monkeypatch.setattr(config, "LOG_CHUNK_CHARS", 300)
    run = execute(RunSpec(algo="bubble", values=tuple(range(20, 0, -1))))
    messages = build_log(run)
    assert len(messages) == 2 and "/step" in messages[-1]


def test_log_lines_are_numbered_with_real_step_numbers():
    run = execute(RunSpec(algo="selection", values=(3, 1, 2)))
    text = "".join(build_log(run))
    for step in run.key_steps:
        assert f"{step.n:>3} |" in text


def test_info_message_round_trips_and_titles_are_short():
    rng = random.Random(1)
    for key in ("bubble", "binary", "bfs", "inorder"):
        spec, notes = build_spec(key, None, None, None, None, rng)
        run = execute(spec)
        assert parse_line(info_message(run, "Alex", notes)) == spec
        assert len(thread_title(run)) <= 100
        assert f"/step n:<1-{len(run.steps)}>" in closing_message(run, reduced=False)
