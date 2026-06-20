"""Persistent WebSocket client for MOTU UltraLite mk5 / Gen5 devices."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import websocket

from ultralite_mk5_lib.buses import solo_bus_mute_indices
from ultralite_mk5_lib.exceptions import NotConnectedError
from ultralite_mk5_lib.levels import LevelCommand, prepare_level_command
from ultralite_mk5_lib.mutes import (
    MuteCommand,
    prepare_mute_command,
    resolve_bus_mute_entity,
    resolve_solo_bus_entity,
)
from ultralite_mk5_lib.protocol import (
    VALID_SAMPLE_RATES,
    build_ws_url,
    make_bus_mute_frame,
    make_sample_rate_frame,
)
from ultralite_mk5_lib.state import DeviceState

if TYPE_CHECKING:
    from collections.abc import Callable


class UltraLiteMk5:
    """
    Persistent WebSocket client for a MOTU Gen5 device.

    Assumes device password protection is disabled (fffe 0002 00 on connect).
    """

    def __init__(
        self,
        target: str,
        *,
        port: int | None = None,
        serial: str | None = None,
        timeout: float = 3.0,
        connect: bool = True,
        on_message: Callable[[bytes], None] | None = None,
    ) -> None:
        self._target = target
        self._port = port
        self._serial = serial
        self._timeout = timeout
        self._on_message = on_message
        self.state = DeviceState()
        self._url = build_ws_url(target, port, serial)
        self._ws: websocket.WebSocket | None = None
        self._stop = threading.Event()
        self._rx_thread: threading.Thread | None = None

        if connect:
            self.connect()

    @property
    def url(self) -> str:
        return self._url

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.connected

    @property
    def timeout(self) -> float:
        return self._timeout

    def connect(self) -> None:
        """Open WebSocket and start the background receive loop."""
        if self.connected:
            return

        ws = websocket.create_connection(self._url, timeout=self._timeout)
        self._ws = ws
        self._stop.clear()
        self._rx_thread = threading.Thread(
            target=self._recv_loop,
            name="ultralite-mk5-rx",
            daemon=True,
        )
        self._rx_thread.start()

    def close(self) -> None:
        """Close WebSocket and stop the receive thread."""
        self._stop.set()
        if self._rx_thread is not None:
            self._rx_thread.join(timeout=2.0)
            self._rx_thread = None

        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None

    def set_sample_rate(self, rate: int) -> None:
        """Set device sample rate in Hz."""
        if rate not in VALID_SAMPLE_RATES:
            raise ValueError(
                f"rate must be one of {VALID_SAMPLE_RATES}, got {rate}"
            )

        ws = self._require_connection()
        frame = make_sample_rate_frame(rate)
        ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)

    def set_bus_mute(self, key: str, muted: bool) -> None:
        """Mute or unmute a mix output bus (koBusMute) by MIXBUSFADER_*_OUT entity key."""
        normalized, _ = resolve_bus_mute_entity(key)
        self.set_mute(normalized, "mute" if muted else "unmute")

    def set_mute(self, key: str, value: str | None = None) -> MuteCommand:
        """
        Set mute for a settable entity key.

        ``value`` is mute/on/true/1 or unmute/off/false/0 (default: mute).
        """
        command = prepare_mute_command(key, value)
        ws = self._require_connection()
        ws.send(command.frame, opcode=websocket.ABNF.OPCODE_BINARY)
        wire_value = 1 if command.muted else 0
        if command.prop_key == "bus_mute":
            self.state.set_bus_mute_local(command.index, command.muted)
        else:
            self.state.set_prop_local(
                command.prop_key,
                command.index,
                wire_value,
            )
        return command

    def solo_output_bus(self, key: str) -> None:
        """
        Solo one output bus: unmute it and mute all others.

        ``key`` is a MIXBUSFADER_*_OUT entity key. Reverb mute state is not
        changed and reverb is not a valid target.
        """
        _, active_index = resolve_solo_bus_entity(key)
        ws = self._require_connection()
        pairs = solo_bus_mute_indices(active_index)
        payload = b"".join(
            make_bus_mute_frame(index, muted)
            for index, muted in pairs
        )
        ws.send(payload, opcode=websocket.ABNF.OPCODE_BINARY)
        for index, muted in pairs:
            self.state.set_bus_mute_local(index, muted)

    def set_level(self, key: str, level: str) -> LevelCommand:
        """
        Set level for a settable entity key.

        ``level`` is a CLI-style token: plain number (linear gain), ``-6db``,
        or ``-inf`` / ``-infdb``.
        """
        command = prepare_level_command(key, level)
        ws = self._require_connection()
        ws.send(command.frame, opcode=websocket.ABNF.OPCODE_BINARY)
        self.state.set_prop_local(
            command.prop_key,
            command.index,
            command.wire_value,
        )
        return command

    def wait(self) -> None:
        """Block while the connection is open."""
        while self.connected and not self._stop.is_set():
            time.sleep(0.1)

    def snapshot_json(self, *, indent: int | None = 2) -> str:
        """Return the current get-state report as a JSON string."""
        return self.state.snapshot_json(indent=indent)

    def _require_connection(self) -> websocket.WebSocket:
        if not self.connected:
            raise NotConnectedError("Not connected; call connect() first")
        assert self._ws is not None
        return self._ws

    def _recv_loop(self) -> None:
        ws = self._ws
        if ws is None:
            return

        while not self._stop.is_set():
            ws.settimeout(0.5)
            try:
                data = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break

            if self._on_message is not None:
                try:
                    self._on_message(data)
                except Exception:
                    pass

            self.state.apply_frame(data)

    def __enter__(self) -> UltraLiteMk5:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
