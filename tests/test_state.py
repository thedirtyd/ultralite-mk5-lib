"""Tests for device state parsing and display helpers."""

from __future__ import annotations

import json
import math
import struct
import unittest

from ultralite_mk5_lib.protocol import K_OPTICAL_MODE_ID, K_SAMPLE_RATE_ID
from ultralite_mk5_lib.state import (
    K_METERS_ID,
    DeviceState,
    db_to_fader_position,
    decode_meter_peaks,
    format_db,
    format_meter_bar,
    inbound_frame_length,
    iter_inbound_frames,
    linear_gain_to_db,
    snapshot_to_json,
    unpack_property_value,
)
from tests.helpers import (
    inbound_byte_frame,
    inbound_float_frame,
    inbound_int32_frame,
)


class UnpackPropertyValueTests(unittest.TestCase):
    def test_byte(self) -> None:
        data = inbound_byte_frame(5006, 0, 42)
        self.assertEqual(unpack_property_value("byte", data), 42)

    def test_int16(self) -> None:
        data = struct.pack(">HHh", 8, 0, -3)
        self.assertEqual(unpack_property_value("int16", data), -3)

    def test_int32(self) -> None:
        data = inbound_int32_frame(10, 0, 48000)
        self.assertEqual(unpack_property_value("int32", data), 48000)

    def test_float_824(self) -> None:
        data = inbound_float_frame(1016, 0, 0.75)
        self.assertAlmostEqual(unpack_property_value("float", data), 0.75, places=5)

    def test_string(self) -> None:
        payload = b"UltraLite\x00"
        data = struct.pack(">HH", 3, 0) + payload
        self.assertEqual(unpack_property_value("string", data), "UltraLite")


class FrameIterationTests(unittest.TestCase):
    def test_iter_inbound_frames_splits_concatenated_payload(self) -> None:
        a = inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000)
        b = inbound_byte_frame(K_OPTICAL_MODE_ID, 0, 0)
        combined = a + b
        frames = list(iter_inbound_frames(combined))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], a)
        self.assertEqual(frames[1], b)

    def test_inbound_frame_length_byte_property(self) -> None:
        frame = inbound_byte_frame(K_OPTICAL_MODE_ID, 0, 0)
        self.assertEqual(inbound_frame_length(frame), 5)


class MeterDecodeTests(unittest.TestCase):
    def test_decode_meter_peaks(self) -> None:
        data = struct.pack(">HH", K_METERS_ID, 0) + bytes([20, 40])
        self.assertEqual(decode_meter_peaks(data), [-10.0, -20.0])


class DisplayHelperTests(unittest.TestCase):
    def test_linear_gain_to_db(self) -> None:
        self.assertAlmostEqual(linear_gain_to_db(1.0), 0.0)
        self.assertTrue(math.isinf(linear_gain_to_db(0.0)))

    def test_format_db(self) -> None:
        self.assertEqual(format_db(float("-inf")), "-inf")
        self.assertEqual(format_db(None), "n/a")

    def test_format_meter_bar_silent(self) -> None:
        bar = format_meter_bar(-127.5)
        self.assertNotIn("\u2588", bar)

    def test_format_meter_bar_loud(self) -> None:
        bar = format_meter_bar(0.0)
        self.assertTrue(all(c == "\u2588" for c in bar))

    def test_db_to_fader_position(self) -> None:
        pos = db_to_fader_position(-36.0, min_db=-72.0, max_db=12.0, width=24)
        self.assertEqual(pos, 10)


class SnapshotJsonTests(unittest.TestCase):
    def test_sanitize_negative_infinity(self) -> None:
        text = snapshot_to_json({"level": float("-inf")})
        parsed = json.loads(text)
        self.assertEqual(parsed["level"], "-inf")


class DeviceStateTests(unittest.TestCase):
    def test_apply_frame_updates_props(self) -> None:
        state = DeviceState()
        state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))
        self.assertEqual(state.props["sample_rate"][0], 48000)

    def test_is_ready_requires_core_keys(self) -> None:
        state = DeviceState()
        self.assertFalse(state.is_ready())
        state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))
        state.apply_frame(inbound_byte_frame(K_OPTICAL_MODE_ID, 0, 0))
        state.apply_frame(inbound_byte_frame(K_OPTICAL_MODE_ID, 1, 0))
        state.apply_frame(inbound_float_frame(1016, 0, 1.0))
        state.apply_frame(inbound_float_frame(1027, 0, 1.0))
        self.assertTrue(state.is_ready())

    def test_reset_clears_state(self) -> None:
        state = DeviceState()
        state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))
        state.reset()
        self.assertEqual(state.props, {})
        self.assertFalse(state.meters_received)

    def test_observer_called_on_frame(self) -> None:
        state = DeviceState()
        calls: list[int] = []

        def observer() -> None:
            calls.append(state.frame_count)

        state.add_observer(observer)
        state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))
        self.assertEqual(calls, [1])

    def test_meter_frame_sets_meters_received(self) -> None:
        state = DeviceState()
        data = struct.pack(">HH", K_METERS_ID, 0) + bytes([10, 20])
        state.apply_frame(data)
        self.assertTrue(state.meters_received)
        self.assertEqual(state.meters[0], -5.0)


    def test_meter_frame_sets_last_notify_kind(self) -> None:
        state = DeviceState()
        data = struct.pack(">HH", K_METERS_ID, 0) + bytes([10, 20])
        state.apply_frame(data)
        self.assertEqual(state.last_notify_kind, "meters")

    def test_prop_frame_sets_last_notify_kind(self) -> None:
        state = DeviceState()
        state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))
        self.assertEqual(state.last_notify_kind, "props")

    def test_set_prop_local_sets_last_notify_kind(self) -> None:
        state = DeviceState()
        state.set_prop_local("sample_rate", 0, 48000)
        self.assertEqual(state.last_notify_kind, "local")

    def test_observer_exception_is_logged_not_propagated(self) -> None:
        state = DeviceState()

        def bad_observer() -> None:
            raise RuntimeError("observer failed")

        state.add_observer(bad_observer)
        with self.assertLogs("ultralite_mk5_lib.state", level="ERROR") as logs:
            state.apply_frame(inbound_int32_frame(K_SAMPLE_RATE_ID, 0, 48000))

        self.assertTrue(any("observer failed" in line for line in logs.output))
        self.assertEqual(state.props["sample_rate"][0], 48000)


if __name__ == "__main__":
    unittest.main()
