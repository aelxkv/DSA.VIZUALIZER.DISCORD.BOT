"""Discord layer tested with mocks (no network): call order, limits, errors."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands

import config
from bot import DsaBot, on_app_command_error
from cogs.step import Step as StepCog
from cogs.visualize import Visualize, algo_choices
from core.errors import UserInputError
from core.gate import RenderGate
from core.logtext import info_message
from core.runner import execute
from core.spec import RunSpec


def run_async(coro):
    return asyncio.run(coro)


def make_bot():
    return SimpleNamespace(
        gate=RenderGate(config.MAX_WAITING, config.RENDER_TIMEOUT_S), user=SimpleNamespace(id=42)
    )


def make_interaction(channel):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = SimpleNamespace(id=7, display_name="Al*ex")
    interaction.channel = channel
    interaction.response = SimpleNamespace(defer=AsyncMock(), is_done=lambda: False)
    interaction.edit_original_response = AsyncMock()
    return interaction


def choice(key):
    return next(c for c in algo_choices() if c.value == key)


# ---- command tree ------------------------------------------------------------
def test_commands_load_with_expected_options():
    async def main():
        bot = DsaBot()
        for ext in ("cogs.visualize", "cogs.step"):
            await bot.load_extension(ext)
        commands = {c.name: c for c in bot.tree.get_commands()}
        assert set(commands) == {"visualize", "step"}
        assert len(commands["visualize"].parameters[0].choices) == 14
        names = [p.name for p in commands["visualize"].parameters]
        assert names == ["algo", "data", "size", "target", "start"]
        await bot.close()

    run_async(main())


def test_bot_uses_minimal_intents():
    intents = DsaBot().intents
    assert intents.guilds and not intents.message_content
    assert not intents.members and not intents.presences


# ---- /visualize --------------------------------------------------------------
def _visualize_setup():
    thread = MagicMock(spec=discord.Thread)
    thread.id = 555
    thread.send = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.create_thread = AsyncMock(return_value=thread)
    interaction = make_interaction(channel)
    first = SimpleNamespace(id=555, content="")

    async def edit(**kwargs):
        first.content = kwargs.get("content", first.content)
        return first

    interaction.edit_original_response = AsyncMock(side_effect=edit)
    return Visualize(make_bot()), interaction, channel, thread, first


def test_visualize_happy_path_posts_everything_in_a_thread():
    cog, interaction, channel, thread, first = _visualize_setup()
    run_async(
        cog.visualize.callback(cog, interaction, choice("bubble"), "5,2,9,1", None, None, None)
    )

    interaction.response.defer.assert_awaited_once()
    kwargs = channel.create_thread.await_args.kwargs
    assert kwargs["message"] is first and kwargs["auto_archive_duration"] == config.ARCHIVE_MINUTES
    assert kwargs["name"].startswith("Bubble Sort")
    # First message carries the run line and an escaped name.
    assert "v=1 | algo=bubble | data=5,2,9,1" in first.content and "Al\\*ex" in first.content
    sends = thread.send.await_args_list
    assert sends[0].kwargs["file"].filename == "bubble.gif"
    assert "/step" in sends[-1].args[0]
    assert all(c.kwargs.get("allowed_mentions") is not None or c.args for c in sends)
    for call in sends[1:]:
        assert len(call.args[0]) <= 2000


def test_visualize_rejects_threads_and_bad_input_before_deferring():
    cog, interaction, *_ = _visualize_setup()
    interaction.channel = MagicMock(spec=discord.Thread)
    with pytest.raises(UserInputError):
        run_async(
            cog.visualize.callback(cog, interaction, choice("bubble"), "5,2", None, None, None)
        )
    interaction.response.defer.assert_not_awaited()

    cog, interaction, *_ = _visualize_setup()
    with pytest.raises(UserInputError):
        run_async(
            cog.visualize.callback(cog, interaction, choice("bubble"), "5,x", None, None, None)
        )
    interaction.response.defer.assert_not_awaited()


def test_visualize_refuses_when_queue_is_full():
    cog, interaction, *_ = _visualize_setup()
    cog.bot.gate._pending = 1 + config.MAX_WAITING
    with pytest.raises(UserInputError):
        run_async(
            cog.visualize.callback(cog, interaction, choice("bubble"), "5,2", None, None, None)
        )


def test_visualize_without_thread_permission_still_delivers_the_gif():
    cog, interaction, channel, thread, first = _visualize_setup()
    channel.create_thread = AsyncMock(
        side_effect=discord.Forbidden(SimpleNamespace(status=403, reason="x"), "no")
    )
    run_async(cog.visualize.callback(cog, interaction, choice("merge"), None, 6, None, None))
    last = interaction.edit_original_response.await_args.kwargs
    assert last["attachments"] and "Create Public Threads" in last["content"]
    thread.send.assert_not_awaited()


def test_visualize_survives_discord_refusing_a_thread_message():
    cog, interaction, channel, thread, first = _visualize_setup()
    thread.send = AsyncMock(
        side_effect=discord.HTTPException(SimpleNamespace(status=400, reason="x"), "bad")
    )
    run_async(
        cog.visualize.callback(cog, interaction, choice("bubble"), "5,2", None, None, None)
    )  # no raise


# ---- /step -------------------------------------------------------------------
def _step_setup(author_id=42, content=None):
    spec = RunSpec(algo="bubble", values=(5, 2, 9, 1))
    text = content if content is not None else info_message(execute(spec), "Alex", [])
    parent = MagicMock(spec=discord.TextChannel)
    parent.fetch_message = AsyncMock(
        return_value=SimpleNamespace(author=SimpleNamespace(id=author_id), content=text)
    )
    thread = MagicMock(spec=discord.Thread)
    thread.id, thread.parent = 555, parent
    return StepCog(make_bot()), make_interaction(thread), parent


def test_step_renders_the_requested_step():
    cog, interaction, parent = _step_setup()
    run_async(cog.step.callback(cog, interaction, 3))
    parent.fetch_message.assert_awaited_once_with(555)
    kwargs = interaction.edit_original_response.await_args.kwargs
    assert kwargs["attachments"][0].filename == "step-3.png" and kwargs["content"].startswith(
        "Step 3 of"
    )


def test_step_rejects_foreign_or_damaged_threads():
    cog, interaction, _ = _step_setup(author_id=999)  # not written by this bot
    with pytest.raises(UserInputError):
        run_async(cog.step.callback(cog, interaction, 1))
    cog, interaction, _ = _step_setup(content="hello")
    with pytest.raises(UserInputError):
        run_async(cog.step.callback(cog, interaction, 1))
    cog, interaction, _ = _step_setup()
    interaction.channel = MagicMock(spec=discord.TextChannel)  # not a thread
    with pytest.raises(UserInputError):
        run_async(cog.step.callback(cog, interaction, 1))


def test_step_out_of_range_gives_friendly_message():
    cog, interaction, _ = _step_setup()
    run_async(cog.step.callback(cog, interaction, 1999))
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert content.startswith("❌") and "steps" in content


# ---- global error handler -----------------------------------------------------
def _error_interaction(done=False):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.command = SimpleNamespace(qualified_name="visualize")
    interaction.response = SimpleNamespace(send_message=AsyncMock(), is_done=lambda: done)
    interaction.followup = SimpleNamespace(send=AsyncMock())
    return interaction


def test_error_handler_messages():
    cooldown = app_commands.CommandOnCooldown(app_commands.Cooldown(1, 20), 12.4)
    interaction = _error_interaction()
    run_async(on_app_command_error(interaction, cooldown))
    assert "12s" in interaction.response.send_message.await_args.args[0]
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True

    wrapped = SimpleNamespace(original=UserInputError("Bad data"))
    interaction = _error_interaction()
    run_async(on_app_command_error(interaction, wrapped))
    assert interaction.response.send_message.await_args.args[0] == "Bad data"

    interaction = _error_interaction(done=True)  # already answered -> follow-up
    run_async(on_app_command_error(interaction, SimpleNamespace(original=RuntimeError("secret"))))
    text = interaction.followup.send.await_args.args[0]
    assert "secret" not in text and "went wrong" in text
