"""Tests for level token parsing and command encoding."""

from __future__ import annotations

import math
import unittest

from ultralite_mk5_lib.levels import (
    fix_set_level_argv,
    parse_level_token,
    prepare_level_command,
    trim_db_to_byte,
)
from ultralite_mk5_lib.outputs import trim_byte_to_db
from ultralite_mk5_lib.protocol import K_MAIN_TRIM_ID, K_MIX_FADER_ID
from tests.helpers import assert_frame_header


class ParseLevelTokenTests(unittest.TestCase):
    def test_db_suffix(self) -> None:
        mode, value = parse_level_token("-6db")
        self.assertEqual(mode, "db")
        self.assertEqual(value, -6.0)

    def test_negative_infinity(self) -> None:
        mode, value = parse_level_token("-inf")
        self.assertEqual(mode, "db")
        self.assertTrue(math.isinf(value) and value < 0)

    def test_linear_gain(self) -> None:
        mode, value = parse_level_token("0.75")
        self.assertEqual(mode, "gain")
        self.assertEqual(value, 0.75)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_level_token("")


class TrimRoundTripTests(unittest.TestCase):
    def test_zero_db(self) -> None:
        self.assertEqual(trim_db_to_byte(0.0), 0)
        self.assertEqual(trim_byte_to_db(0), 0.0)

    def test_minus_six_db(self) -> None:
        self.assertEqual(trim_db_to_byte(-6.0), 6)
        self.assertEqual(trim_byte_to_db(6), -6.0)

    def test_negative_infinity(self) -> None:
        self.assertEqual(trim_db_to_byte(float("-inf")), 100)
        self.assertTrue(math.isinf(trim_byte_to_db(100)))


class PrepareLevelCommandTests(unittest.TestCase):
    def test_mix_fader_db(self) -> None:
        cmd = prepare_level_command("MIXBUSFADER_PHONES_MICLINEIN01", "-12db")
        self.assertEqual(cmd.prop_key, "mix_fader")
        self.assertEqual(cmd.index, 320)
        assert_frame_header(cmd.frame, K_MIX_FADER_ID, 320)

    def test_bus_fader_gain(self) -> None:
        cmd = prepare_level_command("MIXBUSFADER_MAIN0102_OUT", "0.5")
        self.assertEqual(cmd.prop_key, "bus_fader")
        self.assertEqual(cmd.index, 0)
        self.assertAlmostEqual(cmd.wire_value, 0.5)

    def test_input_gain(self) -> None:
        cmd = prepare_level_command("INPUTGAIN_MICLINEIN01", "12")
        self.assertEqual(cmd.prop_key, "input_gain")
        self.assertEqual(cmd.wire_value, 12)

    def test_volume_main_inf(self) -> None:
        cmd = prepare_level_command("VOLUME_MAIN", "-inf")
        self.assertEqual(cmd.prop_key, "main_trim")
        self.assertEqual(cmd.wire_value, 100)
        assert_frame_header(cmd.frame, K_MAIN_TRIM_ID, 0)

    def test_output_trim(self) -> None:
        cmd = prepare_level_command("OUTPUTTRIM_MAINOUT01", "-6db")
        self.assertEqual(cmd.prop_key, "output_trim")
        self.assertEqual(cmd.wire_value, 6)

    def test_invalid_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            prepare_level_command("METER_INPUT_MICLINEIN01", "0")

    def test_fader_gain_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            prepare_level_command("MIXBUSFADER_MAIN0102_OUT", "5")


class FixSetLevelArgvTests(unittest.TestCase):
    def test_inserts_double_dash_before_negative_level(self) -> None:
        argv = ["--host", "127.0.0.1", "set-level", "VOLUME_MAIN", "-6db"]
        fixed = fix_set_level_argv(argv)
        self.assertEqual(fixed, ["--host", "127.0.0.1", "set-level", "VOLUME_MAIN", "--", "-6db"])

    def test_no_change_without_set_level(self) -> None:
        argv = ["get-state", "--json"]
        self.assertEqual(fix_set_level_argv(argv), argv)


if __name__ == "__main__":
    unittest.main()
