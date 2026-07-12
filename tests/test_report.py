"""Tests for get-state style report building."""

from __future__ import annotations

import json
import unittest

from ultralite_mk5_lib.report import build_state_report, state_report_to_json
from tests.helpers import minimal_snapshot


class BuildStateReportTests(unittest.TestCase):
    def test_top_level_sections(self) -> None:
        report = build_state_report(minimal_snapshot())
        self.assertIn("device", report)
        self.assertIn("ab_monitor", report)
        self.assertIn("monitor_trim", report)
        self.assertIn("input_gain", report)
        self.assertIn("input_eq", report)
        self.assertIn("bus_eq", report)
        self.assertIn("output_trim", report)
        self.assertIn("mix_bus_faders", report)
        self.assertIn("meters", report)

    def test_device_fields(self) -> None:
        report = build_state_report(minimal_snapshot())
        device = report["device"]
        self.assertEqual(device["name"], "UltraLite mk5")
        self.assertEqual(device["sample_rate"], 48000)
        self.assertEqual(device["optical_input_mode"], "adat")

    def test_ab_monitor_fields(self) -> None:
        report = build_state_report(minimal_snapshot())
        self.assertEqual(report["ab_monitor"], {"enabled": False, "path": "none"})

    def test_mix_bus_faders_have_keys(self) -> None:
        report = build_state_report(minimal_snapshot())
        buses = report["mix_bus_faders"]["buses"]
        self.assertTrue(buses)
        phones = next(b for b in buses if b["name"] == "phones")
        self.assertEqual(phones["key"], "PHONES")
        fader_keys = [f["key"] for f in phones["faders"] if "key" in f]
        self.assertIn("MIXBUSFADER_PHONES_MICIN01", fader_keys)

    def test_meters_include_visible_slots(self) -> None:
        report = build_state_report(minimal_snapshot())
        self.assertTrue(report["meters"])
        first = report["meters"][0]
        self.assertIn("key", first)
        self.assertIn("slot", first)
        self.assertIn("db", first)


class StateReportToJsonTests(unittest.TestCase):
    def test_valid_strict_json(self) -> None:
        text = state_report_to_json(minimal_snapshot())
        parsed = json.loads(text)
        self.assertIn("device", parsed)


if __name__ == "__main__":
    unittest.main()
