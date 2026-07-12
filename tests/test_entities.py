"""Tests for entity registry and resolution."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.entities import (
    _MIX_FADER_TO_KEY,
    display_name,
    iter_canonical_bus_fader_keys,
    iter_canonical_mix_fader_keys,
    mix_fader_cell,
    prefer_canonical_mix_fader_key,
    property_index,
    resolve_entity,
    resolve_stereo_input_gain_ich,
)


class ResolveEntityTests(unittest.TestCase):
    def test_known_mix_fader(self) -> None:
        ref = resolve_entity("MIXBUSFADER_PHONES_MICIN01")
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
            property_index("METER_INPUT_MICIN01")


class ResolveStereoInputGainIchTests(unittest.TestCase):
    def test_mix_input_key(self) -> None:
        self.assertEqual(resolve_stereo_input_gain_ich("MIXINPUT_MICIN01"), 0)

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
        self.assertEqual(display_name("INPUTGAIN_MICIN01"), "Mic In 1")


class CanonicalMixFaderKeyTests(unittest.TestCase):
    def test_prefers_paired_line_bus_slug(self) -> None:
        self.assertEqual(
            prefer_canonical_mix_fader_key(
                "MIXBUSFADER_LINE03_OPTICAL01",
                "MIXBUSFADER_LINE0304_OPTICAL01",
            ),
            "MIXBUSFADER_LINE0304_OPTICAL01",
        )

    def test_prefers_numbered_host_key_over_host_lr(self) -> None:
        self.assertEqual(
            prefer_canonical_mix_fader_key(
                "MIXBUSFADER_LINE0304_HOSTL",
                "MIXBUSFADER_LINE0304_HOST03",
            ),
            "MIXBUSFADER_LINE0304_HOST03",
        )

    def test_canonical_iter_has_unique_wire_cells(self) -> None:
        keys = iter_canonical_mix_fader_keys()
        cells = {mix_fader_cell(key) for key in keys}
        self.assertEqual(len(keys), len(cells))
        self.assertIn("MIXBUSFADER_LINE0304_OPTICAL01", keys)
        self.assertNotIn("MIXBUSFADER_LINE03_OPTICAL01", keys)

    def test_internal_cell_map_uses_preferred_alias(self) -> None:
        self.assertEqual(_MIX_FADER_TO_KEY[(10, 2)], "MIXBUSFADER_LINE0304_OPTICAL01")
        self.assertEqual(_MIX_FADER_TO_KEY[(20, 2)], "MIXBUSFADER_LINE0304_HOST03")


class CanonicalBusFaderKeyTests(unittest.TestCase):
    def test_prefers_paired_line_bus_out_key(self) -> None:
        keys = iter_canonical_bus_fader_keys()
        self.assertIn("MIXBUSFADER_LINE0304_OUT", keys)
        self.assertNotIn("MIXBUSFADER_LINE03_OUT", keys)


if __name__ == "__main__":
    unittest.main()
