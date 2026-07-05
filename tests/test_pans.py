"""Tests for pan command encoding."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ultralite_mk5_lib.commands import apply_set_pan
from ultralite_mk5_lib.mix_buses import mix_fader_index
from ultralite_mk5_lib.pans import (
    PAN_CENTER,
    PAN_MAX,
    PAN_MIN,
    parse_pan_value,
    prepare_pan_command,
    resolve_mix_pan_entity,
    validate_mix_pan,
)
from ultralite_mk5_lib.protocol import K_MIX_PAN_ID, make_mix_pan_frame
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.views.mix import CrosspointFader
from ultralite_mk5_lib.views.transport import send_prop_local
from tests.helpers import assert_frame_header


class ParsePanValueTests(unittest.TestCase):
    def test_aliases(self) -> None:
        self.assertEqual(parse_pan_value("center"), PAN_CENTER)
        self.assertEqual(parse_pan_value("L"), PAN_MIN)
        self.assertEqual(parse_pan_value("right"), PAN_MAX)

    def test_numeric(self) -> None:
        self.assertEqual(parse_pan_value("0.25"), 0.25)

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_pan_value("maybe")


class ValidateMixPanTests(unittest.TestCase):
    def test_range(self) -> None:
        self.assertEqual(validate_mix_pan(0.0), 0.0)
        self.assertEqual(validate_mix_pan(1.0), 1.0)

    def test_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_mix_pan(1.5)


class PreparePanCommandTests(unittest.TestCase):
    def test_mix_crosspoint_pan(self) -> None:
        cmd = prepare_pan_command("MIXBUSFADER_PHONES_MICIN01", "center")
        self.assertEqual(cmd.prop_key, "mix_pan")
        self.assertEqual(cmd.pan, PAN_CENTER)
        assert_frame_header(cmd.frame, K_MIX_PAN_ID, cmd.index)

    def test_bus_out_key_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prepare_pan_command("MIXBUSFADER_MAIN0102_OUT", "0.5")


class ResolveMixPanEntityTests(unittest.TestCase):
    def test_crosspoint(self) -> None:
        key, index = resolve_mix_pan_entity("MIXBUSFADER_MAIN0102_LINEIN03")
        self.assertEqual(key, "MIXBUSFADER_MAIN0102_LINEIN03")
        self.assertEqual(index, mix_fader_index(2, 0))


class CrosspointFaderPanTests(unittest.TestCase):
    def test_pan_getter(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        fader = CrosspointFader(device, gain_ich=2, gain_och=0)
        flat = fader.flat_index
        send_prop_local(device, "mix_pan", flat, 0.25)
        self.assertEqual(fader.pan, 0.25)

    def test_set_pan_rejects_stereo_linked(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        send_prop_local(device, "mix_stereo", 0, 1)
        fader = CrosspointFader(device, gain_ich=0, gain_och=0)
        with self.assertRaises(ValueError):
            fader.set_pan(PAN_CENTER)

    def test_set_pan_writes_when_mono(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        fader = CrosspointFader(device, gain_ich=0, gain_och=0)
        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            fader.set_pan(0.75)
        mock_send.assert_called_once()
        self.assertEqual(fader.pan, 0.75)


class ApplyPanCommandTests(unittest.TestCase):
    def test_apply_set_pan_routes_through_fader(self) -> None:
        device = MagicMock()
        fader = MagicMock()
        device.mix.fader_by_key.return_value = fader
        cmd = apply_set_pan(device, "MIXBUSFADER_MAIN0102_LINEIN03", "L")
        device.mix.fader_by_key.assert_called_once_with("MIXBUSFADER_MAIN0102_LINEIN03")
        fader.set_pan.assert_called_once_with(PAN_MIN)
        self.assertEqual(cmd.pan, PAN_MIN)


class MakeMixPanFrameTests(unittest.TestCase):
    def test_frame_header(self) -> None:
        frame = make_mix_pan_frame(320, 0.5)
        assert_frame_header(frame, K_MIX_PAN_ID, 320)


if __name__ == "__main__":
    unittest.main()
