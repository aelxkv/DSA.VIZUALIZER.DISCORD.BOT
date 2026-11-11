import pytest

import config
from bot import GENERIC_ERROR, on_app_command_error
from cogs._util import with_help_hint
from core.errors import UserInputError
from tests.test_cogs import _error_interaction, run_async  # noqa: F401  (shared helpers)


def test_hint_text_and_no_duplicates():
    text = with_help_hint("Bad input.", "visualize")
    assert text == "Bad input.\nNeed help? `/help command:visualize`"
    assert with_help_hint(text, "visualize") == text
    assert with_help_hint("Oops", None).endswith("Need help? `/help`")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(type("E", (), {"original": UserInputError("Bad data")})(), id="user-input"),
        pytest.param(type("E", (), {"original": RuntimeError("secret")})(), id="unexpected"),
    ],
)
def test_error_messages_end_with_the_help_hint(error):
    interaction = _error_interaction()
    run_async(on_app_command_error(interaction, error))
    text = interaction.response.send_message.await_args.args[0]
    assert text.endswith("Need help? `/help command:visualize`")
    assert "secret" not in text
    assert GENERIC_ERROR in text or "Bad data" in text


def test_errors_are_counted_by_kind():
    interaction = _error_interaction()
    run_async(on_app_command_error(interaction, type("E", (), {"original": UserInputError("x")})()))
    run_async(on_app_command_error(interaction, type("E", (), {"original": ValueError("x")})()))
    stats = interaction.client.stats
    stats.record_error.assert_any_call("UserInputError", user=True)
    stats.record_error.assert_any_call("ValueError")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://discord.gg/abc123", "https://discord.gg/abc123"),
        ("  https://example.com/support  ", "https://example.com/support"),
        ("http://example.com", None),
        ("javascript:alert(1)", None),
        ("https://", None),
        ("https://exa mple.com", None),
        ("https://example.com/" + "a" * 600, None),
        ("", None),
    ],
)
def test_support_url_validation(monkeypatch, value, expected):
    monkeypatch.setenv("SUPPORT_URL", value)
    assert config.get_support_url() == expected


def test_stats_path_default_and_disable(monkeypatch):
    monkeypatch.delenv("STATS_PATH", raising=False)
    assert str(config.get_stats_path()) == "data/stats.json"
    monkeypatch.setenv("STATS_PATH", "")
    assert config.get_stats_path() is None
