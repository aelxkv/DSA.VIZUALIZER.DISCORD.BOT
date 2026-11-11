"""/visualize: validate input, render, then post everything into a thread."""

from __future__ import annotations

import contextlib
import io
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import algos  # noqa: F401  (registers every algorithm)
import config
import service
from bot import GENERIC_ERROR, DsaBot
from cogs._util import resolve_channel, with_help_hint
from core import registry
from core.errors import BotError, RenderError, UserInputError
from core.logtext import build_log, closing_message, info_message, thread_title
from core.spec import build_spec

log = logging.getLogger(__name__)

NO_MENTIONS = discord.AllowedMentions.none()
BUSY_TEXT = "I'm busy with other runs right now. Please try again in a few seconds."


def algo_choices() -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=f"{info.category}: {info.title}", value=info.key)
        for info in registry.all_algos()
    ]


class Visualize(commands.Cog):
    def __init__(self, bot: DsaBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="visualize",
        description="Animate a data-structure or algorithm and keep every step in a thread.",
    )
    @app_commands.describe(
        algo="What to run",
        data="Numbers like 5,2,9,1 (or edges like 1-2,1-3 for graphs). Leave empty for random.",
        size="How many random items/nodes to generate",
        target="Search algorithms: the value to find",
        start="Graph algorithms: the start node",
    )
    @app_commands.choices(algo=algo_choices())
    @app_commands.checks.cooldown(
        1, config.RUN_COOLDOWN_S, key=lambda interaction: interaction.user.id
    )
    @app_commands.guild_only()
    async def visualize(
        self,
        interaction: discord.Interaction,
        algo: app_commands.Choice[str],
        data: Optional[app_commands.Range[str, 1, config.MAX_DATA_CHARS]] = None,
        size: Optional[app_commands.Range[int, config.MIN_ITEMS, config.MAX_ITEMS]] = None,
        target: Optional[app_commands.Range[int, config.MIN_VALUE, config.MAX_VALUE]] = None,
        start: Optional[app_commands.Range[int, 1, config.MAX_GRAPH_NODES]] = None,
    ) -> None:
        # 1. Cheap checks first, answered privately (nothing public yet).
        channel = await resolve_channel(interaction)
        if not isinstance(channel, discord.TextChannel):
            raise UserInputError("Use this in a normal text channel (not inside a thread).")
        spec, notes = build_spec(algo.value, data, size, target, start, random.Random())
        if self.bot.gate.busy:
            raise UserInputError(BUSY_TEXT)

        # 2. Discord gives us 3 seconds: acknowledge, then do the heavy work.
        await interaction.response.defer(thinking=True)
        try:
            animation = await self.bot.gate.run(service.make_animation, spec)
        except BotError as exc:
            log.warning("run failed algo=%s: %s", spec.algo, exc)
            # Only our own user-safe messages are shown; internal ones stay in the log.
            text = str(exc) if isinstance(exc, (UserInputError, RenderError)) else GENERIC_ERROR
            self.bot.stats.record_run(spec.algo, ok=False)
            await interaction.edit_original_response(
                content=f"❌ {with_help_hint(text, 'visualize')}"
            )
            return
        self.bot.stats.record_run(spec.algo, animation.elapsed_ms)
        run = animation.run

        # 3. First message holds the machine-readable run line; thread hangs off it.
        requester = discord.utils.escape_markdown(interaction.user.display_name)
        message = await interaction.edit_original_response(
            content=info_message(run, requester, notes), allowed_mentions=NO_MENTIONS
        )

        def gif_file() -> discord.File:  # a File can only be sent once: make a fresh one
            return discord.File(io.BytesIO(animation.gif.data), filename=f"{spec.algo}.gif")

        thread = await self._create_thread(channel, message, thread_title(run))
        if thread is None:
            # No thread permission: still deliver the animation, just without a log.
            await interaction.edit_original_response(
                content=message.content
                + "\n⚠️ I can't create threads here (needs **Create Public Threads**), "
                "so `/step` won't work for this run.",
                attachments=[gif_file()],
                allowed_mentions=NO_MENTIONS,
            )
            return

        # 4. Post the animation, the key-step log and the closing message.
        try:
            await thread.send("🎞️ Animation", file=gif_file(), allowed_mentions=NO_MENTIONS)
            for chunk in build_log(run):
                await thread.send(chunk, allowed_mentions=NO_MENTIONS)
            reduced = animation.gif.keys_only or animation.gif.frames < len(run.steps)
            await thread.send(closing_message(run, reduced=reduced), allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            log.exception("posting to thread %s failed", thread.id)
            with contextlib.suppress(discord.HTTPException):
                await thread.send("⚠️ I couldn't post everything (Discord refused a message).")

    @staticmethod
    async def _create_thread(
        channel: discord.TextChannel, message: discord.Message, name: str
    ) -> discord.Thread | None:
        """Thread started from the first message (so thread id == message id)."""
        for minutes in (config.ARCHIVE_MINUTES, config.ARCHIVE_FALLBACK_MINUTES):
            try:
                return await channel.create_thread(
                    name=name, message=message, auto_archive_duration=minutes
                )
            except discord.Forbidden:
                return None
            except discord.HTTPException:
                log.warning("thread creation failed with archive=%s", minutes, exc_info=True)
        return None


async def setup(bot: DsaBot) -> None:
    await bot.add_cog(Visualize(bot))
