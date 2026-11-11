"""Bot class, stats hooks and the global slash-command error handler."""

from __future__ import annotations

import asyncio
import logging
import os
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from cogs._util import with_help_hint
from core.errors import BotError, UserInputError
from core.gate import RenderGate
from core.stats import StatsStore

log = logging.getLogger(__name__)

EXTENSIONS = ("cogs.visualize", "cogs.step", "cogs.help", "cogs.info")
GENERIC_ERROR = "Something went wrong on my side. Please try again in a moment."

# Exactly what the bot needs; used for the invite link and checked against the README.
REQUIRED_PERMISSIONS = discord.Permissions(
    view_channel=True,
    send_messages=True,
    read_message_history=True,
    attach_files=True,
    embed_links=True,
    create_public_threads=True,
    send_messages_in_threads=True,
)


class DsaBot(commands.Bot):
    def __init__(self, stats: StatsStore | None = None) -> None:
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
            help_command=None,  # slash /help replaces the default prefix help
        )
        self.gate = RenderGate(config.MAX_WAITING, config.RENDER_TIMEOUT_S)
        self.stats = stats if stats is not None else StatsStore(config.get_stats_path())
        self.support_url = config.get_support_url()
        self.started_at = discord.utils.utcnow()
        self._started_monotonic = time.monotonic()
        self.tree.on_error = on_app_command_error

    @property
    def uptime_s(self) -> float:
        return time.monotonic() - self._started_monotonic

    def invite_url(self) -> str | None:
        """Invite link built from this bot's own id (None until we are logged in)."""
        if self.user is None:
            return None
        return discord.utils.oauth_url(
            self.user.id,
            permissions=REQUIRED_PERMISSIONS,
            scopes=("bot", "applications.commands"),
        )

    async def setup_hook(self) -> None:
        self.stats.load()
        self.stats.start_session()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        await self._sync_commands()
        self._save_stats.start()

    @tasks.loop(seconds=config.STATS_SAVE_INTERVAL_S)
    async def _save_stats(self) -> None:
        try:
            await asyncio.to_thread(self.stats.save)
        except Exception:  # a failing stats save must never stop the loop
            log.warning("periodic stats save failed", exc_info=True)

    async def close(self) -> None:
        self._save_stats.cancel()
        try:
            self.stats.save()
        except Exception:
            log.warning("final stats save failed", exc_info=True)
        await super().close()

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

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command | app_commands.ContextMenu,
    ) -> None:
        self.stats.record_command(command.qualified_name)


async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    """Turn every failure into a short, safe message; log the real cause."""
    original = getattr(error, "original", error)
    name = interaction.command.qualified_name if interaction.command else None
    stats = getattr(interaction.client, "stats", None)

    if isinstance(error, app_commands.CommandOnCooldown):
        text = f"⏳ Slow down - try again in {max(1, round(error.retry_after))}s."
    elif isinstance(error, app_commands.NoPrivateMessage):
        text = with_help_hint("This command only works in a server.", name)
    elif isinstance(original, UserInputError):
        text = with_help_hint(str(original), name)
        if stats is not None:
            stats.record_error("UserInputError", user=True)
    elif isinstance(error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)):
        text = with_help_hint(
            "I'm missing a permission for that. Ask a server admin to check my role.", name
        )
    else:
        kind = "known" if isinstance(original, BotError) else "unexpected"
        log.error("%s error in /%s", kind, name or "?", exc_info=original)
        if stats is not None:
            stats.record_error(type(original).__name__)
        text = with_help_hint(GENERIC_ERROR, name)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        log.warning("Could not deliver error message to the user", exc_info=True)
