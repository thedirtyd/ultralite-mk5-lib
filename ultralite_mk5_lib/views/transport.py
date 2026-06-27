"""Shared transport helpers for domain views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import websocket

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5


def send_binary(device: UltraLiteMk5, frame: bytes) -> None:
    ws = device._require_connection()
    ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)


def send_prop_local(
    device: UltraLiteMk5,
    prop_key: str,
    index: int,
    value: object,
) -> None:
    device.state.set_prop_local(prop_key, index, value)


def send_bus_mute_local(device: UltraLiteMk5, index: int, muted: bool) -> None:
    device.state.set_bus_mute_local(index, muted)
