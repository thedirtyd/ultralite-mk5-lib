"""Tests for solo command encoding."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES
from ultralite_mk5_lib.commands import apply_clear_mix_solo, apply_set_solo
from ultralite_mk5_lib.enums import Buses
from ultralite_mk5_lib.mix_buses import NUM_MIX_INPUTS, mix_fader_index
from ultralite_mk5_lib.protocol import K_MIX_SOLO_ID
from ultralite_mk5_lib.solos import (
    parse_solo_value,
    prepare_solo_command,
    resolve_clear_mix_solo_entity,
    resolve_mix_solo_entity,
)
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.views.mix import BusView
from tests.helpers import assert_frame_header


class ParseSoloValueTests(unittest.TestCase):
    def test_solo_on(self) -> None:
        self.assertTrue(parse_solo_value("solo"))
        self.assertTrue(parse_solo_value("ON"))

    def test_unsolo(self) -> None:
        self.assertFalse(parse_solo_value("unsolo"))
        self.assertFalse(parse_solo_value("0"))

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_solo_value("maybe")


class PrepareSoloCommandTests(unittest.TestCase):
    def test_mix_crosspoint_solo(self) -> None:
        cmd = prepare_solo_command("MIXBUSFADER_PHONES_MICLINEIN01")
        self.assertEqual(cmd.prop_key, "mix_solo")
        self.assertTrue(cmd.soloed)
        assert_frame_header(cmd.frame, K_MIX_SOLO_ID, cmd.index)

    def test_reverb_crosspoint_solo(self) -> None:
        cmd = prepare_solo_command("MIXBUSFADER_MAIN0102_REVERB", "unsolo")
        self.assertFalse(cmd.soloed)
        assert_frame_header(cmd.frame, K_MIX_SOLO_ID, cmd.index)

    def test_bus_out_key_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prepare_solo_command("MIXBUSFADER_MAIN0102_OUT")


class ResolveClearMixSoloEntityTests(unittest.TestCase):
    def test_main_bus_out(self) -> None:
        key, index = resolve_clear_mix_solo_entity("MIXBUSFADER_MAIN0102_OUT")
        self.assertEqual(key, "MIXBUSFADER_MAIN0102_OUT")
        self.assertEqual(index, 0)

    def test_reverb_bus_out_accepted(self) -> None:
        key, index = resolve_clear_mix_solo_entity("MIXBUSFADER_REVERB_OUT")
        self.assertEqual(key, "MIXBUSFADER_REVERB_OUT")
        self.assertEqual(index, MIX_BUS_MUTE_INDICES["reverb"])

    def test_crosspoint_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_clear_mix_solo_entity("MIXBUSFADER_MAIN0102_LINEIN03")


class ResolveMixSoloEntityTests(unittest.TestCase):
    def test_reverb_crosspoint(self) -> None:
        key, index = resolve_mix_solo_entity("MIXBUSFADER_REVERB_REVERB")
        self.assertEqual(key, "MIXBUSFADER_REVERB_REVERB")
        och = MIX_BUS_MUTE_INDICES["reverb"]
        self.assertEqual(index, mix_fader_index(30, och))


class BusViewClearSolosTests(unittest.TestCase):
    def test_clears_contiguous_bus_slice(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        gain_och = MIX_BUS_MUTE_INDICES["main 1-2"]
        bus = BusView(device, Buses(gain_och))
        start = mix_fader_index(0, gain_och)

        with patch("ultralite_mk5_lib.views.mix.send_binary") as mock_send:
            with patch("ultralite_mk5_lib.views.mix.send_prop_local") as mock_local:
                bus.clear_solos()

        payload = mock_send.call_args[0][1]
        self.assertEqual(len(payload), NUM_MIX_INPUTS * 7)
        for c in range(NUM_MIX_INPUTS):
            assert_frame_header(payload[c * 7 : (c + 1) * 7], K_MIX_SOLO_ID, start + c)
            self.assertEqual(payload[c * 7 + 6], 0)

        local_calls = [
            (args[2], args[3]) for args, _ in mock_local.call_args_list
        ]
        self.assertEqual(len(local_calls), NUM_MIX_INPUTS)
        self.assertEqual(local_calls[0], (start, 0))
        self.assertEqual(local_calls[-1], (start + NUM_MIX_INPUTS - 1, 0))


class ApplySoloCommandTests(unittest.TestCase):
    def test_apply_set_solo_updates_local_state(self) -> None:
        device = MagicMock()
        device.state = DeviceState()
        with patch("ultralite_mk5_lib.commands.send_binary"):
            cmd = apply_set_solo(device, "MIXBUSFADER_MAIN0102_LINEIN03", "solo")
        self.assertTrue(cmd.soloed)
        self.assertEqual(device.state.props["mix_solo"][cmd.index], 1)

    def test_apply_clear_mix_solo(self) -> None:
        device = MagicMock()
        device.mix = MagicMock()
        bus_view = MagicMock()
        device.mix.__getitem__.return_value = bus_view
        apply_clear_mix_solo(device, "MIXBUSFADER_REVERB_OUT")
        device.mix.__getitem__.assert_called_once_with(Buses(MIX_BUS_MUTE_INDICES["reverb"]))
        bus_view.clear_solos.assert_called_once()


if __name__ == "__main__":
    unittest.main()
