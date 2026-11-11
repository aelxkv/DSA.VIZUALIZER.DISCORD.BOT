"""Every command has the documented per-user cooldown (and it is per user)."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import discord
import pytest
from discord import app_commands

import config
from cogs.help import Help
from cogs.info import Info
from cogs.step import Step
from cogs.visualize import Visualize

CASES = [
    (Visualize.visualize, config.RUN_COOLDOWN_S),
    (Step.step, config.STEP_COOLDOWN_S),
    (Help.show_help, config.HELP_COOLDOWN_S),
    (Info.about, config.INFO_COOLDOWN_S),
    (Info.stats, config.INFO_COOLDOWN_S),
]


def fake(user_id: int) -> discord.Interaction:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = SimpleNamespace(id=user_id)
    interaction.created_at = datetime.now(timezone.utc)
    return interaction


@pytest.mark.parametrize(("command", "seconds"), CASES, ids=[c.name for c, _ in CASES])
def test_command_cooldown_is_per_user_and_matches_config(command, seconds):
    checks = [c for c in command.checks if "cooldown" in c.__qualname__]
    assert len(checks) == 1
    check = checks[0]

    async def main():
        assert await check(fake(100)) is True
        with pytest.raises(app_commands.CommandOnCooldown) as caught:
            await check(fake(100))  # same user again: blocked
        assert seconds - 1 < caught.value.retry_after <= seconds
        assert await check(fake(200)) is True  # another user is unaffected

    asyncio.run(main())


def test_help_cooldown_is_three_seconds():
    assert config.HELP_COOLDOWN_S == 3.0
