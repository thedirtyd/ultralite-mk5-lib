"""Tests for input monitor write path."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ultralite_mk5_lib.input_monitor import (
    INPUT_MONITOR_MAIN_OCH,
    set_input_monitor,
)
from ultralite_mk5_lib.mix_buses import mix_fader_index
from ultralite_mk5_lib.pans import PAN_CENTER
from ultralite_mk5_lib.protocol import K_MIX_FADER_ID, K_MIX_PAN_ID, K_MIX_STEREO_ID
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.views.mix import MixView
from ultralite_mk5_lib.views.transport import send_prop_local
from tests.helpers import assert_frame_header


def _make_device() -> MagicMock:
    device = MagicMock()
    device.state = DeviceState()
    device.mix = MixView(device)
    return device


class SetInputMonitorWriteTests(unittest.TestCase):
    def test_enable_linked_preserves_stereo(self) -> None:
        device = _make_device()
        send_prop_local(device, "mix_stereo", 0, 1)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            set_input_monitor(device, 1, INPUT_MONITOR_MAIN_OCH, enabled=True)

        self.assertEqual(device.state.props["mix_stereo"][0], 1)
        stereo_frames = [
            call.args[1]
            for call in mock_send.call_args_list
            if call.args[1][:2] == K_MIX_STEREO_ID.to_bytes(2, "big")
        ]
        self.assertEqual(stereo_frames, [])

    def test_enable_linked_no_pan_frame(self) -> None:
        device = _make_device()
        send_prop_local(device, "mix_stereo", 0, 1)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            set_input_monitor(device, 0, INPUT_MONITOR_MAIN_OCH, enabled=True)

        pan_frames = [
            call.args[1]
            for call in mock_send.call_args_list
            if call.args[1][:2] == K_MIX_PAN_ID.to_bytes(2, "big")
        ]
        self.assertEqual(pan_frames, [])

    def test_enable_linked_writes_both_faders(self) -> None:
        device = _make_device()
        send_prop_local(device, "mix_stereo", 0, 1)
        left_flat = mix_fader_index(0, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            set_input_monitor(device, 1, INPUT_MONITOR_MAIN_OCH, enabled=True)

        fader_frames = [
            call.args[1]
            for call in mock_send.call_args_list
            if call.args[1][:2] == K_MIX_FADER_ID.to_bytes(2, "big")
        ]
        self.assertEqual(len(fader_frames), 2)
        assert_frame_header(fader_frames[0], K_MIX_FADER_ID, left_flat)
        assert_frame_header(fader_frames[1], K_MIX_FADER_ID, right_flat)
        self.assertEqual(device.state.props["mix_fader"][left_flat], 1.0)
        self.assertEqual(device.state.props["mix_fader"][right_flat], 1.0)

    def test_enable_linked_clears_mute_solo_both(self) -> None:
        device = _make_device()
        send_prop_local(device, "mix_stereo", 0, 1)
        left_flat = mix_fader_index(0, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)
        send_prop_local(device, "mix_mute", left_flat, 1)
        send_prop_local(device, "mix_mute", right_flat, 1)
        send_prop_local(device, "mix_solo", left_flat, 1)
        send_prop_local(device, "mix_solo", right_flat, 1)

        with patch("ultralite_mk5_lib.views.mix.send_binary"):
            set_input_monitor(device, 0, INPUT_MONITOR_MAIN_OCH, enabled=True)

        self.assertEqual(device.state.props["mix_mute"][left_flat], 0)
        self.assertEqual(device.state.props["mix_mute"][right_flat], 0)
        self.assertEqual(device.state.props["mix_solo"][left_flat], 0)
        self.assertEqual(device.state.props["mix_solo"][right_flat], 0)

    def test_disable_linked_zeros_both(self) -> None:
        device = _make_device()
        send_prop_local(device, "mix_stereo", 0, 1)
        left_flat = mix_fader_index(0, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)
        send_prop_local(device, "mix_fader", left_flat, 1.0)
        send_prop_local(device, "mix_fader", right_flat, 1.0)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            set_input_monitor(device, 1, INPUT_MONITOR_MAIN_OCH, enabled=False)

        fader_frames = [
            call.args[1]
            for call in mock_send.call_args_list
            if call.args[1][:2] == K_MIX_FADER_ID.to_bytes(2, "big")
        ]
        self.assertEqual(len(fader_frames), 2)
        self.assertEqual(device.state.props["mix_fader"][left_flat], 0.0)
        self.assertEqual(device.state.props["mix_fader"][right_flat], 0.0)

    def test_enable_mono_unlinked_unchanged(self) -> None:
        device = _make_device()
        flat = mix_fader_index(2, INPUT_MONITOR_MAIN_OCH)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            set_input_monitor(device, 2, INPUT_MONITOR_MAIN_OCH, enabled=True)

        pan_frames = [
            call.args[1]
            for call in mock_send.call_args_list
            if call.args[1][:2] == K_MIX_PAN_ID.to_bytes(2, "big")
        ]
        self.assertEqual(len(pan_frames), 1)
        self.assertEqual(device.state.props["mix_pan"][flat], PAN_CENTER)
        self.assertEqual(device.state.props["mix_fader"][flat], 1.0)

    def test_disable_mono_only_touches_requested_channel(self) -> None:
        device = _make_device()
        flat = mix_fader_index(3, INPUT_MONITOR_MAIN_OCH)
        other_flat = mix_fader_index(2, INPUT_MONITOR_MAIN_OCH)
        send_prop_local(device, "mix_fader", flat, 1.0)
        send_prop_local(device, "mix_fader", other_flat, 1.0)

        with patch("ultralite_mk5_lib.views.mix.send_binary"):
            set_input_monitor(device, 3, INPUT_MONITOR_MAIN_OCH, enabled=False)

        self.assertEqual(device.state.props["mix_fader"][flat], 0.0)
        self.assertEqual(device.state.props["mix_fader"][other_flat], 1.0)


if __name__ == "__main__":
    unittest.main()
