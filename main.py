"""Entry point: `python main.py`."""

from __future__ import annotations

import logging

import config
from bot import DsaBot


def main() -> None:
    try:  # optional: local .env support (not needed on the host)
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    token = config.get_token()
    DsaBot().run(token, log_handler=None)


if __name__ == "__main__":
    main()
