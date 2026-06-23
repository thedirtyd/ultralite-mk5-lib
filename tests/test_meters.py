"""Tests for digital output meter catalog and resolution."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.meters import (
    METER_SLOTS,
    OPTICAL_MODE_ADAT,
    OPTICAL_MODE_TOSLINK,
    SPDIF_OUT_PATCH_DEST_LEFT,
    SPDIF_OUT_PATCH_DEST_RIGHT,
    meter_entry_visible,
    optical_output_meter_count,
    resolve_meter_slot,
    spdif_output_meter_count,
)


def _entry_by_name(name: str):
    for entry in METER_SLOTS:
        if entry.name == name:
            return entry
    raise AssertionError(f"missing catalog entry {name!r}")


class DigitalOutputMetersTest(unittest.TestCase):
    def test_optical_output_meter_count_adat(self) -> None:
        self.assertEqual(
            optical_output_meter_count(
                sample_rate=48000,
                optical_output_mode=OPTICAL_MODE_ADAT,
            ),
            8,
        )
        self.assertEqual(
            optical_output_meter_count(
                sample_rate=96000,
                optical_output_mode=OPTICAL_MODE_ADAT,
            ),
            4,
        )
        self.assertEqual(
            optical_output_meter_count(
                sample_rate=192000,
                optical_output_mode=OPTICAL_MODE_ADAT,
            ),
            0,
        )

    def test_optical_output_meter_count_toslink(self) -> None:
        self.assertEqual(
            optical_output_meter_count(
                sample_rate=48000,
                optical_output_mode=OPTICAL_MODE_TOSLINK,
            ),
            2,
        )

    def test_spdif_output_hidden_at_4x(self) -> None:
        self.assertEqual(spdif_output_meter_count(sample_rate=192000), 0)
        spdif_l = _entry_by_name("Outputs - S/PDIF Out L")
        self.assertFalse(
            meter_entry_visible(
                spdif_l,
                sample_rate=192000,
                optical_input_mode=OPTICAL_MODE_ADAT,
                optical_output_mode=OPTICAL_MODE_ADAT,
            )
        )

    def test_resolve_meter_slot_defaults_without_fpga_patch(self) -> None:
        spdif_l = _entry_by_name("Outputs - S/PDIF Out L")
        spdif_r = _entry_by_name("Outputs - S/PDIF Out R")
        optical_1 = _entry_by_name("Outputs - Optical Out 1")
        optical_3 = _entry_by_name("Outputs - Optical Out 3")

        self.assertEqual(resolve_meter_slot(spdif_l), 12)
        self.assertEqual(resolve_meter_slot(spdif_r), 13)
        self.assertEqual(resolve_meter_slot(optical_1), 14)
        self.assertEqual(resolve_meter_slot(optical_3), 16)

    def test_resolve_meter_slot_respects_fpga_patch(self) -> None:
        spdif_l = _entry_by_name("Outputs - S/PDIF Out L")
        optical_1 = _entry_by_name("Outputs - Optical Out 1")
        patch = {
            SPDIF_OUT_PATCH_DEST_LEFT: 46,
            24: 48,
        }
        self.assertEqual(resolve_meter_slot(spdif_l, fpga_patch=patch), 46)
        self.assertEqual(resolve_meter_slot(optical_1, fpga_patch=patch), 48)


if __name__ == "__main__":
    unittest.main()
