"""Hand-written help text (the option tables are generated from the real commands).

Pure data, no Discord imports, so it is easy to test. Every slash command must
have an entry here; tests fail otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class HelpEntry:
    command: str  # top-level slash command name, without "/"
    category: str
    summary: str
    examples: tuple[str, ...]  # full slash text; tests run them through the real parsers
    since: str
    notes: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()
    see_also: tuple[str, ...] = ()


CATEGORY_ICONS = {"Visualize": "🎬", "Info": "ℹ️"}
CATEGORY_BLURBS = {
    "Visualize": "Run an algorithm and keep every step.",
    "Info": "Help and bot status.",
}
CATEGORY_ORDER = ("Visualize", "Info")

ENTRIES: dict[str, HelpEntry] = {
    "visualize": HelpEntry(
        command="visualize",
        category="Visualize",
        summary=(
            "Animate an algorithm on your input (or random data). The bot opens a thread "
            "with the animation, a numbered step log and a summary."
        ),
        examples=(
            "/visualize algo:Bubble Sort data:5,2,9,1",
            "/visualize algo:Merge Sort size:12",
            "/visualize algo:Binary Search data:3,9,14,21 target:14",
            "/visualize algo:BFS data:1-2,1-3,2-4 start:1",
            "/visualize algo:In-order data:50,30,70,20,40",
        ),
        since="1.0.0",
        notes=(
            "Leave `data` empty (or type `random`) for random input; `size` sets how many.",
            "Sorting and search: `data` is a list of numbers. Binary search sorts it first.",
            "Search: if you skip `target`, the bot picks one for you.",
            "Graphs: `data` is a list of edges like `1-2,1-3`; `start` defaults to the smallest node.",
            "Trees: `data` is the insert order of a binary search tree; duplicates are skipped.",
        ),
        limits=(
            f"Sort/search: {config.MIN_ITEMS}-{config.MAX_ITEMS} items, values {config.MIN_VALUE}-{config.MAX_VALUE}",
            f"Trees: up to {config.MAX_TREE_NODES} distinct values",
            f"Graphs: nodes 1-{config.MAX_GRAPH_NODES}, up to {config.MAX_GRAPH_EDGES} edges",
            f"Cooldown: {config.RUN_COOLDOWN_S:.0f} s per user",
        ),
        see_also=("step", "help topic:algorithms", "help topic:colors"),
    ),
    "step": HelpEntry(
        command="step",
        category="Visualize",
        summary="Show one step of a run as an image. Use it inside the thread that /visualize created.",
        examples=("/step n:3",),
        since="1.0.0",
        notes=(
            "Step numbers appear in the step log (for example `Step 12 | ...`).",
            "Any step number works, not only the ones in the log.",
            "It rebuilds the run from the thread's first message, so it works as long as that message exists.",
        ),
        limits=(f"Cooldown: {config.STEP_COOLDOWN_S:.0f} s per user",),
        see_also=("visualize",),
    ),
    "help": HelpEntry(
        command="help",
        category="Info",
        summary="Explain the commands, their options and give examples.",
        examples=(
            "/help",
            "/help command:visualize",
            "/help topic:algorithms",
        ),
        since="2.0.0",
        notes=(
            "Answers are private by default; set `public` to show them to the channel.",
            "`*` marks a required option. Options in `[ ]` are optional.",
        ),
        limits=(f"Cooldown: {config.HELP_COOLDOWN_S:.0f} s per user",),
        see_also=("about", "stats"),
    ),
    "about": HelpEntry(
        command="about",
        category="Info",
        summary="What this bot is, its version, uptime and links.",
        examples=("/about",),
        since="2.0.0",
        limits=(f"Cooldown: {config.INFO_COOLDOWN_S:.0f} s per user",),
        see_also=("stats", "help"),
    ),
    "stats": HelpEntry(
        command="stats",
        category="Info",
        summary="Bot activity: runs, most used algorithms and commands.",
        examples=("/stats",),
        since="2.0.0",
        notes=(
            "Only counts are stored. No user names, messages or inputs.",
            "The bot owner also sees health details (memory, render time, errors).",
        ),
        limits=(f"Cooldown: {config.INFO_COOLDOWN_S:.0f} s per user",),
        see_also=("about",),
    ),
}

# (key, label, short description) for the topic pages; order = menu order.
TOPICS: tuple[tuple[str, str, str], ...] = (
    ("algorithms", "Algorithms", "Every algorithm with its complexity"),
    ("limits", "Limits", "Input sizes, cooldowns and queue"),
    ("colors", "Color legend", "What each color means in the animations"),
    ("faq", "FAQ", "Common questions and fixes"),
)

FAQ: tuple[tuple[str, str], ...] = (
    (
        "How do I look at a step again later?",
        "Open the run's thread and use `/step n:<number>`. Step numbers are in the step log.",
    ),
    (
        "Why was my list sorted before binary search?",
        "Binary search only works on sorted data, so the bot sorts it first and tells you.",
    ),
    (
        "What does `size` do?",
        "It only applies to random data (leave `data` empty). It sets how many items or nodes to generate.",
    ),
    (
        "The bot says it is busy.",
        f"One animation renders at a time and {config.MAX_WAITING} can wait. Try again in a few seconds.",
    ),
    (
        "It says it can't create a thread.",
        "The bot needs **Create Public Threads** in that channel. Ask a server admin to allow it.",
    ),
    (
        "`/step` says it can't find run info.",
        "Use it inside a thread made by `/visualize`. If the thread's first message was deleted the run can't be rebuilt.",
    ),
)
