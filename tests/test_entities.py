"""Tests for entity registry and resolution."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.entities import (
    display_name,
    property_index,
    resolve_entity,
    resolve_stereo_input_gain_ich,
)


class ResolveEntityTests(unittest.TestCase):
    def test_known_mix_fader(self) -> None:
        ref = resolve_entity("MIXBUSFADER_PHONES_MICLINEIN01")
        self.assertEqual(ref.kind, "mix_fader")
        self.assertEqual(ref.index, 320)
        self.assertEqual(ref.gain_ich, 0)
        self.assertEqual(ref.gain_och, 10)

    def test_unknown_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_entity("NOT_A_REAL_KEY")


class PropertyIndexTests(unittest.TestCase):
    def test_volume_main(self) -> None:
        self.assertEqual(property_index("VOLUME_MAIN"), ("main_trim", 0))

    def test_meter_raises(self) -> None:
        with self.assertRaises(ValueError):
            property_index("METER_INPUT_MICLINEIN01")


class ResolveStereoInputGainIchTests(unittest.TestCase):
    def test_mix_input_key(self) -> None:
        self.assertEqual(resolve_stereo_input_gain_ich("MIXINPUT_MICLINEIN01"), 0)

    def test_mix_fader_crosspoint_key(self) -> None:
        self.assertEqual(
            resolve_stereo_input_gain_ich("MIXBUSFADER_MAIN0102_LINEIN03"),
            2,
        )

    def test_bus_fader_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_stereo_input_gain_ich("MIXBUSFADER_MAIN0102_OUT")


class DisplayNameTests(unittest.TestCase):
    def test_returns_cuemix_label(self) -> None:
        self.assertEqual(display_name("INPUTGAIN_MICLINEIN01"), "Mic/Line In 1")


if __name__ == "__main__":
    unittest.main()
