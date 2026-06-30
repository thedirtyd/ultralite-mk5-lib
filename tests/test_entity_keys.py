"""Tests for entity key slug generation."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.entity_keys import (
    input_gain_entity_key,
    meter_entity_key,
    mix_bus_fader_entity_key,
    normalize_key_part,
)


class NormalizeKeyPartTests(unittest.TestCase):
    def test_strips_punctuation(self) -> None:
        self.assertEqual(normalize_key_part("Mic In 1"), "MICIN01")

    def test_zero_pads_single_digits(self) -> None:
        self.assertEqual(normalize_key_part("Main 1-2"), "MAIN0102")


class EntityKeyGenerationTests(unittest.TestCase):
    def test_meter_entity_key(self) -> None:
        self.assertEqual(
            meter_entity_key("Inputs - Mic In 1"),
            "METER_INPUT_MICIN01",
        )

    def test_input_gain_entity_key(self) -> None:
        self.assertEqual(
            input_gain_entity_key("Mic In 1"),
            "INPUTGAIN_MICIN01",
        )

    def test_mix_bus_fader_entity_key(self) -> None:
        self.assertEqual(
            mix_bus_fader_entity_key("main 1-2", "Line In 3"),
            "MIXBUSFADER_MAIN0102_LINEIN03",
        )

    def test_out_column(self) -> None:
        self.assertEqual(
            mix_bus_fader_entity_key("phones", "Out"),
            "MIXBUSFADER_PHONES_OUT",
        )


if __name__ == "__main__":
    unittest.main()
