"""Persistent WebSocket client for MOTU UltraLite mk5 / Gen5 devices."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import websocket

_LOGGER = logging.getLogger(__name__)

# CueMix closes the socket after ~2s without inbound messages (datastore.js).
DEFAULT_RECEIVE_IDLE_TIMEOUT = 2.0

from ultralite_mk5_lib.exceptions import NotConnectedError
from ultralite_mk5_lib.protocol import build_ws_url
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.views.eq import EQView
from ultralite_mk5_lib.views.inputs import InputsView
from ultralite_mk5_lib.layout import LayoutView
from ultralite_mk5_lib.views.meters import MetersView
from ultralite_mk5_lib.views.mix import MixView
from ultralite_mk5_lib.views.outputs import OutputsView
from ultralite_mk5_lib.views.settings import SettingsView

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
        receive_idle_timeout: float = DEFAULT_RECEIVE_IDLE_TIMEOUT,
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
        self.receive_idle_timeout = receive_idle_timeout
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
        self._last_recv_monotonic = 0.0
        self._mix = MixView(self)
        self._inputs = InputsView(self)
        self._outputs = OutputsView(self)
        self._meters = MetersView(self)
        self._settings = SettingsView(self)
        self._layout = LayoutView(self)
        self._eq = EQView(self)

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

    def start_background_reconnect(self) -> None:
        """Start the reconnect thread without blocking."""
        self._stop.clear()
        if self.auto_reconnect:
            self._ensure_reconnect_thread()

    @property
    def mix(self) -> MixView:
        return self._mix

    @property
    def inputs(self) -> InputsView:
        return self._inputs

    @property
    def outputs(self) -> OutputsView:
        return self._outputs

    @property
    def meters(self) -> MetersView:
        return self._meters

    @property
    def settings(self) -> SettingsView:
        return self._settings

    @property
    def layout(self) -> LayoutView:
        return self._layout

    @property
    def eq(self) -> EQView:
        return self._eq

    def wait_ready(self, timeout: float | None = None) -> bool:
        """Block until core mix/trim props needed for get-state have arrived."""
        wait = self._timeout if timeout is None else timeout
        return self.state.wait_until_ready(wait)

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
        self._last_recv_monotonic = time.monotonic()
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
                _LOGGER.exception("on_connection_lost callback failed")

    def _notify_connection_restored(self) -> None:
        self._connected_event.set()
        if not self._loss_notified:
            return
        self._loss_notified = False
        if self._on_connection_restored is not None:
            try:
                self._on_connection_restored()
            except Exception:
                _LOGGER.exception("on_connection_restored callback failed")

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
                if (
                    self.receive_idle_timeout > 0
                    and time.monotonic() - self._last_recv_monotonic
                    > self.receive_idle_timeout
                ):
                    _LOGGER.warning(
                        "No inbound data for %.1fs; reconnecting",
                        self.receive_idle_timeout,
                    )
                    break
                continue
            except Exception:
                break

            self._last_recv_monotonic = time.monotonic()

            if self._on_message is not None:
                try:
                    self._on_message(data)
                except Exception:
                    _LOGGER.exception("on_message callback failed")

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
