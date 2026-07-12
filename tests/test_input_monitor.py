"""Tests for HOME tab input monitor preset helpers."""

from __future__ import annotations

import unittest

from ultralite_mk5_lib.input_monitor import (
    INPUT_MONITOR_MAIN_OCH,
    INPUT_MONITOR_PHONES_OCH,
    input_monitor_button_state,
    input_monitor_gain_och,
    resolve_input_monitor_enabled,
    validate_input_monitor_index,
)
from ultralite_mk5_lib.mix_buses import mix_fader_index


class InputMonitorGainOchTests(unittest.TestCase):
    def test_main_and_phones(self) -> None:
        self.assertEqual(input_monitor_gain_och("main"), INPUT_MONITOR_MAIN_OCH)
        self.assertEqual(input_monitor_gain_och("phones"), INPUT_MONITOR_PHONES_OCH)

    def test_invalid_bus(self) -> None:
        with self.assertRaises(ValueError):
            input_monitor_gain_och("reverb")


class InputMonitorButtonStateTests(unittest.TestCase):
    def test_off_when_fader_zero(self) -> None:
        flat = mix_fader_index(2, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {flat: 0.0},
            "mix_mute": {flat: 0},
            "mix_pan": {flat: 0.5},
            "mix_stereo": {2: 0},
        }
        self.assertEqual(input_monitor_button_state(props, 2, INPUT_MONITOR_MAIN_OCH), "off")

    def test_on_at_preset(self) -> None:
        flat = mix_fader_index(0, INPUT_MONITOR_PHONES_OCH)
        props = {
            "mix_fader": {flat: 1.0},
            "mix_mute": {flat: 0},
            "mix_pan": {flat: 0.5},
            "mix_stereo": {0: 0},
        }
        self.assertEqual(
            input_monitor_button_state(props, 0, INPUT_MONITOR_PHONES_OCH),
            "on",
        )

    def test_edited_when_muted(self) -> None:
        flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {flat: 1.0},
            "mix_mute": {flat: 1},
            "mix_pan": {flat: 0.5},
            "mix_stereo": {1: 0},
        }
        self.assertEqual(input_monitor_button_state(props, 1, INPUT_MONITOR_MAIN_OCH), "edited")

    def test_edited_when_pan_off_center(self) -> None:
        flat = mix_fader_index(2, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {flat: 1.0},
            "mix_mute": {flat: 0},
            "mix_pan": {flat: 0.25},
            "mix_stereo": {2: 0},
        }
        self.assertEqual(input_monitor_button_state(props, 2, INPUT_MONITOR_MAIN_OCH), "edited")

    def test_stereo_linked_on_when_both_preset(self) -> None:
        left_flat = mix_fader_index(0, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {left_flat: 1.0, right_flat: 1.0},
            "mix_mute": {left_flat: 0, right_flat: 0},
            "mix_pan": {left_flat: 0.25, right_flat: 0.75},
            "mix_stereo": {0: 1},
        }
        self.assertEqual(
            input_monitor_button_state(props, 0, INPUT_MONITOR_MAIN_OCH),
            "on",
        )
        self.assertEqual(
            input_monitor_button_state(props, 1, INPUT_MONITOR_MAIN_OCH),
            "on",
        )

    def test_stereo_linked_off_when_both_zero(self) -> None:
        left_flat = mix_fader_index(2, INPUT_MONITOR_PHONES_OCH)
        right_flat = mix_fader_index(3, INPUT_MONITOR_PHONES_OCH)
        props = {
            "mix_fader": {left_flat: 0.0, right_flat: 0.0},
            "mix_mute": {left_flat: 0, right_flat: 0},
            "mix_pan": {left_flat: 0.5, right_flat: 0.5},
            "mix_stereo": {2: 1},
        }
        self.assertEqual(
            input_monitor_button_state(props, 2, INPUT_MONITOR_PHONES_OCH),
            "off",
        )
        self.assertEqual(
            input_monitor_button_state(props, 3, INPUT_MONITOR_PHONES_OCH),
            "off",
        )

    def test_stereo_linked_edited_when_one_off(self) -> None:
        left_flat = mix_fader_index(4, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(5, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {left_flat: 1.0, right_flat: 0.0},
            "mix_mute": {left_flat: 0, right_flat: 0},
            "mix_pan": {left_flat: 0.5, right_flat: 0.5},
            "mix_stereo": {4: 1},
        }
        self.assertEqual(
            input_monitor_button_state(props, 4, INPUT_MONITOR_MAIN_OCH),
            "edited",
        )
        self.assertEqual(
            input_monitor_button_state(props, 5, INPUT_MONITOR_MAIN_OCH),
            "edited",
        )

    def test_stereo_lookup_uses_left_index(self) -> None:
        left_flat = mix_fader_index(0, INPUT_MONITOR_MAIN_OCH)
        right_flat = mix_fader_index(1, INPUT_MONITOR_MAIN_OCH)
        props = {
            "mix_fader": {left_flat: 1.0, right_flat: 1.0},
            "mix_mute": {left_flat: 0, right_flat: 0},
            "mix_pan": {left_flat: 0.5, right_flat: 0.5},
            "mix_stereo": {0: 1},
        }
        self.assertEqual(
            input_monitor_button_state(props, 1, INPUT_MONITOR_MAIN_OCH),
            "on",
        )

    def test_validate_index(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_monitor_index(8)


class ResolveInputMonitorEnabledTests(unittest.TestCase):
    def test_toggle_from_off_enables(self) -> None:
        self.assertTrue(resolve_input_monitor_enabled("toggle", current="off"))

    def test_toggle_from_on_disables(self) -> None:
        self.assertFalse(resolve_input_monitor_enabled("toggle", current="on"))

    def test_toggle_from_edited_disables(self) -> None:
        self.assertFalse(resolve_input_monitor_enabled("toggle", current="edited"))

    def test_explicit_on_off(self) -> None:
        self.assertTrue(resolve_input_monitor_enabled("on", current="off"))
        self.assertFalse(resolve_input_monitor_enabled("off", current="on"))


if __name__ == "__main__":
    unittest.main()
