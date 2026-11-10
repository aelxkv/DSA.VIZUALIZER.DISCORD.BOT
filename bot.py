"""Bot class and the global slash-command error handler."""

from __future__ import annotations

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

import config
from core.errors import BotError, UserInputError
from core.gate import RenderGate

log = logging.getLogger(__name__)

EXTENSIONS = ("cogs.visualize", "cogs.step")
GENERIC_ERROR = "Something went wrong on my side. Please try again in a moment."


class DsaBot(commands.Bot):
    def __init__(self) -> None:
        # Smallest possible footprint: no privileged intents, no member or
        # message caches (the host has very little RAM).
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
            member_cache_flags=discord.MemberCacheFlags.none(),
            chunk_guilds_at_startup=False,
            max_messages=None,
        )
        self.gate = RenderGate(config.MAX_WAITING, config.RENDER_TIMEOUT_S)
        self.tree.on_error = on_app_command_error

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        await self._sync_commands()

    async def _sync_commands(self) -> None:
        """Sync only when asked (SYNC_COMMANDS=global|guild), never every start."""
        mode = os.environ.get("SYNC_COMMANDS", "none").strip().lower()
        if mode == "global":
            synced = await self.tree.sync()
            log.info("Synced %d command(s) globally", len(synced))
        elif mode == "guild":
            guild_id = os.environ.get("DEV_GUILD_ID", "").strip()
            if not guild_id.isdigit():
                log.error("SYNC_COMMANDS=guild needs a numeric DEV_GUILD_ID; skipping sync")
                return
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d command(s) to guild %s", len(synced), guild_id)
        else:
            log.info("Command sync skipped (SYNC_COMMANDS=%s)", mode)

    async def on_ready(self) -> None:
        log.info("Logged in as %s in %d server(s)", self.user, len(self.guilds))


async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    """Turn every failure into a short, safe message; log the real cause."""
    original = getattr(error, "original", error)
    if isinstance(error, app_commands.CommandOnCooldown):
        text = f"⏳ Slow down - try again in {max(1, round(error.retry_after))}s."
    elif isinstance(error, app_commands.NoPrivateMessage):
        text = "This command only works in a server."
    elif isinstance(original, UserInputError):
        text = str(original)
    elif isinstance(error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)):
        text = "I'm missing a permission for that. Ask a server admin to check my role."
    else:
        kind = "known" if isinstance(original, BotError) else "unexpected"
        log.error(
            "%s error in /%s",
            kind,
            interaction.command.qualified_name if interaction.command else "?",
            exc_info=original,
        )
        text = GENERIC_ERROR
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        log.warning("Could not deliver error message to the user", exc_info=True)
