"""Tests for set-level argv handling (negative dB tokens)."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.interactive import build_interactive_parser
from ultralite_mk5_lib.levels import fix_set_level_argv


class FixSetLevelArgvTests(unittest.TestCase):
    def test_negative_db_gets_end_of_options(self) -> None:
        argv = ["set-level", "MIXBUSFADER_PHONES_MICLINEIN01", "-12db"]
        self.assertEqual(
            fix_set_level_argv(argv),
            ["set-level", "MIXBUSFADER_PHONES_MICLINEIN01", "--", "-12db"],
        )

    def test_existing_end_of_options_unchanged(self) -> None:
        argv = ["set-level", "MIXBUSFADER_PHONES_MICLINEIN01", "--", "-12db"]
        self.assertEqual(fix_set_level_argv(argv), argv)

    def test_positive_gain_unchanged(self) -> None:
        argv = ["set-level", "INPUTGAIN_MICLINEIN01", "12"]
        self.assertEqual(fix_set_level_argv(argv), argv)


class InteractiveSetLevelParseTests(unittest.TestCase):
    def test_parse_negative_db(self) -> None:
        parser = build_interactive_parser()
        argv = fix_set_level_argv(
            ["set-level", "MIXBUSFADER_PHONES_MICLINEIN01", "-12db"]
        )
        args = parser.parse_args(argv)
        self.assertEqual(args.command, "set-level")
        self.assertEqual(args.key, "MIXBUSFADER_PHONES_MICLINEIN01")
        self.assertEqual(args.level, "-12db")

    def test_parse_with_explicit_end_of_options(self) -> None:
        parser = build_interactive_parser()
        argv = fix_set_level_argv(
            ["set-level", "MIXBUSFADER_PHONES_MICLINEIN01", "--", "-12db"]
        )
        args = parser.parse_args(argv)
        self.assertEqual(args.level, "-12db")


if __name__ == "__main__":
    unittest.main()
