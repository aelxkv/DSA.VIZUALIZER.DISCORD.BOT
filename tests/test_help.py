"""/help can never lie: coverage, limits and every example is run through the real parsers."""

import asyncio
import random
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import AppCommandOptionType, app_commands

import help_pages
from bot import DsaBot
from cogs.help import Help, HelpView, PageSelect, link_buttons
from core import registry
from core.errors import UserInputError
from core.help_content import ENTRIES, FAQ, TOPICS
from core.spec import build_spec
from core.stats import StatsStore

VERSION = "9.9.9"
EXTS = ("cogs.visualize", "cogs.step", "cogs.help", "cogs.info")


@pytest.fixture(scope="module")
def cmds():
    async def load():
        bot = DsaBot(stats=StatsStore())
        for ext in EXTS:
            await bot.load_extension(ext)
        found = list(bot.tree.get_commands())
        await bot.close()
        return found

    return asyncio.run(load())


def embed_size(embed: discord.Embed) -> int:
    return (
        len(embed.title or "")
        + len(embed.description or "")
        + sum(len(f.name) + len(f.value) for f in embed.fields)
        + len(embed.footer.text or "")
    )


def assert_embed_within_discord_limits(embed: discord.Embed) -> None:
    assert len(embed.title or "") <= 256 and len(embed.description or "") <= 4096
    assert len(embed.fields) <= 25
    for field in embed.fields:
        assert 0 < len(field.name) <= 256 and 0 < len(field.value) <= 1024, field.name
    assert embed_size(embed) <= 6000


# ---- coverage: a command cannot ship without help ---------------------------------
def test_every_command_has_a_help_entry_and_every_entry_a_command(cmds):
    assert {c.qualified_name for c in cmds} == set(ENTRIES)


def test_every_option_is_described(cmds):
    for cmd in cmds:
        assert cmd.description.strip()
        for param in cmd.parameters:
            assert param.description and param.description != "…", (cmd.name, param.name)


def test_entries_are_complete(cmds):
    names = {c.qualified_name for c in cmds}
    for entry in ENTRIES.values():
        assert entry.summary and entry.examples and re.fullmatch(r"\d+\.\d+\.\d+", entry.since)
        for ref in entry.see_also:
            assert ref.split()[0] in names, (entry.command, ref)


# ---- examples are real -------------------------------------------------------------
def parse_example(text: str) -> tuple[str, dict[str, str]]:
    assert text.startswith("/")
    name, _, rest = text[1:].partition(" ")
    marks = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"(\w+):", rest)]
    args = {}
    for i, (_start, end, key) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(rest)
        args[key] = rest[end:stop].strip()
    return name, args


def check_against_definition(cmd: app_commands.Command, args: dict[str, str]) -> dict[str, object]:
    params = {p.name: p for p in cmd.parameters}
    for p in params.values():
        assert not p.required or p.name in args, f"/{cmd.name} example misses required `{p.name}`"
    typed: dict[str, object] = {}
    for key, raw in args.items():
        assert key in params, f"/{cmd.name} has no option `{key}`"
        p = params[key]
        if p.choices:
            match = [
                c for c in p.choices if raw in (c.name, c.value) or c.name.endswith(f": {raw}")
            ]
            assert match, f"`{raw}` is not a choice of `{key}`"
            typed[key] = match[0].value
        elif p.type is AppCommandOptionType.integer:
            value = int(raw)
            assert p.min_value <= value <= p.max_value
            typed[key] = value
        elif p.type is AppCommandOptionType.boolean:
            assert raw in ("true", "false")
            typed[key] = raw == "true"
        else:
            if p.max_value:
                assert len(raw) <= p.max_value
            typed[key] = raw
    return typed


def test_every_help_example_is_valid_and_runs(cmds):
    by_name = {c.qualified_name: c for c in cmds}
    count = 0
    for entry in ENTRIES.values():
        for example in entry.examples:
            name, args = parse_example(example)
            assert name == entry.command
            typed = check_against_definition(by_name[name], args)
            if name == "visualize":  # semantic check with the real parser
                build_spec(
                    typed["algo"],
                    typed.get("data"),
                    typed.get("size"),
                    typed.get("target"),
                    typed.get("start"),
                    random.Random(1),
                )
            count += 1
    assert count >= 8


def test_help_examples_cover_every_algorithm_family():
    algos = " ".join(ENTRIES["visualize"].examples)
    for needle in ("Bubble Sort", "Binary Search", "BFS", "In-order", "size:"):
        assert needle in algos


# ---- pages ------------------------------------------------------------------------
def test_all_pages_fit_discord_limits(cmds):
    for key, _, _ in help_pages.menu_pages(cmds):
        assert_embed_within_discord_limits(help_pages.page_embed(key, cmds, VERSION))
    for cmd in cmds:
        assert_embed_within_discord_limits(
            help_pages.command_embed(cmd, ENTRIES.get(cmd.name), VERSION)
        )


def test_long_field_lists_are_split_not_cut():
    embed = discord.Embed()
    help_pages.add_lines_field(embed, "Many", [f"line {i} " + "x" * 90 for i in range(40)])
    assert len(embed.fields) > 1
    assert all(len(f.value) <= 1024 for f in embed.fields)
    assert sum(f.value.count("\n") + 1 for f in embed.fields) == 40


