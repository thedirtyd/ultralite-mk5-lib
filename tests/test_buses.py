"""Tests for mix bus mute helpers."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.buses import (
    MIX_BUS_MUTE_INDICES,
    REVERB_BUS_MUTE_INDEX,
    solo_bus_mute_indices,
    stereo_bus_muted,
)


class SoloBusMuteIndicesTests(unittest.TestCase):
    def test_solo_main_mutes_others_except_reverb(self) -> None:
        pairs = solo_bus_mute_indices(0)
        indices = dict(pairs)
        self.assertFalse(indices[0])
        self.assertTrue(indices[10])
        self.assertNotIn(REVERB_BUS_MUTE_INDEX, indices)

    def test_all_non_reverb_buses_present(self) -> None:
        pairs = solo_bus_mute_indices(10)
        expected = {
            idx for name, idx in MIX_BUS_MUTE_INDICES.items() if name != "reverb"
        }
        self.assertEqual({idx for idx, _ in pairs}, expected)
        self.assertFalse(dict(pairs)[10])


class StereoBusMutedTests(unittest.TestCase):
    def test_neither_set_returns_none(self) -> None:
        self.assertIsNone(stereo_bus_muted({}, 0))

    def test_left_only(self) -> None:
        self.assertTrue(stereo_bus_muted({0: 1}, 0))

    def test_right_only(self) -> None:
        self.assertTrue(stereo_bus_muted({1: 1}, 0))

    def test_both_unmuted(self) -> None:
        self.assertFalse(stereo_bus_muted({0: 0, 1: 0}, 0))


if __name__ == "__main__":
    unittest.main()
