"""Shared fixtures for ultralite-mk5-lib unit tests."""

from __future__ import annotations

import struct
from typing import Any

from ultralite_mk5_lib.meters import OPTICAL_MODE_ADAT
from ultralite_mk5_lib.mix_buses import mix_fader_index
from ultralite_mk5_lib.state import K_MIN_METER_DB, NUM_METERS


def assert_frame_header(frame: bytes, prop_id: int, index: int) -> None:
    """Assert the first four bytes of an outbound property frame."""
    msg_id, idx = struct.unpack(">HH", frame[:4])
    if msg_id != prop_id or idx != index:
        raise AssertionError(
            f"expected prop_id={prop_id} index={index}, got {msg_id} {idx}"
        )


def inbound_byte_frame(prop_id: int, index: int, value: int) -> bytes:
    """Build an inbound device property frame (no length prefix)."""
    return struct.pack(">HHB", prop_id, index, value & 0xFF)


def inbound_int32_frame(prop_id: int, index: int, value: int) -> bytes:
    return struct.pack(">HHi", prop_id, index, value)


def inbound_float_frame(prop_id: int, index: int, gain: float) -> bytes:
    from ultralite_mk5_lib.protocol import gain_to_824

    return struct.pack(">HHi", prop_id, index, gain_to_824(gain))


def minimal_props(**overrides: dict[int, Any]) -> dict[str, dict[int, Any]]:
    """Synthetic props dict with enough data for matrix and report builders."""
    props: dict[str, dict[int, Any]] = {
        "mix_fader": {
            mix_fader_index(0, 10): 0.75,
            mix_fader_index(2, 0): 1.0,
        },
        "mix_mute": {mix_fader_index(0, 10): 0},
        "mix_stereo": {0: 1},
        "bus_fader": {0: 1.0, 10: 0.5},
        "bus_mute": {0: 0, 1: 0, 10: 0, 11: 0},
        "optical_mode": {0: OPTICAL_MODE_ADAT, 1: OPTICAL_MODE_ADAT},
        "input_gain": {0: 12, 2: 6},
        "input_48v": {0: 1, 1: 0},
        "input_pad": {0: 0, 1: 1},
        "jack_detect": {0: 0, 1: 1},
        "output_trim": {6: 0, 8: 6, 10: 6},
        "main_trim": {0: 0},
        "mute_enable": {0: 0},
        "ab_enable": {0: 0},
        "a_enable": {0: 0},
        "b_enable": {0: 0},
        "fpga_patch": {38: 46, 39: 47, 42: 64, 43: 65},
    }
    for key, indices in overrides.items():
        if isinstance(indices, dict):
            props.setdefault(key, {}).update(indices)
        else:
            props[key] = indices  # type: ignore[assignment]
    return props


def minimal_snapshot(**overrides: Any) -> dict[str, Any]:
    """Synthetic DeviceState.snapshot()-shaped dict for report tests."""
    props = overrides.pop("props", None) or minimal_props()
    snap: dict[str, Any] = {
        "device_name": "UltraLite mk5",
        "sample_rate": 48000,
        "api_version": 1,
        "optical_input_mode": "adat",
        "optical_output_mode": "adat",
        "bus_faders": {"main 1-2": 1.0},
        "bus_mutes": {"main 1-2": False},
        "meters": [K_MIN_METER_DB] * NUM_METERS,
        "meters_received": True,
        "props": props,
        "frame_count": 1,
    }
    snap.update(overrides)
    return snap
