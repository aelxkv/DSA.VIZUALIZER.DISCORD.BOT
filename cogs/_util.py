"""Helpers shared by the command cogs."""

from __future__ import annotations

import discord


async def resolve_channel(
    interaction: discord.Interaction,
) -> discord.abc.GuildChannel | discord.Thread | None:
    """Return the real channel object, fetching it if it is not cached."""
    channel = interaction.channel
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        return channel
    guild = interaction.guild
    if guild is None or interaction.channel_id is None:
        return None
    try:
        found = guild.get_channel_or_thread(interaction.channel_id)
        if found is None:
            found = await guild.fetch_channel(interaction.channel_id)
        return found
    except discord.HTTPException:
        return None


def with_help_hint(text: str, command: str | None = None) -> str:
    """Append the standard pointer to /help (once) to a user-facing error."""
    if "Need help?" in text:
        return text
    target = f" command:{command}" if command else ""
    return f"{text}\nNeed help? `/help{target}`"
