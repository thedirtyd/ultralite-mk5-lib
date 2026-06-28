"""Tests for output trim and monitoring builders."""

from __future__ import annotations

import math
import unittest

from ultralite_mk5_lib.outputs import (
    build_monitors_trim,
    build_output_monitoring,
    build_output_trims,
    trim_byte_to_db,
)
from tests.helpers import minimal_props


class TrimByteToDbTests(unittest.TestCase):
    def test_zero_db(self) -> None:
        self.assertEqual(trim_byte_to_db(0), 0.0)

    def test_minus_ninety_nine(self) -> None:
        self.assertEqual(trim_byte_to_db(99), -99.0)

    def test_negative_infinity(self) -> None:
        db = trim_byte_to_db(100)
        self.assertTrue(db is not None and math.isinf(db) and db < 0)

    def test_none(self) -> None:
        self.assertIsNone(trim_byte_to_db(None))


class BuildOutputTrimsTests(unittest.TestCase):
    def test_line_output_trims(self) -> None:
        rows = build_output_trims(minimal_props())
        self.assertEqual(len(rows), 10)
        by_name = dict(rows)
        self.assertEqual(by_name["Main Out 1"], 0.0)
        self.assertEqual(by_name["Line Out 3"], -6.0)


class BuildMonitorsTrimTests(unittest.TestCase):
    def test_main_out_includes_mute(self) -> None:
        rows = build_monitors_trim(minimal_props())
        main = next(r for r in rows if r[1] == "VOLUME_MAIN")
        self.assertEqual(main[0], "Main Out")
        self.assertEqual(main[2], 0.0)
        self.assertFalse(main[3])

    def test_phones_no_hardware_mute(self) -> None:
        rows = build_monitors_trim(minimal_props())
        phones = next(r for r in rows if r[1] == "VOLUME_PHONES")
        self.assertIsNone(phones[3])


class BuildOutputMonitoringTests(unittest.TestCase):
    def test_default_meter_slots(self) -> None:
        props = minimal_props(fpga_patch={})
        monitoring = build_output_monitoring(
            props,
            [-10.0] * 128,
            meters_received=True,
        )
        self.assertEqual(monitoring["monitor"]["meter_slots"], {"L": 46, "R": 47})
        self.assertEqual(monitoring["phones_output"]["meter_slots"], {"L": 64, "R": 65})

    def test_patched_meter_slots(self) -> None:
        props = minimal_props()
        meters = [-127.5] * 128
        meters[46] = -12.0
        monitoring = build_output_monitoring(
            props,
            meters,
            meters_received=True,
        )
        self.assertEqual(monitoring["monitor"]["meters_db"]["L"], -12.0)

    def test_meters_not_received(self) -> None:
        monitoring = build_output_monitoring(minimal_props(), [], meters_received=False)
        self.assertIsNone(monitoring["monitor"]["meters_db"])


if __name__ == "__main__":
    unittest.main()
