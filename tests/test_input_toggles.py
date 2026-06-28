"""Tests for 48V and pad toggle command encoding."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.input_toggles import (
    parse_toggle_value,
    prepare_48v_command,
    prepare_pad_command,
)
from ultralite_mk5_lib.protocol import K_INPUT_48V_ID, K_INPUT_PAD_ID
from tests.helpers import assert_frame_header


class ParseToggleValueTests(unittest.TestCase):
    def test_on(self) -> None:
        self.assertTrue(parse_toggle_value("on"))
        self.assertTrue(parse_toggle_value("1"))

    def test_off(self) -> None:
        self.assertFalse(parse_toggle_value("off"))
        self.assertFalse(parse_toggle_value("false"))

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_toggle_value("maybe")


class Prepare48vCommandTests(unittest.TestCase):
    def test_default_on(self) -> None:
        cmd = prepare_48v_command("INPUT48V_MICLINEIN01")
        self.assertTrue(cmd.on)
        self.assertEqual(cmd.index, 0)
        assert_frame_header(cmd.frame, K_INPUT_48V_ID, 0)

    def test_jack_detect_blocks_line_input(self) -> None:
        with self.assertRaises(ValueError):
            prepare_48v_command(
                "INPUT48V_MICLINEIN02",
                jack_detect={1: 1},
            )

    def test_unknown_48v_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            prepare_48v_command("INPUT48V_LINEIN03")


class PreparePadCommandTests(unittest.TestCase):
    def test_pad_off(self) -> None:
        cmd = prepare_pad_command("INPUTPAD_MICLINEIN01", "off")
        self.assertFalse(cmd.on)
        assert_frame_header(cmd.frame, K_INPUT_PAD_ID, 0)

    def test_wrong_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            prepare_pad_command("INPUTGAIN_MICLINEIN01")


if __name__ == "__main__":
    unittest.main()
