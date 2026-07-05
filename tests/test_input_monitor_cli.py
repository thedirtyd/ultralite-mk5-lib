"""Tests for set-input-monitor CLI routing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ultralite_mk5_lib.commands import apply_set_input_monitor
from ultralite_mk5_lib.input_monitor import INPUT_MONITOR_PHONES_OCH
from ultralite_mk5_lib.mix_buses import mix_fader_index
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.views.transport import send_prop_local


class ApplySetInputMonitorTests(unittest.TestCase):
    def test_toggle_off_to_on(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        flat = mix_fader_index(0, INPUT_MONITOR_PHONES_OCH)
        send_prop_local(device, "mix_fader", flat, 0.0)

        with patch("ultralite_mk5_lib.input_monitor.set_input_monitor") as mock_set:
            def _enable(device, gain_ich, gain_och, *, enabled):
                if enabled:
                    send_prop_local(device, "mix_fader", flat, 1.0)
                    send_prop_local(device, "mix_mute", flat, 0)
                    send_prop_local(device, "mix_pan", flat, 0.5)
                    send_prop_local(device, "mix_stereo", 0, 0)

            mock_set.side_effect = _enable
            state = apply_set_input_monitor(device, "phones", 0, "toggle")

        mock_set.assert_called_once_with(
            device, 0, INPUT_MONITOR_PHONES_OCH, enabled=True
        )
        self.assertEqual(state, "on")

    def test_toggle_on_to_off(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        flat = mix_fader_index(0, INPUT_MONITOR_PHONES_OCH)
        send_prop_local(device, "mix_fader", flat, 1.0)
        send_prop_local(device, "mix_mute", flat, 0)
        send_prop_local(device, "mix_pan", flat, 0.5)
        send_prop_local(device, "mix_stereo", 0, 0)

        with patch("ultralite_mk5_lib.input_monitor.set_input_monitor") as mock_set:
            def _disable(device, gain_ich, gain_och, *, enabled):
                if not enabled:
                    send_prop_local(device, "mix_fader", flat, 0.0)

            mock_set.side_effect = _disable
            state = apply_set_input_monitor(device, "phones", 0, "toggle")

        mock_set.assert_called_once_with(
            device, 0, INPUT_MONITOR_PHONES_OCH, enabled=False
        )
        self.assertEqual(state, "off")


if __name__ == "__main__":
    unittest.main()
