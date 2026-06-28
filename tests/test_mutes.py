"""Tests for mute command encoding."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.mutes import (
    parse_mute_value,
    prepare_mute_command,
    resolve_solo_bus_entity,
)
from ultralite_mk5_lib.protocol import K_BUS_MUTE_ID, K_MIX_MUTE_ID
from tests.helpers import assert_frame_header


class ParseMuteValueTests(unittest.TestCase):
    def test_mute_on(self) -> None:
        self.assertTrue(parse_mute_value("mute"))
        self.assertTrue(parse_mute_value("ON"))

    def test_unmute(self) -> None:
        self.assertFalse(parse_mute_value("unmute"))
        self.assertFalse(parse_mute_value("0"))

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_mute_value("maybe")


class PrepareMuteCommandTests(unittest.TestCase):
    def test_mix_fader_mute(self) -> None:
        cmd = prepare_mute_command("MIXBUSFADER_PHONES_MICLINEIN01")
        self.assertEqual(cmd.prop_key, "mix_mute")
        self.assertTrue(cmd.muted)
        assert_frame_header(cmd.frame, K_MIX_MUTE_ID, cmd.index)

    def test_bus_fader_unmute(self) -> None:
        cmd = prepare_mute_command("MIXBUSFADER_MAIN0102_OUT", "unmute")
        self.assertEqual(cmd.prop_key, "bus_mute")
        self.assertEqual(cmd.index, 0)
        self.assertFalse(cmd.muted)
        assert_frame_header(cmd.frame, K_BUS_MUTE_ID, 0)

    def test_invalid_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            prepare_mute_command("INPUTGAIN_MICLINEIN01")


class ResolveSoloBusEntityTests(unittest.TestCase):
    def test_main_bus(self) -> None:
        key, index = resolve_solo_bus_entity("MIXBUSFADER_MAIN0102_OUT")
        self.assertEqual(key, "MIXBUSFADER_MAIN0102_OUT")
        self.assertEqual(index, 0)

    def test_reverb_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_solo_bus_entity("MIXBUSFADER_REVERB_OUT")


if __name__ == "__main__":
    unittest.main()
