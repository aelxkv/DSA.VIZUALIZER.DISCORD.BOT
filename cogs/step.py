"""/step: re-render any single step of the run that owns this thread."""

from __future__ import annotations

import io
import logging

import discord
from discord import app_commands
from discord.ext import commands

import algos  # noqa: F401
import config
import service
from bot import GENERIC_ERROR, DsaBot
from cogs._util import resolve_channel, with_help_hint
from core.errors import BotError, RenderError, UserInputError
from core.spec import parse_line

log = logging.getLogger(__name__)

NOT_A_RUN = "Use `/step` inside the thread of a `/visualize` run."


class Step(commands.Cog):
    def __init__(self, bot: DsaBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="step", description="Show one step of this thread's run as an image."
    )
    @app_commands.describe(n="Step number (the log in this thread shows them)")
    @app_commands.checks.cooldown(
        1, config.STEP_COOLDOWN_S, key=lambda interaction: interaction.user.id
    )
    @app_commands.guild_only()
    async def step(
        self,
        interaction: discord.Interaction,
        n: app_commands.Range[int, 1, config.MAX_STEPS],
    ) -> None:
        thread = await resolve_channel(interaction)
        if not isinstance(thread, discord.Thread):
            raise UserInputError(NOT_A_RUN)
        if self.bot.gate.busy:
            raise UserInputError("I'm busy right now. Please try again in a few seconds.")
        await interaction.response.defer(thinking=True)

        spec = parse_line(await self._starter_text(thread))
        try:
            png, total = await self.bot.gate.run(service.make_step_image, spec, n)
        except BotError as exc:
            log.warning("step failed algo=%s n=%d: %s", spec.algo, n, exc)
            text = str(exc) if isinstance(exc, (UserInputError, RenderError)) else GENERIC_ERROR
            await interaction.edit_original_response(content=f"❌ {with_help_hint(text, 'step')}")
            return
        await interaction.edit_original_response(
            content=f"Step {n} of {total}",
            attachments=[discord.File(io.BytesIO(png), filename=f"step-{n}.png")],
        )

    async def _starter_text(self, thread: discord.Thread) -> str:
        """Text of the bot's own first message (thread id == that message's id)."""
        parent = thread.parent
        if parent is None:
            try:
                fetched = await thread.guild.fetch_channel(thread.parent_id or 0)
            except discord.HTTPException:
                raise UserInputError(NOT_A_RUN) from None
            parent = fetched if isinstance(fetched, discord.TextChannel) else None
        if parent is None:
            raise UserInputError(NOT_A_RUN)
        try:
            starter = await parent.fetch_message(thread.id)
        except discord.NotFound:
            raise UserInputError(
                "The run's first message was deleted, so I can't rebuild it."
            ) from None
        except discord.HTTPException:
            raise UserInputError(
                "I can't read the first message (needs **Read Message History**)."
            ) from None
        if self.bot.user is None or starter.author.id != self.bot.user.id:
            raise UserInputError(NOT_A_RUN)
        return starter.content


async def setup(bot: DsaBot) -> None:
    await bot.add_cog(Step(bot))
