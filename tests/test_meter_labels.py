"""Tests for snapshot-aware meter display names."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.meter_labels import (
    build_meter_names,
    digital_meter_layout,
    iter_layout_meter_keys,
    meter_display_name,
    meter_name_entry,
)
from ultralite_mk5_lib.meters import OPTICAL_MODE_ADAT

from tests.helpers import minimal_props, minimal_snapshot

class TestMeterDisplayName(unittest.TestCase):
    def test_stereo_linked_mic_pair_keeps_mono_labels(self) -> None:
        snap = minimal_snapshot()
        left = meter_display_name("METER_INPUT_MICIN01", snap)
        right = meter_display_name("METER_INPUT_MICIN02", snap)
        self.assertEqual(left, "Inputs - Mic In 1")
        self.assertEqual(right, "Inputs - Mic In 2")
        self.assertNotEqual(left, right)

    def test_stereo_linked_optical_pair_keeps_mono_labels(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={10: 1}))
        left = meter_display_name("METER_INPUT_OPTICAL01", snap)
        right = meter_display_name("METER_INPUT_OPTICAL02", snap)
        self.assertEqual(left, "Inputs - Optical 1")
        self.assertEqual(right, "Inputs - Optical 2")

    def test_stereo_linked_spdif_pair_keeps_mono_labels(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={8: 1}))
        left = meter_display_name("METER_INPUT_SPDIF01", snap)
        right = meter_display_name("METER_INPUT_SPDIF02", snap)
        self.assertEqual(left, "Inputs - S/PDIF 1")
        self.assertEqual(right, "Inputs - S/PDIF 2")

    def test_unlinked_spdif_mono_labels(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={}))
        self.assertEqual(
            meter_display_name("METER_INPUT_SPDIF01", snap),
            "Inputs - S/PDIF 1",
        )
        self.assertEqual(
            meter_display_name("METER_INPUT_SPDIF02", snap),
            "Inputs - S/PDIF 2",
        )

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

    def test_mix_post_fx_keeps_mono_label_when_linked(self) -> None:
        snap = minimal_snapshot(props=minimal_props(mix_stereo={0: 0}))
        self.assertEqual(
            meter_display_name("METER_MIX_MICIN01POSTFX", snap),
            "Mix - Mic In 1 Post-FX",
        )
        linked = minimal_snapshot()
        self.assertEqual(
            meter_display_name("METER_MIX_MICIN01POSTFX", linked),
            "Mix - Mic In 1 Post-FX",
        )
        self.assertEqual(
            meter_display_name("METER_MIX_MICIN02POSTFX", linked),
            "Mix - Mic In 2 Post-FX",
        )

    def test_reverb_wet_title_case(self) -> None:
        snap = minimal_snapshot()
        self.assertEqual(
            meter_display_name("METER_MIX_REVERBWET", snap),
            "Mix - Reverb Wet",
        )


class TestBuildMeterNames(unittest.TestCase):
    def test_includes_layout_active_keys(self) -> None:
        names = build_meter_names(minimal_snapshot())
        self.assertIn("METER_INPUT_MICIN01", names)
        self.assertIn("METER_INPUT_OPTICAL01", names)
        self.assertIn("mono", names["METER_INPUT_MICIN01"])

    def test_stereo_pair_has_mono_and_stereo(self) -> None:
        names = build_meter_names(minimal_snapshot())
        left = names["METER_INPUT_MICIN01"]
        right = names["METER_INPUT_MICIN02"]
        self.assertEqual(left["mono"], "Inputs - Mic In 1")
        self.assertEqual(right["mono"], "Inputs - Mic In 2")
        self.assertEqual(left["stereo"], "Inputs - Mic In 1-2")
        self.assertEqual(right["stereo"], left["stereo"])

    def test_output_trim_has_mono_only(self) -> None:
        names = build_meter_names(minimal_snapshot())
        main = names["METER_OUTPUT_MAINOUT01MIX"]
        self.assertEqual(main["mono"], "Main Out 1")
        self.assertNotIn("stereo", main)

    def test_optical_pair_stereo_label(self) -> None:
        names = build_meter_names(minimal_snapshot())
        self.assertEqual(names["METER_INPUT_OPTICAL01"]["stereo"], "Inputs - Optical 1-2")
        self.assertEqual(names["METER_INPUT_OPTICAL02"]["mono"], "Inputs - Optical 2")

    def test_spdif_pair_stereo_label(self) -> None:
        names = build_meter_names(minimal_snapshot())
        self.assertEqual(names["METER_INPUT_SPDIF01"]["mono"], "Inputs - S/PDIF 1")
        self.assertEqual(names["METER_INPUT_SPDIF02"]["mono"], "Inputs - S/PDIF 2")
        self.assertEqual(names["METER_INPUT_SPDIF01"]["stereo"], "Inputs - S/PDIF 1-2")
        self.assertEqual(names["METER_INPUT_SPDIF02"]["stereo"], names["METER_INPUT_SPDIF01"]["stereo"])

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
