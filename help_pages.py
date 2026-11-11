"""Embed builders for /help. Option tables come from the real command definitions."""

from __future__ import annotations

from collections.abc import Sequence

import discord
from discord import AppCommandOptionType, app_commands

import branding
import config
from core import complexity, registry
from core.help_content import (
    CATEGORY_BLURBS,
    CATEGORY_ICONS,
    CATEGORY_ORDER,
    ENTRIES,
    FAQ,
    TOPICS,
    HelpEntry,
)
from core.logtext import LEGENDS

COLOR = 0x3B82F6
FIELD_LIMIT = 1024
Command = app_commands.Command


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def add_lines_field(embed: discord.Embed, name: str, lines: Sequence[str]) -> None:
    """Add lines as one or more fields, never exceeding Discord's field limit."""
    chunk: list[str] = []
    size = 0
    first = True
    for raw in lines:
        line = _clip(raw, FIELD_LIMIT - 24)
        if chunk and size + len(line) + 1 > FIELD_LIMIT:
            embed.add_field(
                name=name if first else f"{name} (cont.)", value="\n".join(chunk), inline=False
            )
            first, chunk, size = False, [], 0
        chunk.append(line)
        size += len(line) + 1
    if chunk:
        embed.add_field(
            name=name if first else f"{name} (cont.)", value="\n".join(chunk), inline=False
        )


def _base(title: str, description: str, version: str) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=COLOR)
    embed.set_footer(text=f"{branding.NAME} v{version}")
    return embed


# ---- option documentation (generated from the command definitions) ----------
def kind_label(param: app_commands.Parameter) -> str:
    if param.choices:
        return f"choice of {len(param.choices)}"
    kind = param.type
    if kind is AppCommandOptionType.integer:
        low, high = param.min_value, param.max_value
        return (
            f"whole number {low}-{high}" if low is not None and high is not None else "whole number"
        )
    if kind is AppCommandOptionType.string:
        return f"text (max {param.max_value} chars)" if param.max_value else "text"
    if kind is AppCommandOptionType.boolean:
        return "yes/no"
    return kind.name.lower()


def usage_text(cmd: Command) -> str:
    parts = [f"/{cmd.qualified_name}"]
    for param in cmd.parameters:
        parts.append(param.display_name if param.required else f"[{param.display_name}]")
    return " ".join(parts)


def option_lines(cmd: Command) -> list[str]:
    lines = []
    for param in cmd.parameters:
        star = "*" if param.required else ""
        lines.append(f"• `{param.display_name}{star}` · {kind_label(param)} · {param.description}")
    return lines


def _entry(cmd: Command) -> HelpEntry | None:
    return ENTRIES.get(cmd.qualified_name)


def _category(cmd: Command) -> str:
    entry = _entry(cmd)
    return entry.category if entry else "Other"


def group_by_category(cmds: Sequence[Command]) -> dict[str, list[Command]]:
    groups: dict[str, list[Command]] = {}
    for cmd in sorted(cmds, key=lambda c: c.qualified_name):
        groups.setdefault(_category(cmd), []).append(cmd)
    ordered = {c: groups[c] for c in CATEGORY_ORDER if c in groups}
    ordered.update({c: v for c, v in groups.items() if c not in ordered})
    return ordered


# ---- pages ---------------------------------------------------------------------
def overview_embed(cmds: Sequence[Command], version: str) -> discord.Embed:
    embed = _base(
        f"📘 {branding.NAME}",
        f"{branding.TAGLINE}\n\nPick a page from the menu below, or use `/help command:<name>` for full details.",
        version,
    )
    for category, group in group_by_category(cmds).items():
        icon = CATEGORY_ICONS.get(category, "•")
        lines = [f"`/{c.qualified_name}` · {c.description}" for c in group]
        add_lines_field(embed, f"{icon} {category}", lines)
    add_lines_field(embed, "Quick start", list(branding.QUICK_START))
    return embed


def category_embed(category: str, cmds: Sequence[Command], version: str) -> discord.Embed:
    icon = CATEGORY_ICONS.get(category, "•")
    embed = _base(f"{icon} {category}", CATEGORY_BLURBS.get(category, ""), version)
    for cmd in group_by_category(cmds).get(category, []):
        entry = _entry(cmd)
        text = [entry.summary if entry else cmd.description, f"`{usage_text(cmd)}`"]
        if cmd.parameters:
            required = [p.display_name for p in cmd.parameters if p.required]
            optional = [p.display_name for p in cmd.parameters if not p.required]
            if required:
                text.append("Required: " + ", ".join(f"`{n}`" for n in required))
            if optional:
                text.append("Optional: " + ", ".join(f"`{n}`" for n in optional))
        text.append(f"Details: `/help command:{cmd.qualified_name}`")
        embed.add_field(
            name=f"/{cmd.qualified_name}", value=_clip("\n".join(text), FIELD_LIMIT), inline=False
        )
    return embed