def test_command_page_documents_every_option(cmds):
    visualize = next(c for c in cmds if c.name == "visualize")
    embed = help_pages.command_embed(visualize, ENTRIES["visualize"], VERSION)
    text = " ".join(f.name + " " + f.value for f in embed.fields)
    for param in visualize.parameters:
        assert f"`{param.name}" in text and param.description in text
    assert "/visualize algo [data] [size] [target] [start]" in text
    assert "`algo*`" in text  # required marker
    assert "choice of 14" in text


def test_overview_lists_every_command(cmds):
    text = " ".join(f.value for f in help_pages.overview_embed(cmds, VERSION).fields)
    for cmd in cmds:
        assert f"`/{cmd.name}`" in text


def test_algorithm_topic_lists_every_algorithm():
    embed = help_pages.topic_embed("algorithms", VERSION)
    text = " ".join(f.value for f in embed.fields)
    for info in registry.all_algos():
        assert info.title in text


def test_limits_topic_reflects_config():
    import config

    text = " ".join(f.value for f in help_pages.topic_embed("limits", VERSION).fields)
    assert str(config.MAX_ITEMS) in text and str(config.MAX_TREE_NODES) in text


def test_topics_and_faq_are_consistent():
    for key, _, _ in TOPICS:
        help_pages.topic_embed(key, VERSION)
    with pytest.raises(KeyError):
        help_pages.topic_embed("nope", VERSION)
    assert all(q and a for q, a in FAQ)


# ---- the /help command and its menu ---------------------------------------------------
def make_interaction(user_id=1):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = SimpleNamespace(id=user_id)
    interaction.response = SimpleNamespace(
        send_message=AsyncMock(), edit_message=AsyncMock(), defer=AsyncMock()
    )
    interaction.edit_original_response = AsyncMock()
    return interaction


def make_cog(cmds):
    tree = SimpleNamespace(get_commands=lambda: cmds)
    bot = SimpleNamespace(
        tree=tree,
        invite_url=lambda: "https://discord.com/oauth2/authorize?client_id=1",
        support_url="https://example.com/help",
    )
    return Help(bot)


def test_help_overview_is_private_by_default_with_menu_and_buttons(cmds):
    async def main():
        cog, interaction = make_cog(cmds), make_interaction()
        await cog.show_help.callback(cog, interaction, None, None, False)
        kwargs = interaction.response.send_message.await_args.kwargs
        assert kwargs["ephemeral"] is True
        view = kwargs["view"]
        assert isinstance(view, HelpView)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        links = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert len(selects) == 1 and len(selects[0].options) <= 25
        assert [b.label for b in links] == ["Invite the bot", "Support"]

    asyncio.run(main())


def test_help_public_flag_and_command_page(cmds):
    async def main():
        cog, interaction = make_cog(cmds), make_interaction()
        await cog.show_help.callback(cog, interaction, "/Visualize", None, True)
        kwargs = interaction.response.send_message.await_args.kwargs
        assert kwargs["ephemeral"] is False
        assert kwargs["embed"].title == "/visualize"

    asyncio.run(main())


def test_help_rejects_unknown_command_and_both_arguments(cmds):
    async def main():
        cog, interaction = make_cog(cmds), make_interaction()
        with pytest.raises(UserInputError):
            await cog.show_help.callback(cog, interaction, "nonsense", None, False)
        with pytest.raises(UserInputError):
            await cog.show_help.callback(
                cog, interaction, "visualize", app_commands.Choice(name="FAQ", value="faq"), False
            )

    asyncio.run(main())


def test_autocomplete_filters_and_limits(cmds):
    async def main():
        cog = make_cog(cmds)
        everything = await cog.command_autocomplete(make_interaction(), "")
        assert {c.value for c in everything} == {c.name for c in cmds}
        assert [c.value for c in await cog.command_autocomplete(make_interaction(), "/vis")] == [
            "visualize"
        ]
        assert await cog.command_autocomplete(make_interaction(), "zzz") == []
        assert all(len(c.name) <= 100 for c in everything)

    asyncio.run(main())


def test_menu_only_works_for_the_person_who_asked(cmds):
    async def main():
        view = HelpView(owner_id=1, cmds=cmds, current="overview", buttons=[])
        intruder = make_interaction(user_id=2)
        assert await view.interaction_check(intruder) is False
        assert intruder.response.send_message.await_args.kwargs["ephemeral"] is True
        assert await view.interaction_check(make_interaction(user_id=1)) is True

    asyncio.run(main())


def test_menu_switches_pages_and_survives_bad_values(cmds):
    async def main():
        view = HelpView(owner_id=1, cmds=cmds, current="overview", buttons=[])
        select = next(c for c in view.children if isinstance(c, PageSelect))
        interaction = make_interaction()
        select._values = ["topic:faq"]
        await select.callback(interaction)
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        assert embed.title == "FAQ"
        assert [o.value for o in select.options if o.default] == ["topic:faq"]
        select._values = ["bogus"]
        stale = make_interaction()
        await select.callback(stale)
        stale.response.defer.assert_awaited_once()

    asyncio.run(main())


def test_menu_disables_itself_on_timeout(cmds):
    async def main():
        view = HelpView(owner_id=1, cmds=cmds, current="overview", buttons=[])
        view.interaction = make_interaction()
        await view.on_timeout()
        assert all(c.disabled for c in view.children if isinstance(c, discord.ui.Select))
        view.interaction.edit_original_response.assert_awaited_once()

    asyncio.run(main())


def test_link_buttons():
    assert link_buttons(None, None) == []
    only_invite = link_buttons("https://discord.com/x", None)
    assert [b.label for b in only_invite] == ["Invite the bot"]
    assert all(b.style is discord.ButtonStyle.link for b in only_invite)
