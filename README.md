# DSA Visualizer Bot

Discord bot that animates 14 algorithms and keeps **every step in a thread** so you can refer back to it later.

| Category | Algorithms |
|---|---|
| Sorting | bubble, selection, insertion, quick, heap, merge, radix |
| Searching | linear, binary |
| Graph traversal | BFS, DFS |
| Tree traversal | pre-order, in-order, post-order |

## Commands

| Command | What it does |
|---|---|
| `/visualize algo [data] [size] [target] [start]` | Runs the algorithm, creates a thread, posts the GIF, a numbered key-step log and a summary |
| `/step n` | Use **inside a run's thread**: renders step `n` as an image |

Input is a **list** or **random**:

```
/visualize algo:Bubble Sort data:5,2,9,1
/visualize algo:Merge Sort size:12                (random)
/visualize algo:Binary Search data:3,9,14 target:9
/visualize algo:BFS data:1-2,1-3,2-4 start:1      (edges)
/visualize algo:In-order data:50,30,70,20,40      (BST insert order)
```

## How it works

```
cogs/ (Discord)  ->  core/ (spec, registry, runner)  ->  algos/ (pure generators)
                                    |
                               render/ (Pillow) -> GIF / PNG
```

* **Algorithms are generators** that yield immutable step objects (`core/steps.py`). They know nothing about Discord or drawing.
* **Three renderers**: bars (sorting), cells (searching), node graph (graph and tree traversal).
* **No database.** The thread's first message holds one machine-readable line, e.g. `` `v=1 | algo=merge | data=5,2,9,1 | target=- | start=-` ``. `/step` re-reads it, re-runs the algorithm (deterministic) and renders the step. Thread id equals that message's id.
* **Stability**: input caps, step cap, frame cap, GIF size fallback, one render at a time with a short queue, per-user cooldowns, render timeout, global error handler, no privileged intents, no caches.

## Setup (local or Termux)

Needs Python 3.10+.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # put your bot token in DISCORD_TOKEN
SYNC_COMMANDS=guild DEV_GUILD_ID=<your test server id> python main.py
```

Termux tip: `pkg install python python-pillow` first, then `pip install discord.py`.

### Discord Developer Portal

1. Create an application, add a **Bot**, copy the token. **Leave all privileged intents OFF.**
2. Invite with this URL (replace `YOUR_APP_ID`):

```
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot%20applications.commands&permissions=309237746688
```

The permission number covers: View Channel, Send Messages, Read Message History, Attach Files, Create Public Threads, Send Messages in Threads.

## Deploy on bot-hosting.net

1. Put the code in a **private** GitHub repo (never commit `.env`).
2. Create a Python deployment from that repo. Start command: `python main.py`.
3. Add environment variables: `DISCORD_TOKEN` (secret) and `SYNC_COMMANDS=global`.
4. After the first successful start (log says "Synced 2 command(s)"), change `SYNC_COMMANDS` to `none`.
5. **Renew the free plan every 4 days** from the panel (set a phone reminder). If it expires the bot goes offline.
6. Run `python scripts/bench.py` in the host console. If the slowest run is over half of `RENDER_TIMEOUT_S`, lower `MAX_ITEMS` / `MAX_FRAMES` in `config.py`.

## Limits (all in `config.py`)

| Item | Limit |
|---|---|
| Sort/search items | 2-20, values 1-99 |
| Tree nodes | up to 15 (duplicates skipped) |
| Graph | up to 10 nodes, 15 edges |
| GIF | up to 120 frames, under 8 MB (shrinks, then key steps only) |
| `/visualize` cooldown | 20 s per user |
| Render queue | 1 running + 3 waiting |

## Add an algorithm

1. Write a generator in `algos/` that yields `BarStep` / `CellStep` / `GraphStep` (tuples only, first and last step `is_key=True`).
2. Decorate it: `@algo("shell", "Shell Sort", "Sorting", "bars")`.
3. Add a test case. It appears in the slash-command choices automatically.

## Quality checks

```bash
pytest                    # algorithms vs reference implementations, parser, renderer, gate, Discord layer (mocked)
ruff check . && ruff format --check .
python scripts/bench.py   # worst-case time and memory on this machine
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Slash commands missing | Run once with `SYNC_COMMANDS=global` (can take a few minutes to appear) |
| "I can't create threads here" | Give the bot **Create Public Threads** in that channel |
| `/step` says it can't read the first message | Give the bot **Read Message History** |
| "I'm busy" | Queue is full; try again in a few seconds |
| Bot offline on the free host | Plan expired; renew in the panel |
