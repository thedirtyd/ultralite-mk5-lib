"""Tests for wire protocol helpers."""

from __future__ import annotations

import struct
import unittest

from ultralite_mk5_lib.protocol import (
    K824_DIVISOR,
    K_BUS_MUTE_ID,
    K_INPUT_GAIN_ID,
    K_MAIN_TRIM_ID,
    K_MIX_FADER_ID,
    K_MIX_PAN_ID,
    K_MIX_MUTE_ID,
    K_MIX_SOLO_ID,
    K_OPTICAL_MODE_ID,
    K_SAMPLE_RATE_ID,
    build_ws_url,
    gain_to_824,
    make_bus_mute_frame,
    make_input_48v_frame,
    make_input_gain_frame,
    make_main_trim_frame,
    make_mix_fader_frame,
    make_mix_pan_frame,
    make_mix_mute_frame,
    make_mix_solo_frame,
    make_optical_mode_frame,
    make_sample_rate_frame,
    parse_optical_mode,
    parse_sample_rate,
)
from tests.helpers import assert_frame_header


class BuildWsUrlTests(unittest.TestCase):
    def test_direct_host_defaults_port_1280(self) -> None:
        self.assertEqual(build_ws_url("192.168.1.5", None, None), "ws://192.168.1.5:1280")

    def test_localhost_with_serial_uses_proxy_port(self) -> None:
        self.assertEqual(
            build_ws_url("127.0.0.1", None, "ULM5FFF0EE"),
            "ws://127.0.0.1:1281/ULM5FFF0EE",
        )

    def test_explicit_port_and_serial(self) -> None:
        self.assertEqual(
            build_ws_url("host", 9999, "/ABC"),
            "ws://host:9999/ABC",
        )

    def test_full_url_passthrough(self) -> None:
        url = "ws://example:1280/foo"
        self.assertEqual(build_ws_url(url, 1281, "X"), url)


class ParseSampleRateTests(unittest.TestCase):
    def test_hz_values(self) -> None:
        self.assertEqual(parse_sample_rate("48000"), 48000)
        self.assertEqual(parse_sample_rate(96000), 96000)

    def test_khz_values(self) -> None:
        self.assertEqual(parse_sample_rate("48"), 48000)
        self.assertEqual(parse_sample_rate("96"), 96000)

    def test_invalid_rate_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_sample_rate("44101")


class ParseOpticalModeTests(unittest.TestCase):
    def test_adat_and_toslink(self) -> None:
        self.assertEqual(parse_optical_mode("adat"), 0)
        self.assertEqual(parse_optical_mode("TOSLINK"), 1)

    def test_invalid_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_optical_mode("spdif")


class GainTo824Tests(unittest.TestCase):
    def test_unity_gain(self) -> None:
        self.assertEqual(gain_to_824(1.0), K824_DIVISOR)

    def test_half_gain(self) -> None:
        self.assertEqual(gain_to_824(0.5), K824_DIVISOR // 2)


class MakeFrameTests(unittest.TestCase):
    def test_sample_rate_frame(self) -> None:
        frame = make_sample_rate_frame(48000)
        assert_frame_header(frame, K_SAMPLE_RATE_ID, 0)
        self.assertEqual(struct.unpack(">i", frame[6:10])[0], 48000)

    def test_mix_fader_frame(self) -> None:
        frame = make_mix_fader_frame(320, 0.75)
        assert_frame_header(frame, K_MIX_FADER_ID, 320)
        raw = struct.unpack(">i", frame[6:10])[0]
        self.assertAlmostEqual(raw / K824_DIVISOR, 0.75, places=5)

    def test_mix_pan_frame(self) -> None:
        frame = make_mix_pan_frame(320, 0.5)
        assert_frame_header(frame, K_MIX_PAN_ID, 320)
        raw = struct.unpack(">i", frame[6:10])[0]
        self.assertAlmostEqual(raw / K824_DIVISOR, 0.5, places=5)

    def test_input_gain_frame(self) -> None:
        frame = make_input_gain_frame(0, 12)
        assert_frame_header(frame, K_INPUT_GAIN_ID, 0)
        self.assertEqual(frame[6], 12)

    def test_main_trim_frame(self) -> None:
        frame = make_main_trim_frame(0, 6)
        assert_frame_header(frame, K_MAIN_TRIM_ID, 0)
        self.assertEqual(frame[6], 6)

    def test_optical_mode_frame(self) -> None:
        frame = make_optical_mode_frame(1, 1)
        assert_frame_header(frame, K_OPTICAL_MODE_ID, 1)
        self.assertEqual(frame[6], 1)

    def test_mix_mute_frame(self) -> None:
        frame = make_mix_mute_frame(5, True)
        assert_frame_header(frame, K_MIX_MUTE_ID, 5)
        self.assertEqual(frame[6], 1)

    def test_mix_solo_frame(self) -> None:
        frame = make_mix_solo_frame(42, True)
        assert_frame_header(frame, K_MIX_SOLO_ID, 42)
        self.assertEqual(frame[6], 1)

        frame_off = make_mix_solo_frame(42, False)
        self.assertEqual(frame_off[6], 0)

    def test_bus_mute_frame(self) -> None:
        frame = make_bus_mute_frame(0, False)
        assert_frame_header(frame, K_BUS_MUTE_ID, 0)
        self.assertEqual(frame[6], 0)

    def test_input_48v_frame(self) -> None:
        frame = make_input_48v_frame(1, True)
        self.assertEqual(frame[6], 1)


if __name__ == "__main__":
    unittest.main()
