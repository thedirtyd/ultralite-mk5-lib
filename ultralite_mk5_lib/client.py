"""Persistent WebSocket client for MOTU UltraLite mk5 / Gen5 devices."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import websocket

from ultralite_mk5_lib.buses import solo_bus_mute_indices
from ultralite_mk5_lib.entities import resolve_stereo_input_gain_ich
from ultralite_mk5_lib.mutes import (
    MuteCommand,
    prepare_mute_command,
    resolve_bus_mute_entity,
    resolve_solo_bus_entity,
)
from ultralite_mk5_lib.protocol import (
    VALID_SAMPLE_RATES,
    OPTICAL_INPUT_MODE_INDEX,
    OPTICAL_OUTPUT_MODE_INDEX,
    build_ws_url,
    make_bus_mute_frame,
    make_mix_stereo_frame,
    make_optical_mode_frame,
    make_sample_rate_frame,
    parse_optical_mode,
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
        auto_reconnect: bool = True,
        reconnect_interval: float = 1.0,
        on_connection_lost: Callable[[], None] | None = None,
        on_connection_restored: Callable[[], None] | None = None,
        on_message: Callable[[bytes], None] | None = None,
    ) -> None:
        self._target = target
        self._port = port
        self._serial = serial
        self._timeout = timeout
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self._on_connection_lost = on_connection_lost
        self._on_connection_restored = on_connection_restored
        self._on_message = on_message
        self.state = DeviceState()
        self._url = build_ws_url(target, port, serial)
        self._ws: websocket.WebSocket | None = None
        self._stop = threading.Event()
        self._connected_event = threading.Event()
        self._connect_lock = threading.Lock()
        self._loss_notified = False
        self._rx_thread: threading.Thread | None = None
        self._reconnect_thread: threading.Thread | None = None

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

        self._stop.clear()
        if self.auto_reconnect:
            self._ensure_reconnect_thread()
            self.wait_until_connected()
            return

        with self._connect_lock:
            self._open_socket()
        self._notify_connection_restored()

    def close(self) -> None:
        """Close WebSocket and stop the receive and reconnect threads."""
        self._stop.set()
        self._connected_event.set()

        with self._connect_lock:
            self._teardown_socket()

        if self._reconnect_thread is not None:
            self._reconnect_thread.join(timeout=2.0)
            self._reconnect_thread = None

    def wait_until_connected(self, timeout: float | None = None) -> bool:
        """Block until connected. Returns False on timeout or after close()."""
        if self.connected:
            return True
        if self._stop.is_set():
            return False
        if self.auto_reconnect:
            self._ensure_reconnect_thread()

        if timeout is None:
            while not self._stop.is_set():
                if self._connected_event.wait(timeout=0.5):
                    return self.connected
            return False

        if not self._connected_event.wait(timeout=timeout):
            return False
        return self.connected

    def set_sample_rate(self, rate: int) -> None:
        """Set device sample rate in Hz."""
        if rate not in VALID_SAMPLE_RATES:
            raise ValueError(
                f"rate must be one of {VALID_SAMPLE_RATES}, got {rate}"
            )

        ws = self._require_connection()
        frame = make_sample_rate_frame(rate)
        ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)

    def set_optical_input_mode(self, mode: str) -> None:
        """Set optical input mode to adat or toslink (kOpticalMode index 0)."""
        wire = parse_optical_mode(mode)
        ws = self._require_connection()
        ws.send(
            make_optical_mode_frame(OPTICAL_INPUT_MODE_INDEX, wire),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )
        self.state.set_prop_local("optical_mode", OPTICAL_INPUT_MODE_INDEX, wire)

    def set_optical_output_mode(self, mode: str) -> None:
        """Set optical output mode to adat or toslink (kOpticalMode index 1)."""
        wire = parse_optical_mode(mode)
        ws = self._require_connection()
        ws.send(
            make_optical_mode_frame(OPTICAL_OUTPUT_MODE_INDEX, wire),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )
        self.state.set_prop_local("optical_mode", OPTICAL_OUTPUT_MODE_INDEX, wire)

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

    def set_channel_stereo_mode(self, key: str, mode: str) -> None:
        """
        Link or unlink an input channel pair (kiMixStereo).

        ``key`` may be a ``MIXINPUT_*`` entity key, or any ``MIXBUSFADER_*``
        crosspoint key for the L or R channel of the pair. Stereo mode applies
        globally across all mix buses.
        ``mode`` is ``stereo`` or ``mono``.
        """
        normalized = key.strip().upper()
        gain_ich = resolve_stereo_input_gain_ich(normalized)

        mode_lower = mode.strip().lower()
        if mode_lower not in ("stereo", "mono"):
            raise ValueError(f"mode must be 'stereo' or 'mono', got {mode!r}")

        stereo_left_ich = gain_ich & 0xFE
        stereo = mode_lower == "stereo"
        ws = self._require_connection()
        ws.send(
            make_mix_stereo_frame(stereo_left_ich, stereo),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )
        self.state.set_prop_local("mix_stereo", stereo_left_ich, 1 if stereo else 0)

    def wait(self) -> None:
        """Block while the connection is open."""
        while self.connected and not self._stop.is_set():
            time.sleep(0.1)

    def snapshot_json(self, *, indent: int | None = 2) -> str:
        """Return the current get-state report as a JSON string."""
        return self.state.snapshot_json(indent=indent)

    def _require_connection(self) -> websocket.WebSocket:
        if not self.connected:
            if self.auto_reconnect:
                if not self.wait_until_connected():
                    raise NotConnectedError("Not connected")
            else:
                raise NotConnectedError("Not connected; call connect() first")
        assert self._ws is not None
        return self._ws

    def _open_socket(self) -> None:
        ws = websocket.create_connection(self._url, timeout=self._timeout)
        self._ws = ws
        self._rx_thread = threading.Thread(
            target=self._recv_loop,
            name="ultralite-mk5-rx",
            daemon=True,
        )
        self._rx_thread.start()

    def _teardown_socket(self, *, from_rx_thread: bool = False) -> None:
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

        if from_rx_thread:
            self._rx_thread = None
            return

        if self._rx_thread is not None:
            if self._rx_thread.is_alive():
                self._rx_thread.join(timeout=2.0)
            self._rx_thread = None

    def _notify_connection_lost(self) -> None:
        if self._loss_notified:
            return
        self._loss_notified = True
        self._connected_event.clear()
        if self._on_connection_lost is not None:
            try:
                self._on_connection_lost()
            except Exception:
                pass

    def _notify_connection_restored(self) -> None:
        self._connected_event.set()
        if not self._loss_notified:
            return
        self._loss_notified = False
        if self._on_connection_restored is not None:
            try:
                self._on_connection_restored()
            except Exception:
                pass

    def _ensure_reconnect_thread(self) -> None:
        if self._reconnect_thread is not None and self._reconnect_thread.is_alive():
            return
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            name="ultralite-mk5-reconnect",
            daemon=True,
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        while not self._stop.is_set():
            if self.connected:
                return

            with self._connect_lock:
                if self._stop.is_set() or self.connected:
                    return
                try:
                    self._open_socket()
                except Exception:
                    pass
                else:
                    self._notify_connection_restored()
                    return

            time.sleep(self.reconnect_interval)

    def _handle_disconnect(self) -> None:
        with self._connect_lock:
            if self._ws is None:
                if self.auto_reconnect and not self._stop.is_set():
                    self._ensure_reconnect_thread()
                return

            self._teardown_socket(from_rx_thread=True)
            self.state.reset()
            self._notify_connection_lost()
            if self.auto_reconnect and not self._stop.is_set():
                self._ensure_reconnect_thread()

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

        if not self._stop.is_set():
            self._handle_disconnect()

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
