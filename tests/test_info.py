import asyncio
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import config
from bot import REQUIRED_PERMISSIONS, DsaBot
from cogs.info import Info, _bar, about_embed, presence_for, stats_embed
from core.stats import StatsStore
from version import __version__


def filled_snapshot():
    store = StatsStore()
    store.start_session()
    for _ in range(3):
        store.record_command("visualize")
        store.record_run("bubble", 100.0)
    store.record_run("merge", 50.0)
    store.record_command("help")
    store.record_error("ValueError")
    return store.snapshot()


def all_text(embed: discord.Embed) -> str:
    return " ".join(f"{f.name} {f.value}" for f in embed.fields) + (embed.description or "")


def test_about_embed_shows_version_and_description():
    embed = about_embed(
        uptime_s=3700,
        guilds=12,
        latency_s=0.0456,
        command_names=["help", "visualize"],
        algo_count=14,
    )
    text = all_text(embed)
    assert f"v{__version__}" in text and "1h 1m" in text and "46 ms" in text
    assert "`/help` `/visualize`" in text and "discord.py" in text and "Pillow" in text
    assert "Learn data structures" in embed.description


def test_about_survives_unknown_latency():
    embed = about_embed(uptime_s=1, guilds=0, latency_s=math.nan, command_names=[], algo_count=14)
    assert "n/a" in all_text(embed)


def test_public_stats_hide_owner_details():
    embed = stats_embed(snapshot=filled_snapshot(), uptime_s=90, guilds=3, owner=False)
    text = all_text(embed)
    assert "4 total · 4 this session" in text
    assert "Bubble Sort" in text and "/visualize" in text
    assert "Owner view" not in text and "Memory" not in text
    assert "No user names" in embed.footer.text


def test_owner_stats_show_health_details():
    embed = stats_embed(
        snapshot=filled_snapshot(),
        uptime_s=90,
        guilds=3,
        owner=True,
        latency_s=0.05,
        queue=2,
        save_ok=True,
        memory_mb=61.4,
    )
    text = all_text(embed)
    assert "Owner view" in text and "61 MB" in text and "avg 88 ms" in text
    assert "Errors: 1 lifetime" in text and "queue: 2" in text and "saving OK" in text


def test_stats_for_unknown_or_removed_algorithm_do_not_crash():
    snap = filled_snapshot()
    snap["lifetime"]["algos"]["removed_algo"] = 99
    assert "removed_algo" in all_text(stats_embed(snapshot=snap, uptime_s=1, guilds=1, owner=False))


def test_empty_stats():
    snap = StatsStore().snapshot()
    assert "Nothing yet" in all_text(stats_embed(snapshot=snap, uptime_s=1, guilds=0, owner=False))


def test_bar_scales():
    assert _bar(8, 8) == "█" * 8 and _bar(1, 8).count("█") == 1 and _bar(0, 8) == "░" * 8


def test_presence_rotates_and_wraps():
    seen = {presence_for(i, version="2.0.0", algo_count=14, runs_total=1234).name for i in range(8)}
    assert len(seen) == 4
    assert (
        presence_for(0, version="2.0.0", algo_count=14, runs_total=0).name == "/visualize · v2.0.0"
    )
    assert "1,234" in presence_for(2, version="2.0.0", algo_count=14, runs_total=1234).name
    assert "learn" in presence_for(2, version="2.0.0", algo_count=14, runs_total=0).name


def make_cog(owner_result):
    bot = SimpleNamespace(
        stats=StatsStore(),
        uptime_s=100.0,
        guilds=[1, 2],
        latency=0.05,
        gate=SimpleNamespace(pending=0),
        support_url=None,
        invite_url=lambda: "https://discord.com/oauth2/authorize?client_id=1",
        is_owner=owner_result,
        tree=SimpleNamespace(get_commands=lambda: [SimpleNamespace(qualified_name="stats")]),
    )
    return Info(bot)


def interaction():
    it = MagicMock(spec=discord.Interaction)
    it.user = SimpleNamespace(id=5)
    it.response = SimpleNamespace(send_message=AsyncMock())
    return it


def test_stats_command_owner_gets_private_extended_view():
    cog, it = make_cog(AsyncMock(return_value=True)), interaction()
    asyncio.run(cog.stats.callback(cog, it))
    kwargs = it.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is True and "Owner view" in all_text(kwargs["embed"])


def test_stats_command_everyone_else_gets_public_view():
    cog, it = make_cog(AsyncMock(return_value=False)), interaction()
    asyncio.run(cog.stats.callback(cog, it))
    kwargs = it.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is False and "Owner view" not in all_text(kwargs["embed"])


def test_stats_command_falls_back_to_public_if_owner_check_fails():
    failing = AsyncMock(
        side_effect=discord.HTTPException(SimpleNamespace(status=500, reason="x"), "boom")
    )
    cog, it = make_cog(failing), interaction()
    asyncio.run(cog.stats.callback(cog, it))
    assert it.response.send_message.await_args.kwargs["ephemeral"] is False


def test_about_command_has_link_buttons():
    cog, it = make_cog(AsyncMock()), interaction()
    asyncio.run(cog.about.callback(cog, it))
    view = it.response.send_message.await_args.kwargs["view"]
    assert [b.label for b in view.children] == ["Invite the bot"]


def test_invite_url_is_built_from_the_bots_own_id():
    bot = DsaBot(stats=StatsStore())
    assert bot.invite_url() is None  # not logged in yet
    bot._connection.user = SimpleNamespace(id=123456789012345678)
    url = bot.invite_url()
    assert "client_id=123456789012345678" in url
    assert f"permissions={REQUIRED_PERMISSIONS.value}" in url
    assert "applications.commands" in url and url.startswith("https://discord.com/")


def test_required_permissions_are_exactly_what_the_bot_uses():
    p = REQUIRED_PERMISSIONS
    assert p.create_public_threads and p.send_messages_in_threads and p.attach_files
    assert p.read_message_history and p.embed_links and p.view_channel and p.send_messages
    assert not (p.administrator or p.manage_messages or p.manage_channels or p.mention_everyone)


@pytest.mark.parametrize("name", ["_save_stats"])
def test_background_loops_use_configured_intervals(name):
    loop = getattr(DsaBot, name)
    assert loop.seconds == config.STATS_SAVE_INTERVAL_S


def test_presence_loop_interval():
    assert Info.rotate_presence.minutes == config.PRESENCE_INTERVAL_MIN
