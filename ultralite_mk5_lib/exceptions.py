"""Library exceptions."""

from __future__ import annotations


class UltraLiteMk5Error(Exception):
    """Base error for ultralite_mk5_lib."""


class PasswordRequiredError(UltraLiteMk5Error):
    """Device password protection is enabled; auth is not implemented."""


class NotConnectedError(UltraLiteMk5Error):
    """Operation requires an open WebSocket connection."""
