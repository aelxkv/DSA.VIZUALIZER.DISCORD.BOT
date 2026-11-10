"""Exception types shared across layers."""

from __future__ import annotations


class BotError(Exception):
    """Base class for every error this project raises on purpose."""


class UserInputError(BotError):
    """The user supplied something invalid. The message is safe to show them."""


class AlgoLimitError(BotError):
    """An algorithm produced more steps than allowed (should never happen)."""


class RenderError(BotError):
    """Rendering failed or the result could not be made small enough."""