def command_embed(cmd: Command, entry: HelpEntry | None, version: str) -> discord.Embed:
    summary = entry.summary if entry else cmd.description
    embed = _base(f"/{cmd.qualified_name}", summary, version)
    embed.add_field(name="Usage", value=f"```\n{usage_text(cmd)}\n```", inline=False)
    if cmd.parameters:
        add_lines_field(embed, "Options  (* = required)", option_lines(cmd))
    else:
        embed.add_field(name="Options", value="None. Just run it.", inline=False)
    if entry:
        if entry.examples:
            add_lines_field(embed, "Examples", [f"`{e}`" for e in entry.examples])
        if entry.limits:
            add_lines_field(embed, "Limits", [f"• {x}" for x in entry.limits])
        if entry.notes:
            add_lines_field(embed, "Notes", [f"• {x}" for x in entry.notes])
        if entry.see_also:
            embed.add_field(
                name="See also", value=" · ".join(f"`/{x}`" for x in entry.see_also), inline=False
            )
        embed.set_footer(
            text=f"{entry.category} · since v{entry.since} · {branding.NAME} v{version}"
        )
    return embed


def topic_embed(topic: str, version: str) -> discord.Embed:
    titles = {key: (label, desc) for key, label, desc in TOPICS}
    if topic not in titles:
        raise KeyError(topic)
    label, desc = titles[topic]
    embed = _base(label, desc, version)
    if topic == "algorithms":
        by_cat: dict[str, list[str]] = {}
        for info in registry.all_algos():
            c = complexity.get(info.key)
            line = f"**{info.title}** · avg {c.average} · worst {c.worst} · space {c.space}"
            by_cat.setdefault(info.category, []).append(line)
        for category, lines in by_cat.items():
            add_lines_field(embed, category, lines)
    elif topic == "limits":
        add_lines_field(
            embed,
            "Input",
            [
                f"• Sort/search: {config.MIN_ITEMS}-{config.MAX_ITEMS} items, values {config.MIN_VALUE}-{config.MAX_VALUE}",
                f"• Trees: up to {config.MAX_TREE_NODES} distinct values",
                f"• Graphs: nodes 1-{config.MAX_GRAPH_NODES}, up to {config.MAX_GRAPH_EDGES} edges",
            ],
        )
        add_lines_field(
            embed,
            "Cooldowns",
            [
                f"• /visualize: {config.RUN_COOLDOWN_S:.0f} s",
                f"• /step: {config.STEP_COOLDOWN_S:.0f} s",
                f"• /help: {config.HELP_COOLDOWN_S:.0f} s",
                f"• /about and /stats: {config.INFO_COOLDOWN_S:.0f} s",
            ],
        )
        add_lines_field(
            embed,
            "Rendering",
            [
                f"• One animation at a time, {config.MAX_WAITING} can wait",
                f"• Up to {config.MAX_FRAMES} frames; long runs show key steps only",
                f"• Give up after {config.RENDER_TIMEOUT_S:.0f} s",
            ],
        )
    elif topic == "colors":
        for kind, text in LEGENDS.items():
            names = {"bars": "Sorting", "cells": "Searching", "graph": "Graphs", "tree": "Trees"}
            embed.add_field(name=names[kind], value=text, inline=False)
    else:  # faq
        for question, answer in FAQ:
            embed.add_field(
                name=_clip(question, 250), value=_clip(answer, FIELD_LIMIT), inline=False
            )
    return embed


# ---- menu ------------------------------------------------------------------------
def menu_pages(cmds: Sequence[Command]) -> list[tuple[str, str, str]]:
    """(key, label, description) for the dropdown, in display order."""
    pages = [("overview", "Overview", "All commands at a glance")]
    for category in group_by_category(cmds):
        pages.append((f"cat:{category}", category, CATEGORY_BLURBS.get(category, "Commands")))
    pages.extend((f"topic:{key}", label, desc) for key, label, desc in TOPICS)
    return pages


def page_embed(key: str, cmds: Sequence[Command], version: str) -> discord.Embed:
    if key == "overview":
        return overview_embed(cmds, version)
    kind, _, name = key.partition(":")
    if kind == "cat":
        return category_embed(name, cmds, version)
    if kind == "topic":
        return topic_embed(name, version)
    raise KeyError(key)
