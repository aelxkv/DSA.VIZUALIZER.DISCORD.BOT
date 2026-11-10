"""Central configuration: every limit and tunable lives here.

Nothing in this module touches Discord or the filesystem, so it is safe to
import from anywhere (including tests and the benchmark script).
"""

from __future__ import annotations

import os

# --- Input limits ---------------------------------------------------------
MIN_ITEMS = 2
MAX_ITEMS = 20  # sorting / searching
MAX_TREE_NODES = 15
MIN_GRAPH_NODES = 2
MAX_GRAPH_NODES = 10
MAX_GRAPH_EDGES = 15
MIN_VALUE = 1
MAX_VALUE = 99
MAX_DATA_CHARS = 200  # raw length of the `data` option, checked before parsing

DEFAULT_SIZE = 10
DEFAULT_TREE_SIZE = 7
DEFAULT_GRAPH_SIZE = 6

# --- Engine limits --------------------------------------------------------
MAX_STEPS = 2000  # hard stop for runaway generators
MAX_FRAMES = 120  # frames in one GIF (non-key steps are dropped first)

# --- Rendering ------------------------------------------------------------
FRAME_WIDTH = 480
FRAME_HEIGHT = 270
GIF_COLORS = 64
FRAME_MS = 400
LAST_FRAME_MS = 1500
GIF_HARD_BYTES = 8 * 1024 * 1024  # stay well below Discord's upload limit
SHRINK_SCALE = 0.7  # second attempt if the GIF is too large
PNG_SCALE = 2  # /step images are drawn larger than GIF frames

# --- Load control ---------------------------------------------------------
RENDER_TIMEOUT_S = 20.0
RUN_COOLDOWN_S = 20.0
STEP_COOLDOWN_S = 5.0
MAX_WAITING = 3  # runs allowed to queue behind the one being rendered

# --- Discord output -------------------------------------------------------
LOG_CHUNK_CHARS = 1900  # Discord's hard limit is 2000
MAX_LOG_MESSAGES = 5
LOG_LINE_MAX = 150
ARCHIVE_MINUTES = 10080  # 7 days (falls back to 1 day if refused)
ARCHIVE_FALLBACK_MINUTES = 1440

# --- Run-info line --------------------------------------------------------
RUN_LINE_VERSION = 1


def get_token() -> str:
    """Return the bot token from the environment or raise a clear error."""
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Put it in the host's environment "
            "variables (or a local .env file) - never in the code."
        )
    return token
