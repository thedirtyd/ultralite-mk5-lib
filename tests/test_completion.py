"""Tests for interactive CLI tab completion."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.completion import (
    _completion_context,
    completion_candidates,
    readline_matches,
)
from ultralite_mk5_lib.entities import (
    INPUT_48V_ENTITY_KEYS,
    SET_LEVEL_ENTITY_KEYS,
    SOLO_OUTPUT_BUS_KEYS,
)
from ultralite_mk5_lib.interactive import COMMAND_ALIASES, INTERACTIVE_COMMANDS


class CompletionCandidatesTests(unittest.TestCase):
    def test_empty_line_lists_commands(self) -> None:
        names = set(completion_candidates("", 0))
        self.assertIn("set-level", names)
        self.assertIn("ls", names)
        self.assertEqual(names, {*INTERACTIVE_COMMANDS, *COMMAND_ALIASES})

    def test_set_level_trailing_space_lists_all_level_keys(self) -> None:
        line = "set-level "
        self.assertEqual(
            completion_candidates(line, len(line)),
            list(SET_LEVEL_ENTITY_KEYS),
        )

    def test_set_level_prefix_filters_keys(self) -> None:
        line = "set-level MIX"
        matches = completion_candidates(line, len(line))
        self.assertTrue(matches)
        self.assertTrue(all(m.startswith("MIX") for m in matches))
        self.assertIn("MIXBUSFADER_MAIN0102_LINEIN03", matches)

    def test_set_level_after_key_offers_no_candidates(self) -> None:
        line = "set-level MIXBUSFADER_MAIN0102_LINEIN03 "
        self.assertEqual(completion_candidates(line, len(line)), [])

    def test_set_48v_lists_mic_keys_only(self) -> None:
        line = "set-48v "
        self.assertEqual(
            completion_candidates(line, len(line)),
            list(INPUT_48V_ENTITY_KEYS),
        )

    def test_solo_output_bus_excludes_reverb(self) -> None:
        line = "solo-output-bus "
        matches = completion_candidates(line, len(line))
        self.assertEqual(matches, list(SOLO_OUTPUT_BUS_KEYS))
        self.assertNotIn("MIXBUSFADER_REVERB_OUT", matches)

    def test_set_channel_mode_mixinput_prefix(self) -> None:
        line = "set-channel-mode MIXINPUT_"
        matches = completion_candidates(line, len(line))
        self.assertTrue(matches)
        self.assertTrue(all(m.startswith("MIXINPUT_") for m in matches))

    def test_set_mute_mixbusfader_prefix(self) -> None:
        line = "set-mute MIXBUSFADER"
        matches = completion_candidates(line, len(line))
        self.assertTrue(matches)
        self.assertTrue(all("MIXBUSFADER" in m for m in matches))

    def test_partial_lowercase_entity_completes_uppercase(self) -> None:
        line = "set-level mixbusfader_main"
        matches = completion_candidates(line, len(line))
        self.assertTrue(matches)
        self.assertTrue(all(m == m.upper() for m in matches))
        self.assertTrue(all(m.startswith("MIXBUSFADER_MAIN") for m in matches))

    def test_help_command_topic_completion(self) -> None:
        line = "help set-"
        matches = completion_candidates(line, len(line))
        self.assertIn("set-level", matches)
        self.assertIn("set-mute", matches)
        self.assertTrue(all(m.startswith("set-") for m in matches))


class ReadlineMatchesTests(unittest.TestCase):
    def test_single_match_returns_full_candidate(self) -> None:
        self.assertEqual(
            readline_matches("VOLUME_M", ["VOLUME_MAIN"]),
            ["VOLUME_MAIN"],
        )

    def test_case_sensitive_prefix_allows_lcp(self) -> None:
        matches = readline_matches(
            "MIX",
            ["MIXBUSFADER_PHONES_OUT", "MIXBUSFADER_MAIN0102_OUT"],
            allow_lcp=True,
        )
        self.assertEqual(len(matches), 2)

    def test_entity_prefix_blocks_lcp_even_when_case_sensitive(self) -> None:
        matches = readline_matches(
            "OUT",
            ["OUTPUTTRIM_LINEOUT03", "OUTPUTTRIM_LINEOUT04"],
            allow_lcp=False,
        )
        self.assertEqual(matches, ["OUT"])

    def test_mixed_case_prefix_blocks_lcp(self) -> None:
        matches = readline_matches(
            "OUTPUTTRIM_lin",
            ["OUTPUTTRIM_LINEOUT03", "OUTPUTTRIM_LINEOUT04"],
            allow_lcp=False,
        )
        self.assertEqual(matches, ["OUTPUTTRIM_lin"])

    def test_empty_prefix_blocks_lcp_for_readline(self) -> None:
        candidates = ["set-level", "set-mute"]
        self.assertEqual(readline_matches("", candidates), [""])

    def test_completion_context_entity_arg_disables_lcp(self) -> None:
        line = "set-level OUT"
        text, allow_lcp = _completion_context(line, len(line))
        self.assertEqual(text, "OUT")
        self.assertFalse(allow_lcp)

    def test_completion_context_trailing_space_entity(self) -> None:
        line = "set-level "
        text, allow_lcp = _completion_context(line, len(line))
        self.assertEqual(text, "")
        self.assertFalse(allow_lcp)


if __name__ == "__main__":
    unittest.main()
