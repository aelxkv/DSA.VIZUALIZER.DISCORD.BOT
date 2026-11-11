"""/help: commands, options and examples, generated from the live command list."""

from __future__ import annotations

import contextlib
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
import help_pages
from bot import DsaBot
from core.errors import UserInputError
from core.help_content import ENTRIES, TOPICS
from version import __version__

log = logging.getLogger(__name__)
VIEW_TIMEOUT_S = 180


def link_buttons(invite_url: str | None, support_url: str | None) -> list[discord.ui.Button]:
    """Invite and (optional) support link buttons."""
    buttons: list[discord.ui.Button] = []
    if invite_url:
        buttons.append(
            discord.ui.Button(
                style=discord.ButtonStyle.link, label="Invite the bot", url=invite_url
            )
        )
    if support_url:
        buttons.append(
            discord.ui.Button(style=discord.ButtonStyle.link, label="Support", url=support_url)
        )
    return buttons


class PageSelect(discord.ui.Select["HelpView"]):
    def __init__(self, pages: list[tuple[str, str, str]], current: str) -> None:
        options = [
            discord.SelectOption(
                label=label, value=key, description=desc[:100], default=(key == current)
            )
            for key, label, desc in pages
        ]
        super().__init__(
            placeholder="Choose a help page", options=options, min_values=1, max_values=1, row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert view is not None
        key = self.values[0]
        for option in self.options:
            option.default = option.value == key
        try:
            embed = help_pages.page_embed(key, view.cmds, __version__)
        except KeyError:  # a stale menu entry: ignore quietly
            await interaction.response.defer()
            return
        await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    """Page menu + link buttons. Only the person who ran /help can use the menu."""

    def __init__(
        self,
        owner_id: int,
        cmds: list[app_commands.Command],
        current: str,
        buttons: list[discord.ui.Button],
    ) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_S)
        self.owner_id = owner_id
        self.cmds = cmds
        self.interaction: discord.Interaction | None = None
        self.add_item(PageSelect(help_pages.menu_pages(cmds), current))
        for button in buttons:
            button.row = 1
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "This menu belongs to someone else. Run `/help` to get your own.", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                child.disabled = True
        if self.interaction is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.interaction.edit_original_response(view=self)


class Help(commands.Cog):
    def __init__(self, bot: DsaBot) -> None:
        self.bot = bot

    def _cmds(self) -> list[app_commands.Command]:
        return [c for c in self.bot.tree.get_commands() if isinstance(c, app_commands.Command)]

    @app_commands.command(
        name="help", description="How to use this bot: commands, options and examples."
    )
    @app_commands.describe(
        command="Show full details for one command",
        topic="Open a reference page",
        public="Show the answer to everyone in the channel (default: only you)",
    )
    @app_commands.choices(
        topic=[app_commands.Choice(name=label, value=key) for key, label, _ in TOPICS]
    )
    @app_commands.checks.cooldown(
        1, config.HELP_COOLDOWN_S, key=lambda interaction: interaction.user.id
    )
    @app_commands.guild_only()
    async def show_help(
        self,
        interaction: discord.Interaction,
        command: Optional[app_commands.Range[str, 1, 32]] = None,  # noqa: UP045
        topic: Optional[app_commands.Choice[str]] = None,  # noqa: UP045
        public: bool = False,
    ) -> None:
        if command and topic:
            raise UserInputError("Use either `command` or `topic`, not both.")
        cmds = self._cmds()
        buttons = link_buttons(self.bot.invite_url(), self.bot.support_url)
        view: discord.ui.View
        if command:
            embed = self._command_page(cmds, command)
            view = discord.ui.View(timeout=None)
            for button in buttons:
                view.add_item(button)
        else:
            current = f"topic:{topic.value}" if topic else "overview"
            embed = help_pages.page_embed(current, cmds, __version__)
            view = HelpView(interaction.user.id, cmds, current, buttons)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=not public)
        if isinstance(view, HelpView):
            view.interaction = interaction

    @staticmethod
    def _command_page(cmds: list[app_commands.Command], name: str) -> discord.Embed:
        key = name.strip().lstrip("/").lower()
        for cmd in cmds:
            if cmd.qualified_name == key:
                return help_pages.command_embed(cmd, ENTRIES.get(key), __version__)
        shown = key.replace("`", "'")[:30]
        raise UserInputError(f"There is no command called `{shown}`. Use `/help` to see them all.")

    @show_help.autocomplete("command")
    async def command_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.strip().lstrip("/").lower()
        matches = [c for c in self._cmds() if needle in c.qualified_name]
        return [
            app_commands.Choice(
                name=f"/{c.qualified_name} · {c.description}"[:100], value=c.qualified_name
            )
            for c in sorted(matches, key=lambda c: c.qualified_name)[:25]
        ]


async def setup(bot: DsaBot) -> None:
    await bot.add_cog(Help(bot))
