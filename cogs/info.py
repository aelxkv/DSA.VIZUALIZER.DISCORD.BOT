"""/about, /stats and the rotating bot status."""

from __future__ import annotations

import logging
import math
import platform
from typing import Any

import discord
import PIL
from discord import app_commands
from discord.ext import commands, tasks

import branding
import config
from bot import DsaBot
from cogs.help import link_buttons
from core import registry
from core.stats import StatsStore
from core.sysinfo import format_duration, rss_mb
from version import __version__

log = logging.getLogger(__name__)
COLOR = 0x3B82F6


def presence_for(index: int, *, version: str, algo_count: int, runs_total: int) -> discord.Activity:
    """The bot's status line; `index` rotates through the options."""
    options = [
        (discord.ActivityType.playing, f"/visualize · v{version}"),
        (discord.ActivityType.watching, f"{algo_count} algorithms"),
        (
            discord.ActivityType.watching,
            f"{runs_total:,} animated runs" if runs_total else "you learn DSA",
        ),
        (discord.ActivityType.listening, "/help"),
    ]
    kind, name = options[index % len(options)]
    return discord.Activity(type=kind, name=name)


def _bar(count: int, top: int, width: int = 8) -> str:
    filled = max(1, round(width * count / top)) if top and count else 0
    return "█" * filled + "░" * (width - filled)


def _algo_title(key: str) -> str:
    try:
        return registry.get(key).title
    except Exception:  # an algorithm that was removed since the stats were written
        return key


def _top_lines(counter: dict[str, int], *, titles: bool, n: int = 5) -> str:
    top = StatsStore.top(counter, n)
    if not top:
        return "Nothing yet"
    biggest = top[0][1]
    lines = []
    for key, count in top:
        label = _algo_title(key) if titles else f"/{key}"
        lines.append(f"`{_bar(count, biggest)}` {label} · {count:,}")
    return "\n".join(lines)


