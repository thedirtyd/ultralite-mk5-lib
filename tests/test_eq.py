"""Tests for EQ catalog, validation, and report builders."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.eq import (
    EQ_BAND_KEYS,
    EQMode,
    build_bus_eq_state,
    build_input_eq_state,
    clamp_freq,
    clamp_gain,
    clamp_q,
    parse_eq_gain_token,
    gain_applies,
    input_eq_hidden_in_report,
    parse_mode,
    q_applies,
    resolve_eq_band,
)
from ultralite_mk5_lib.protocol import (
    K_BUS_EQ_FREQ_ID,
    K_INPUT_EQ_FREQ_ID,
    K_INPUT_EQ_GAIN_ID,
    make_input_eq_freq_frame,
    make_input_eq_gain_frame,
)
from tests.helpers import assert_frame_header, minimal_props


class EQCatalogTests(unittest.TestCase):
    def test_registry_has_expected_key_count(self) -> None:
        self.assertEqual(len(EQ_BAND_KEYS), 32 + 21)

    def test_input_eq_key_resolves(self) -> None:
        spec = resolve_eq_band("INPUTEQ_LINEIN03_B2")
        self.assertEqual(spec.block, "input")
        self.assertEqual(spec.channel_eq_index, 2)
        self.assertEqual(spec.band, 2)
        self.assertEqual(spec.flat_index, 9)

    def test_bus_eq_key_resolves(self) -> None:
        spec = resolve_eq_band("BUSEQ_MAIN0102_B1")
        self.assertEqual(spec.block, "output")
        self.assertEqual(spec.channel_eq_index, 0)
        self.assertEqual(spec.flat_index, 0)

    def test_middle_input_band_locked_to_peak(self) -> None:
        spec = resolve_eq_band("INPUTEQ_LINEIN03_B2")
        self.assertEqual(spec.locked_mode, EQMode.PEAK)


class EQValidationTests(unittest.TestCase):
    def test_clamp_freq(self) -> None:
        self.assertEqual(clamp_freq(10), 20)
        self.assertEqual(clamp_freq(500), 500)
        self.assertEqual(clamp_freq(99999), 20000)

    def test_clamp_gain_and_q(self) -> None:
        self.assertEqual(clamp_gain(-99), -20.0)
        self.assertEqual(clamp_gain(99), 20.0)
        self.assertEqual(clamp_q(0.1), 0.45)
        self.assertEqual(clamp_q(99), 10.0)

    def test_parse_eq_gain_token(self) -> None:
        self.assertEqual(parse_eq_gain_token("-6"), -6.0)
        self.assertEqual(parse_eq_gain_token("-6db"), -6.0)
        self.assertEqual(parse_eq_gain_token("-6.5dB"), -6.5)

    def test_applicability(self) -> None:
        self.assertFalse(gain_applies(EQMode.HIGH_PASS))
        self.assertTrue(gain_applies(EQMode.PEAK))
        self.assertTrue(q_applies(EQMode.PEAK))
        self.assertFalse(q_applies(EQMode.LOW_SHELF))

    def test_parse_mode(self) -> None:
        self.assertEqual(parse_mode("highpass"), EQMode.HIGH_PASS)
        self.assertEqual(parse_mode("lowshelf"), EQMode.LOW_SHELF)


class EQReportTests(unittest.TestCase):
    def test_input_eq_hides_right_channel_when_linked(self) -> None:
        props = minimal_props(
            mix_stereo={2: 1},
            input_eq_mode={8: 0, 12: 3},
            input_eq_bypass={8: 0, 12: 0},
            input_eq_freq={8: 400, 12: 8000},
            input_eq_gain={8: 0.0, 12: 0.0},
            input_eq_q={8: 1.0, 12: 1.0},
        )
        rows = build_input_eq_state(props)
        keys = {row["key"] for row in rows}
        self.assertIn("INPUTEQ_LINEIN03_B1", keys)
        self.assertNotIn("INPUTEQ_LINEIN04_B1", keys)
        line3 = next(row for row in rows if row["key"] == "INPUTEQ_LINEIN03_B1")
        self.assertEqual(line3["channel"], "Line In 3-4")

    def test_bus_eq_state_includes_all_buses(self) -> None:
        props = minimal_props(
            bus_eq_mode={0: 1, 6: 0},
            bus_eq_bypass={0: 0},
            bus_eq_freq={0: 60},
            bus_eq_gain={0: -3.0},
            bus_eq_q={0: 1.0},
        )
        rows = build_bus_eq_state(props)
        self.assertEqual(len(rows), 21)
        main_b1 = next(row for row in rows if row["key"] == "BUSEQ_MAIN0102_B1")
        self.assertEqual(main_b1["curve"], "lowshelf")
        self.assertFalse(main_b1["curve_locked"])


class EQProtocolTests(unittest.TestCase):
    def test_input_eq_frames(self) -> None:
        frame = make_input_eq_freq_frame(8, 400)
        assert_frame_header(frame, K_INPUT_EQ_FREQ_ID, 8)
        frame = make_input_eq_gain_frame(8, -6.0)
        assert_frame_header(frame, K_INPUT_EQ_GAIN_ID, 8)


class EQStereoMetadataTests(unittest.TestCase):
    def test_right_channel_spec_detected(self) -> None:
        spec = resolve_eq_band("INPUTEQ_LINEIN04_B1")
        props = minimal_props(mix_stereo={2: 1})
        self.assertTrue(spec.is_stereo_right)
        self.assertTrue(input_eq_hidden_in_report(spec, props))


if __name__ == "__main__":
    unittest.main()
