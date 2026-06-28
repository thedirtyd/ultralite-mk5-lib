"""Tests for snapshot-aware meter display names."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.meter_labels import (
    build_meter_names,
    digital_meter_layout,
    iter_layout_meter_keys,
    meter_display_name,
)
from ultralite_mk5_lib.meters import OPTICAL_MODE_ADAT

from tests.helpers import minimal_props, minimal_snapshot


class TestMeterDisplayName(unittest.TestCase):
    def test_stereo_linked_mic_pair_shares_label(self) -> None:
        snap = minimal_snapshot()
        left = meter_display_name("METER_INPUT_MICLINEIN01", snap)
        right = meter_display_name("METER_INPUT_MICLINEIN02", snap)
        self.assertEqual(left, right)
        self.assertIn("1/2", left)

    def test_stereo_linked_optical_pair_shares_label(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={10: 1}))
        left = meter_display_name("METER_INPUT_OPTICAL01", snap)
        right = meter_display_name("METER_INPUT_OPTICAL02", snap)
        self.assertEqual(left, right)
        self.assertEqual(left, "Inputs - Optical 1/2")

    def test_unlinked_optical_mono_labels(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={}))
        self.assertEqual(
            meter_display_name("METER_INPUT_OPTICAL01", snap),
            "Inputs - Optical 1",
        )
        self.assertEqual(
            meter_display_name("METER_INPUT_OPTICAL02", snap),
            "Inputs - Optical 2",
        )

    def test_output_trim_short_name(self) -> None:
        snap = minimal_snapshot()
        self.assertEqual(
            meter_display_name("METER_OUTPUT_MAINOUT01MIX", snap),
            "Main Out 1",
        )

    def test_phones_mix_labels(self) -> None:
        snap = minimal_snapshot()
        self.assertEqual(
            meter_display_name("METER_OUTPUT_PHONESMIXL", snap),
            "Phones L",
        )
        self.assertEqual(
            meter_display_name("METER_OUTPUT_PHONESMIXR", snap),
            "Phones R",
        )


class TestBuildMeterNames(unittest.TestCase):
    def test_includes_layout_active_keys(self) -> None:
        names = build_meter_names(minimal_snapshot())
        self.assertIn("METER_INPUT_MICLINEIN01", names)
        self.assertIn("METER_INPUT_OPTICAL01", names)

    def test_192k_omits_optical_meters(self) -> None:
        snap = minimal_snapshot(sample_rate=192000)
        keys = iter_layout_meter_keys(snap)
        self.assertNotIn("METER_INPUT_OPTICAL01", keys)
        names = build_meter_names(snap)
        self.assertNotIn("METER_INPUT_OPTICAL01", names)


class TestDigitalMeterLayout(unittest.TestCase):
    def test_48k_adat_counts(self) -> None:
        layout = digital_meter_layout(minimal_snapshot())
        self.assertEqual(layout["spdif_in"], 2)
        self.assertEqual(layout["optical_in"], 8)
        self.assertEqual(layout["spdif_out"], 2)
        self.assertEqual(layout["optical_out"], 8)

    def test_192k_hides_digital(self) -> None:
        snap = minimal_snapshot(
            sample_rate=192000,
            props=minimal_props(
                optical_mode={0: OPTICAL_MODE_ADAT, 1: OPTICAL_MODE_ADAT},
            ),
        )
        layout = digital_meter_layout(snap)
        self.assertEqual(layout["optical_in"], 0)
        self.assertEqual(layout["optical_out"], 0)


if __name__ == "__main__":
    unittest.main()
