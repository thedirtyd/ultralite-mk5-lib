"""Tests for mix bus matrix layout and fader indexing."""

from __future__ import annotations

import math
import unittest

from ultralite_mk5_lib.meters import OPTICAL_MODE_ADAT, OPTICAL_MODE_TOSLINK
from ultralite_mk5_lib.mix_buses import (
    NUM_MIX_INPUTS,
    build_mix_bus_fader_matrix,
    db_to_linear_gain,
    mix_fader_gain_to_db,
    mix_fader_index,
    mix_matrix_columns,
)
from tests.helpers import minimal_props


class MixFaderIndexTests(unittest.TestCase):
    def test_formula(self) -> None:
        self.assertEqual(mix_fader_index(0, 10), 10 * NUM_MIX_INPUTS + 0)
        self.assertEqual(mix_fader_index(2, 0), 2)


class GainConversionTests(unittest.TestCase):
    def test_unity_gain(self) -> None:
        self.assertAlmostEqual(mix_fader_gain_to_db(1.0), 0.0)
        self.assertAlmostEqual(db_to_linear_gain(0.0), 1.0)

    def test_zero_gain_is_negative_infinity(self) -> None:
        db = mix_fader_gain_to_db(0.0)
        self.assertTrue(db is not None and math.isinf(db) and db < 0)


class MixMatrixColumnsTests(unittest.TestCase):
    def test_48k_adat_includes_optical_and_spdif(self) -> None:
        cols = mix_matrix_columns(sample_rate=48000, optical_input_mode=OPTICAL_MODE_ADAT)
        labels = [c.label for c in cols]
        self.assertIn("S/PDIF 1", labels)
        self.assertIn("Optical 1", labels)
        self.assertIn("Out", labels)

    def test_192k_hides_spdif_and_optical(self) -> None:
        cols = mix_matrix_columns(
            sample_rate=192000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        labels = [c.label for c in cols]
        self.assertNotIn("S/PDIF 1", labels)
        self.assertNotIn("Optical 1", labels)

    def test_toslink_fewer_optical_channels(self) -> None:
        adat = mix_matrix_columns(
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        toslink = mix_matrix_columns(
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_TOSLINK,
        )
        adat_opt = sum(1 for c in adat if c.label.startswith("Optical"))
        tos_opt = sum(1 for c in toslink if c.label.startswith("Optical"))
        self.assertGreater(adat_opt, tos_opt)

    def test_host_stereo_label_omits_lr_suffix(self) -> None:
        cols = mix_matrix_columns(
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        host_l = next(c for c in cols if c.label == "Host 1/2 L")
        host_r = next(c for c in cols if c.label == "Host 1/2 R")
        self.assertEqual(host_l.stereo_label, "Host 1/2")
        self.assertEqual(host_r.stereo_label, None)

        phones_l = next(c for c in cols if c.label == "Host Phones L")
        self.assertEqual(phones_l.stereo_label, "Host Phones")


class BuildMixBusFaderMatrixTests(unittest.TestCase):
    def test_matrix_has_columns_and_buses(self) -> None:
        matrix = build_mix_bus_fader_matrix(
            minimal_props(),
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        self.assertIn("columns", matrix)
        self.assertIn("buses", matrix)
        self.assertEqual(len(matrix["buses"]), 7)

    def test_fader_cell_includes_gain_and_db(self) -> None:
        props = minimal_props()
        matrix = build_mix_bus_fader_matrix(
            props,
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        phones = next(b for b in matrix["buses"] if b["name"] == "phones")
        mic_cell = phones["faders"][0]
        self.assertAlmostEqual(mic_cell["gain"], 0.75)
        self.assertIn("db", mic_cell)

    def test_fader_cell_includes_solo_when_prop_present(self) -> None:
        idx = mix_fader_index(0, 10)
        props = minimal_props(mix_solo={idx: 1})
        matrix = build_mix_bus_fader_matrix(
            props,
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        phones = next(b for b in matrix["buses"] if b["name"] == "phones")
        mic_cell = phones["faders"][0]
        self.assertTrue(mic_cell.get("solo"))

    def test_stereo_linked_hides_right_column(self) -> None:
        props = minimal_props()
        matrix = build_mix_bus_fader_matrix(
            props,
            sample_rate=48000,
            optical_input_mode=OPTICAL_MODE_ADAT,
        )
        mic2_col = next(c for c in matrix["columns"] if c["label"] == "Mic In 2")
        self.assertTrue(mic2_col.get("stereo_hidden"))


if __name__ == "__main__":
    unittest.main()
