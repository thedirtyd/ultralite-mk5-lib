"""Tests for input gain and mic pre state builders."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.inputs import build_input_gains, build_mic_pre_state
from tests.helpers import minimal_props


class BuildInputGainsTests(unittest.TestCase):
    def test_row_shape(self) -> None:
        rows = build_input_gains(minimal_props())
        self.assertEqual(len(rows), 8)
        name, db, min_db, max_db = rows[0]
        self.assertEqual(name, "Mic In 1")
        self.assertEqual(db, 12.0)
        self.assertEqual(min_db, 0.0)
        self.assertEqual(max_db, 74.0)

    def test_missing_gain_is_none(self) -> None:
        rows = build_input_gains({})
        self.assertIsNone(rows[0][1])


class BuildMicPreStateTests(unittest.TestCase):
    def test_mic_pre_fields(self) -> None:
        rows = build_mic_pre_state(minimal_props())
        self.assertEqual(len(rows), 2)
        mic1 = rows[0]
        self.assertEqual(mic1["name"], "Mic In 1")
        self.assertTrue(mic1["48v"])
        self.assertFalse(mic1["pad"])
        self.assertEqual(mic1["jack"], "mic")
        self.assertEqual(mic1["key_48v"], "INPUT48V_MICIN01")

    def test_line_jack_mode(self) -> None:
        rows = build_mic_pre_state(minimal_props())
        mic2 = rows[1]
        self.assertEqual(mic2["jack"], "line")


if __name__ == "__main__":
    unittest.main()