def _latency_text(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms" if math.isfinite(seconds) else "n/a"


def about_embed(
    *,
    uptime_s: float,
    guilds: int,
    latency_s: float,
    command_names: list[str],
    algo_count: int,
) -> discord.Embed:
    embed = discord.Embed(title=f"{branding.NAME}", description=branding.DESCRIPTION, color=COLOR)
    embed.add_field(name="Version", value=f"v{__version__}", inline=True)
    embed.add_field(name="Online for", value=format_duration(uptime_s), inline=True)
    embed.add_field(name="Servers", value=f"{guilds:,}", inline=True)
    embed.add_field(name="Algorithms", value=str(algo_count), inline=True)
    embed.add_field(name="Latency", value=_latency_text(latency_s), inline=True)
    embed.add_field(
        name="Commands",
        value=" ".join(f"`/{n}`" for n in sorted(command_names)) or "None",
        inline=False,
    )
    embed.add_field(
        name="Built with",
        value=(
            f"Python {platform.python_version()} · discord.py {discord.__version__} "
            f"· Pillow {PIL.__version__}"
        ),
        inline=False,
    )
    embed.set_footer(text=f"{branding.NAME} v{__version__}")
    return embed


def stats_embed(
    *,
    snapshot: dict[str, Any],
    uptime_s: float,
    guilds: int,
    owner: bool,
    latency_s: float = float("nan"),
    queue: int = 0,
    save_ok: bool | None = None,
    memory_mb: float | None = None,
) -> discord.Embed:
    life, session = snapshot["lifetime"], snapshot["session"]
    embed = discord.Embed(title=f"{branding.NAME} · Stats", color=COLOR)
    embed.add_field(name="Version", value=f"v{__version__}", inline=True)
    embed.add_field(name="Online for", value=format_duration(uptime_s), inline=True)
    embed.add_field(name="Servers", value=f"{guilds:,}", inline=True)
    embed.add_field(
        name="Animated runs",
        value=f"{life['runs_total']:,} total · {session['runs']:,} this session",
        inline=False,
    )
    embed.add_field(
        name="Top algorithms", value=_top_lines(life["algos"], titles=True), inline=False
    )
    embed.add_field(
        name="Commands used", value=_top_lines(life["commands"], titles=False), inline=False
    )
    embed.add_field(name="Counting since", value=str(life["first_started"])[:10], inline=True)
    embed.add_field(name="Restarts", value=f"{max(life['sessions'] - 1, 0):,}", inline=True)
    if owner:
        errors = sum(life["errors"].values())
        failed = life["runs_failed"]
        embed.add_field(
            name="🔧 Owner view",
            value=(f"Memory: {memory_mb:.0f} MB" if memory_mb is not None else "Memory: n/a")
            + f"\nRender time: avg {life['render_ms_avg']:.0f} ms · max {life['render_ms_max']:.0f} ms"
            + f"\nErrors: {errors:,} lifetime · {session['errors']:,} this session"
            + f"\nFailed runs: {failed:,} · bad input: {life['user_errors']:,}"
            + f"\nLatency: {_latency_text(latency_s)} · queue: {queue}"
            + "\nStats file: "
            + {True: "saving OK", False: "cannot save (memory only)", None: "not saved yet"}[
                save_ok
            ],
            inline=False,
        )
    embed.set_footer(text="Counts only. No user names, messages or inputs are stored.")
    return embed


class Info(commands.Cog):
    def __init__(self, bot: DsaBot) -> None:
        self.bot = bot
        self._status_index = 0

    async def cog_load(self) -> None:
        self.rotate_presence.start()

    async def cog_unload(self) -> None:
        self.rotate_presence.cancel()

    @tasks.loop(minutes=config.PRESENCE_INTERVAL_MIN)
    async def rotate_presence(self) -> None:
        try:
            snap = self.bot.stats.snapshot()
            activity = presence_for(
                self._status_index,
                version=__version__,
                algo_count=len(registry.all_algos()),
                runs_total=snap["lifetime"]["runs_total"],
            )
            self._status_index += 1
            await self.bot.change_presence(activity=activity)
        except Exception:  # the status is cosmetic: never let the loop die
            log.warning("could not update presence", exc_info=True)

    @rotate_presence.before_loop
    async def _before_presence(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="about", description="What this bot is, its version and links.")
    @app_commands.checks.cooldown(
        1, config.INFO_COOLDOWN_S, key=lambda interaction: interaction.user.id
    )
    @app_commands.guild_only()
    async def about(self, interaction: discord.Interaction) -> None:
        embed = about_embed(
            uptime_s=self.bot.uptime_s,
            guilds=len(self.bot.guilds),
            latency_s=self.bot.latency,
            command_names=[c.qualified_name for c in self.bot.tree.get_commands()],
            algo_count=len(registry.all_algos()),
        )
        view = discord.ui.View(timeout=None)
        for button in link_buttons(self.bot.invite_url(), self.bot.support_url):
            view.add_item(button)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="stats", description="Bot activity: runs and most used features.")
    @app_commands.checks.cooldown(
        1, config.INFO_COOLDOWN_S, key=lambda interaction: interaction.user.id
    )
    @app_commands.guild_only()
    async def stats(self, interaction: discord.Interaction) -> None:
        try:
            owner = await self.bot.is_owner(interaction.user)
        except discord.HTTPException:
            owner = False  # could not check: show the public view
        embed = stats_embed(
            snapshot=self.bot.stats.snapshot(),
            uptime_s=self.bot.uptime_s,
            guilds=len(self.bot.guilds),
            owner=owner,
            latency_s=self.bot.latency,
            queue=self.bot.gate.pending,
            save_ok=self.bot.stats.last_save_ok,
            memory_mb=rss_mb(),
        )
        # The owner view contains health details, so only the owner sees it.
        await interaction.response.send_message(embed=embed, ephemeral=owner)


async def setup(bot: DsaBot) -> None:
    await bot.add_cog(Info(bot))
