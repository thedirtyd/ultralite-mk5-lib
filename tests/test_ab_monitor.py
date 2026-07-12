"""Tests for A/B monitoring helpers."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.ab_monitor import (
    ab_monitor_enabled,
    ab_monitor_path,
    build_ab_monitor_state,
    build_ab_monitor_write,
    parse_ab_monitor_enabled,
    parse_ab_monitor_path,
)
from ultralite_mk5_lib.protocol import K_A_ENABLE_ID, K_AB_ENABLE_ID, K_B_ENABLE_ID
from tests.helpers import assert_frame_header, minimal_props


class ABMonitorReadTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        props = minimal_props()
        self.assertFalse(ab_monitor_enabled(props))
        self.assertEqual(ab_monitor_path(props), "none")

    def test_enabled_a_only(self) -> None:
        props = minimal_props(
            ab_enable={0: 1},
            a_enable={0: 1},
            b_enable={0: 0},
        )
        self.assertTrue(ab_monitor_enabled(props))
        self.assertEqual(ab_monitor_path(props), "a")

    def test_enabled_both(self) -> None:
        props = minimal_props(
            ab_enable={0: 1},
            a_enable={0: 1},
            b_enable={0: 1},
        )
        self.assertEqual(ab_monitor_path(props), "both")

    def test_build_state(self) -> None:
        state = build_ab_monitor_state(
            minimal_props(ab_enable={0: 1}, a_enable={0: 0}, b_enable={0: 1})
        )
        self.assertEqual(state, {"enabled": True, "path": "b"})


class ABMonitorParseTests(unittest.TestCase):
    def test_parse_enabled(self) -> None:
        self.assertTrue(parse_ab_monitor_enabled("on"))
        self.assertFalse(parse_ab_monitor_enabled("off"))

    def test_parse_path(self) -> None:
        self.assertEqual(parse_ab_monitor_path("both"), "both")

    def test_invalid_enabled(self) -> None:
        with self.assertRaises(ValueError):
            parse_ab_monitor_enabled("maybe")

    def test_invalid_path(self) -> None:
        with self.assertRaises(ValueError):
            parse_ab_monitor_path("none")


class ABMonitorWriteTests(unittest.TestCase):
    def test_enable_frames(self) -> None:
        write = build_ab_monitor_write(enabled=True)
        self.assertEqual(len(write.frames), 21)
        assert_frame_header(write.frames[0:7], K_AB_ENABLE_ID, 0)
        self.assertEqual(write.frames[6], 1)
        assert_frame_header(write.frames[7:14], K_A_ENABLE_ID, 0)
        self.assertEqual(write.frames[13], 1)
        assert_frame_header(write.frames[14:21], K_B_ENABLE_ID, 0)
        self.assertEqual(write.frames[20], 0)

    def test_disable_frames(self) -> None:
        write = build_ab_monitor_write(enabled=False)
        self.assertEqual(write.frames[6], 0)
        self.assertEqual(write.frames[13], 0)
        self.assertEqual(write.frames[20], 0)

    def test_path_both_frames(self) -> None:
        write = build_ab_monitor_write(path="both")
        self.assertEqual(write.frames[6], 1)
        self.assertEqual(write.frames[13], 1)
        self.assertEqual(write.frames[20], 1)


if __name__ == "__main__":
    unittest.main()
