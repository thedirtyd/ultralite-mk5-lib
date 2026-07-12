"""Tests for WebSocket client reconnect and receive-idle handling."""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

import websocket

from ultralite_mk5_lib.client import UltraLiteMk5
from ultralite_mk5_lib.protocol import K_SAMPLE_RATE_ID
from tests.helpers import inbound_int32_frame


class MockWebSocket:
    """Minimal websocket stand-in for recv-loop tests."""

    def __init__(
        self,
        *,
        recv_results: list[object],
        timeout_exception: type[Exception] | None = None,
    ) -> None:
        self.connected = True
        self._recv_results = list(recv_results)
        self._timeout_exception = timeout_exception or websocket.WebSocketTimeoutException
        self._timeout = 0.5
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self._timeout = timeout

    def recv(self) -> bytes:
        if not self._recv_results:
            raise self._timeout_exception()
        result = self._recv_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self) -> None:
        self.connected = False
        self.closed = True


class ReceiveIdleTests(unittest.TestCase):
    def test_recv_idle_triggers_disconnect_and_reset(self) -> None:
        mock_ws = MockWebSocket(recv_results=[])
        lost = threading.Event()
        restored = threading.Event()

        with patch(
            "ultralite_mk5_lib.client.websocket.create_connection",
            return_value=mock_ws,
        ):
            device = UltraLiteMk5(
                "127.0.0.1",
                connect=False,
                auto_reconnect=False,
                receive_idle_timeout=0.2,
                on_connection_lost=lost.set,
                on_connection_restored=restored.set,
            )
            device._open_socket()
            device.state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))

            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if lost.is_set() and not device.connected:
                    break
                time.sleep(0.05)

        self.assertTrue(lost.is_set())
        self.assertFalse(device.connected)
        self.assertEqual(device.state.props, {})
        self.assertFalse(restored.is_set())

    def test_inbound_frames_refresh_idle_timer(self) -> None:
        mock_ws = MockWebSocket(
            recv_results=[
                inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000),
                websocket.WebSocketTimeoutException(),
                websocket.WebSocketTimeoutException(),
            ]
        )
        lost = threading.Event()

        with patch(
            "ultralite_mk5_lib.client.websocket.create_connection",
            return_value=mock_ws,
        ):
            device = UltraLiteMk5(
                "127.0.0.1",
                connect=False,
                auto_reconnect=False,
                receive_idle_timeout=2.0,
                on_connection_lost=lost.set,
            )
            device._open_socket()

            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if device.state.frame_count >= 1:
                    break
                time.sleep(0.02)

        self.assertEqual(device.state.frame_count, 1)
        self.assertFalse(lost.is_set())
        self.assertTrue(device.connected)
        device.close()

    def test_set_prop_local_updates_state_without_inbound_recv(self) -> None:
        mock_ws = MockWebSocket(recv_results=[])
        observer_calls: list[str] = []

        with patch(
            "ultralite_mk5_lib.client.websocket.create_connection",
            return_value=mock_ws,
        ):
            device = UltraLiteMk5(
                "127.0.0.1",
                connect=False,
                auto_reconnect=False,
                receive_idle_timeout=0.0,
            )
            device._open_socket()
            device.state.add_observer(
                lambda: observer_calls.append(device.state.last_notify_kind)
            )
            device.state.set_prop_local("sample_rate", 0, 44100)

        self.assertEqual(observer_calls, ["local"])
        self.assertEqual(device.state.props["sample_rate"][0], 44100)
        device.close()


if __name__ == "__main__":
    unittest.main()
