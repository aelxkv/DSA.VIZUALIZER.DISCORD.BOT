import json
import threading

import config
from core.stats import StatsStore
from core.sysinfo import format_duration, rss_mb


def test_counts_and_session_split(tmp_path):
    store = StatsStore(tmp_path / "s.json")
    store.start_session()
    store.record_command("visualize")
    store.record_command("visualize")
    store.record_run("bubble", 120.0)
    store.record_run("bubble", 80.0)
    store.record_run("merge", ok=False)
    store.record_error("ValueError")
    store.record_error("UserInputError", user=True)
    snap = store.snapshot()
    life, session = snap["lifetime"], snap["session"]
    assert life["commands"] == {"visualize": 2}
    assert life["algos"] == {"bubble": 2}  # failed runs are not counted per algorithm
    assert life["runs_total"] == 3 and life["runs_failed"] == 1
    assert life["errors"] == {"ValueError": 1} and life["user_errors"] == 1
    assert life["render_ms_avg"] == 100.0 and life["render_ms_max"] == 120.0
    assert session["runs"] == 3 and session["errors"] == 1


def test_top_is_sorted_with_stable_ties():
    assert StatsStore.top({"b": 2, "a": 2, "c": 5, "d": 1}, 3) == [("c", 5), ("a", 2), ("b", 2)]


def test_round_trip_survives_restart_but_session_resets(tmp_path):
    path = tmp_path / "data" / "stats.json"
    first = StatsStore(path)
    first.start_session()
    first.record_run("quick", 10.0)
    assert first.save() is True
    assert not list(path.parent.glob("*.tmp"))  # atomic write leaves no temp file

    second = StatsStore(path)
    second.load()
    second.start_session()
    snap = second.snapshot()
    assert snap["lifetime"]["runs_total"] == 1 and snap["lifetime"]["sessions"] == 2
    assert snap["session"]["runs"] == 0


def test_saving_when_nothing_changed_writes_nothing(tmp_path):
    store = StatsStore(tmp_path / "s.json")
    assert store.save() is True
    assert not (tmp_path / "s.json").exists()


def test_damaged_file_is_quarantined_and_bot_starts_fresh(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    store = StatsStore(path)
    store.load()
    assert store.snapshot()["lifetime"]["runs_total"] == 0
    assert (tmp_path / "s.json.corrupt").exists()


def test_bad_values_and_unknown_schema_are_rejected(tmp_path):
    for bad in (
        {"schema": 99},
        {"schema": 1, "runs_total": -5},
        {"schema": 1, "runs_total": True},
        {"schema": 1, "commands": {"x": "many"}},
        {"schema": 1, "commands": {"k" * 100: 1}},
        [],
    ):
        path = tmp_path / "s.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        store = StatsStore(path)
        store.load()
        assert store.snapshot()["lifetime"]["runs_total"] == 0
        (tmp_path / "s.json.corrupt").unlink(missing_ok=True)


def test_unwritable_location_never_raises(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    store = StatsStore(blocker / "stats.json")  # parent is a file: cannot mkdir
    store.record_command("visualize")
    assert store.save() is False and store.last_save_ok is False
    assert store.snapshot()["lifetime"]["commands"] == {"visualize": 1}  # still counted


def test_memory_only_mode():
    store = StatsStore(None)
    store.record_run("bfs", 5.0)
    assert store.save() is False
    assert store.snapshot()["lifetime"]["runs_total"] == 1


def test_counter_size_is_bounded():
    store = StatsStore()
    for i in range(config.MAX_STATS_KEYS + 50):
        store.record_command(f"cmd{i}")
    commands = store.snapshot()["lifetime"]["commands"]
    assert len(commands) <= config.MAX_STATS_KEYS + 1 and commands["other"] == 50


def test_thread_safety():
    store = StatsStore()

    def work():
        for _ in range(500):
            store.record_command("visualize")

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.snapshot()["lifetime"]["commands"]["visualize"] == 4000


def test_format_duration():
    assert format_duration(0) == "0s" and format_duration(45) == "45s"
    assert format_duration(125) == "2m 5s" and format_duration(3 * 3600 + 7 * 60) == "3h 7m"
    assert format_duration(2 * 86400 + 4 * 3600) == "2d 4h" and format_duration(-9) == "0s"


def test_rss_is_a_positive_number_or_none():
    value = rss_mb()
    assert value is None or value > 0
