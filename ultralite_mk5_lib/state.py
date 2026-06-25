"""Live device state from inbound WebSocket frames."""

from __future__ import annotations

import json
import math
import struct
import threading
from collections.abc import Callable
from typing import Any

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES, stereo_bus_muted
from ultralite_mk5_lib.mix_buses import build_mix_bus_fader_matrix
from ultralite_mk5_lib.outputs import build_output_monitoring
from ultralite_mk5_lib.protocol import (
    OPTICAL_INPUT_MODE_INDEX,
    OPTICAL_OUTPUT_MODE_INDEX,
    optical_mode_from_props,
)

# Property id -> (state key, wire type). From dev.js kDevJS.
PROPERTY_TABLE: dict[int, tuple[str, str]] = {
    8: ("api_version", "int16"),
    3: ("device_name", "string"),
    6: ("input_channel_names", "string"),
    7: ("output_channel_names", "string"),
    10: ("sample_rate", "int32"),
    11: ("clock_source", "byte"),
    1000: ("mix_stereo", "byte"),   # kiMixStereo — input channel stereo link
    1016: ("mix_fader", "float"),
    1017: ("mix_pan", "float"),
    1018: ("mix_solo", "byte"),
    1019: ("mix_mute", "byte"),
    1027: ("bus_fader", "float"),
    1028: ("bus_mute", "byte"),
    5001: ("input_gain", "byte"),    # kiGain — analog input trim (Inputs tab)
    5003: ("input_pad", "byte"),     # kPad — mic pre pad (indices 0–1)
    5004: ("input_48v", "byte"),     # k48V — phantom power (indices 0–1)
    5005: ("jack_detect", "byte"),   # kJackDetect — 0=mic, 1=line (read-only)
    5006: ("optical_mode", "byte"),  # kOpticalMode — [0]=input, [1]=output (ADAT/TOSlink)
    5000: ("output_trim", "byte"),   # koTrim — DAC trims (phones, lines)
    5010: ("fpga_patch", "byte"),    # kFPGAPatch — output routing + meter map
    5011: ("main_trim", "byte"),     # kMainTrim — Monitor / main out trim
    5019: ("mute_enable", "byte"),   # kMuteEnable — Monitor hardware mute
}

K_METERS_ID = 6000
NUM_METERS = 128
K_MIN_METER_DB = -127.5

K824_DIVISOR = 0x01000000


def unpack_property_value(prop_type: str, data: bytes) -> Any | None:
    """Decode inbound property payload (bytes from offset 4)."""
    if len(data) < 5:
        return None

    if prop_type == "byte":
        return data[4]
    if prop_type == "int16":
        if len(data) < 6:
            return None
        return struct.unpack(">h", data[4:6])[0]
    if prop_type == "int32":
        if len(data) < 8:
            return None
        return struct.unpack(">i", data[4:8])[0]
    if prop_type == "float":
        if len(data) < 8:
            return None
        raw = struct.unpack(">i", data[4:8])[0]
        return raw / K824_DIVISOR
    if prop_type == "string":
        end = data.find(b"\x00", 4)
        if end == -1:
            end = len(data)
        return data[4:end].decode("utf-8", errors="replace")

    return None


PROXY_MESSAGE_ID = 0xFFFE


def inbound_frame_length(data: bytes, offset: int = 0) -> int | None:
    """Return the byte length of one inbound device message at offset."""
    if offset + 4 > len(data):
        return None

    msg_id = struct.unpack(">H", data[offset : offset + 2])[0]

    if msg_id == K_METERS_ID:
        return len(data) - offset

    if msg_id in (PROXY_MESSAGE_ID, 0xFFFF):
        return len(data) - offset

    if msg_id not in PROPERTY_TABLE:
        return len(data) - offset

    prop_type = PROPERTY_TABLE[msg_id][1]
    if prop_type == "byte":
        return 5
    if prop_type == "int16":
        return 6
    if prop_type in ("int32", "float"):
        return 8
    if prop_type == "string":
        end = data.find(b"\x00", offset + 4)
        if end == -1:
            return len(data) - offset
        return end + 1 - offset

    return len(data) - offset


def iter_inbound_frames(data: bytes):
    """Yield individual device messages from one WebSocket binary payload."""
    offset = 0
    while offset < len(data):
        frame_len = inbound_frame_length(data, offset)
        if frame_len is None or frame_len <= 0:
            yield data[offset:]
            return
        yield data[offset : offset + frame_len]
        offset += frame_len


def decode_meter_peaks(data: bytes) -> list[float]:
    """Convert raw meter bytes to dB (-peak/2 per meterstore.js)."""
    return [-raw / 2.0 for raw in data[4:]]


def linear_gain_to_db(gain: float | None) -> float | None:
    if gain is None:
        return None
    if gain <= 0:
        return float("-inf")
    return 20.0 * math.log10(gain)


def format_db(value: float | None) -> str:
    if value is None:
        return "n/a"
    if math.isinf(value) and value < 0:
        return "-inf"
    return f"{value:.1f}"


# Meter bar maps METER_BAR_MIN_DB..0 dB to ASCII blocks (meterstore.js uses -72 dB floor).
METER_BAR_MIN_DB = -72.0
METER_BAR_WIDTH = 24


METER_BAR_FILLED = "\u2588"  # █ FULL BLOCK
METER_BAR_EMPTY = "\u2591"   # ░ LIGHT SHADE

# Bus faders: -72..+12 dB (warp.js Calc12dBToCtrl24). Trims: -72..0 dB.
FADER_BUS_MIN_DB = -72.0
FADER_BUS_MAX_DB = 12.0
FADER_TRIM_MIN_DB = -72.0
FADER_TRIM_MAX_DB = 0.0


def db_to_fader_position(
    db: float | None,
    *,
    min_db: float,
    max_db: float,
    width: int = METER_BAR_WIDTH,
) -> int | None:
    """Map dB to 0..width-1 for a horizontal fader track (left=quiet, right=loud)."""
    if db is None:
        return None
    if math.isinf(db) and db < 0:
        return 0
    db_clamped = max(min_db, min(max_db, db))
    span = max_db - min_db
    if span <= 0:
        return 0
    fraction = (db_clamped - min_db) / span
    return max(0, min(width - 1, round(fraction * (width - 1))))


def format_fader_bar(position: int | None, width: int = METER_BAR_WIDTH) -> str:
    """Single █ marker on a ░ track at fader position."""
    chars = [METER_BAR_EMPTY] * width
    if position is not None:
        chars[max(0, min(width - 1, position))] = METER_BAR_FILLED
    return "".join(chars)


def format_meter_bar(db: float | None, width: int = METER_BAR_WIDTH) -> str:
    """Horizontal level bar: █ = level, ░ = headroom below METER_BAR_MIN_DB."""
    empty = METER_BAR_EMPTY * width
    if db is None:
        return empty
    if math.isinf(db) and db < 0:
        return empty
    if db <= METER_BAR_MIN_DB:
        return empty
    if db >= 0:
        return METER_BAR_FILLED * width
    fraction = (db - METER_BAR_MIN_DB) / (0.0 - METER_BAR_MIN_DB)
    filled = max(0, min(width, round(fraction * width)))
    return METER_BAR_FILLED * filled + METER_BAR_EMPTY * (width - filled)


def snapshot_to_json(
    snapshot: dict[str, Any],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a state snapshot dict to a JSON string (strict JSON, no NaN)."""
    return json.dumps(_sanitize_snapshot(snapshot), indent=indent)


def _sanitize_snapshot(value: Any) -> Any:
    """Convert snapshot values to strict-JSON-safe forms."""
    if isinstance(value, dict):
        return {k: _sanitize_snapshot(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_snapshot(v) for v in value]
    if isinstance(value, float):
        if math.isinf(value):
            return "-inf" if value < 0 else "inf"
        if math.isnan(value):
            return None
    return value


class DeviceState:
    """
    Accumulates device property updates and meter peaks from WebSocket frames.

    Mirrors DataStore.recv() and MeterStore.set() from the CueMix www sources.
    """

    READY_KEYS = ("sample_rate", "mix_fader", "bus_fader", "optical_mode")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._props: dict[str, dict[int, Any]] = {}
        self._meters: list[float] = [K_MIN_METER_DB] * NUM_METERS
        self._meters_received = False
        self._frame_count = 0
        self._observers: list[Callable[[], None]] = []

    @property
    def props(self) -> dict[str, dict[int, Any]]:
        """Property key -> {index: value} for all received slots."""
        with self._lock:
            return {key: dict(indices) for key, indices in self._props.items()}

    @property
    def meters(self) -> list[float]:
        with self._lock:
            return list(self._meters)

    @property
    def meters_received(self) -> bool:
        with self._lock:
            return self._meters_received

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count

    @property
    def optical_input_mode(self) -> str | None:
        """Optical input mode (adat/toslink), or None until received."""
        with self._lock:
            return optical_mode_from_props(self._props, OPTICAL_INPUT_MODE_INDEX)

    @property
    def optical_output_mode(self) -> str | None:
        """Optical output mode (adat/toslink), or None until received."""
        with self._lock:
            return optical_mode_from_props(self._props, OPTICAL_OUTPUT_MODE_INDEX)

    def add_observer(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked after every applied frame."""
        with self._lock:
            self._observers.append(callback)

    def reset(self) -> None:
        """Clear accumulated state after disconnect (mirrors CueMix DatastoreReset)."""
        with self._lock:
            self._props.clear()
            self._meters = [K_MIN_METER_DB] * NUM_METERS
            self._meters_received = False
            self._frame_count = 0
            self._notify_observers()

    def apply_frame(self, data: bytes) -> None:
        """Apply one inbound WebSocket payload to live state."""
        if len(data) < 2:
            return

        for frame in iter_inbound_frames(data):
            self._apply_single_frame(frame)

    def set_bus_mute_local(self, index: int, muted: bool) -> None:
        """Update koBusMute in local state (used after outbound mute commands)."""
        self.set_prop_local("bus_mute", index, 1 if muted else 0)

    def set_prop_local(self, prop_key: str, index: int, value: Any) -> None:
        """Update one props slot in local state (used after outbound commands)."""
        with self._lock:
            self._props.setdefault(prop_key, {})[index] = value
            self._notify_observers()

    def _apply_single_frame(self, data: bytes) -> None:
        if len(data) < 2:
            return

        msg_id = struct.unpack(">H", data[0:2])[0]

        with self._lock:
            self._frame_count += 1

            if msg_id == K_METERS_ID:
                peaks = decode_meter_peaks(data)
                n = min(len(peaks), NUM_METERS)
                self._meters[:n] = peaks[:n]
                self._meters_received = True
            elif msg_id in PROPERTY_TABLE:
                if len(data) < 4:
                    self._notify_observers()
                    return
                index = struct.unpack(">H", data[2:4])[0]
                key, prop_type = PROPERTY_TABLE[msg_id]
                value = unpack_property_value(prop_type, data)
                if value is not None:
                    self._props.setdefault(key, {})[index] = value

            self._notify_observers()

    def _notify_observers(self) -> None:
        self._condition.notify_all()
        for callback in self._observers:
            try:
                callback()
            except Exception:
                pass

    def wait_for(
        self,
        predicate: Callable[["DeviceState"], bool],
        timeout: float,
    ) -> bool:
        """Block until predicate(self) is true. Returns False on timeout."""
        with self._condition:
            if predicate(self):
                return True
            return self._condition.wait_for(lambda: predicate(self), timeout=timeout)

    def is_ready(self) -> bool:
        """True once core mix/trim props needed for get-state have arrived."""
        with self._lock:
            return all(key in self._props for key in self.READY_KEYS)

    def wait_until_ready(self, timeout: float) -> bool:
        """Block until is_ready(). Returns False on timeout."""
        return self.wait_for(lambda state: state.is_ready(), timeout)

    def snapshot(self) -> dict[str, Any]:
        """Thread-safe structured copy of current state."""
        with self._lock:
            device_name = self._scalar("device_name", 0)
            sample_rate = self._scalar("sample_rate", 0)
            api_version = self._scalar("api_version", 0)

            bus_faders: dict[str, float | None] = {}
            bus_mutes: dict[str, bool | None] = {}
            bus_mute_indices = self._props.get("bus_mute", {})
            for name, index in MIX_BUS_MUTE_INDICES.items():
                bus_faders[name] = self._scalar("bus_fader", index)
                bus_mutes[name] = stereo_bus_muted(bus_mute_indices, index)

            props_copy = {key: dict(indices) for key, indices in self._props.items()}
            optical_input_mode = props_copy.get("optical_mode", {}).get(0)
            optical_input_mode_name = optical_mode_from_props(
                props_copy,
                OPTICAL_INPUT_MODE_INDEX,
            )
            optical_output_mode_name = optical_mode_from_props(
                props_copy,
                OPTICAL_OUTPUT_MODE_INDEX,
            )
            mix_bus_fader_matrix = build_mix_bus_fader_matrix(
                props_copy,
                sample_rate=sample_rate,
                optical_input_mode=optical_input_mode,
            )
            output_monitoring = build_output_monitoring(
                props_copy,
                self._meters,
                meters_received=self._meters_received,
            )

            return {
                "device_name": device_name,
                "sample_rate": sample_rate,
                "api_version": api_version,
                "optical_input_mode": optical_input_mode_name,
                "optical_output_mode": optical_output_mode_name,
                "bus_faders": bus_faders,
                "bus_mutes": bus_mutes,
                "mix_bus_fader_matrix": mix_bus_fader_matrix,
                "output_monitoring": output_monitoring,
                "meters": list(self._meters),
                "meters_received": self._meters_received,
                "props": props_copy,
                "frame_count": self._frame_count,
            }

    def snapshot_json(self, *, indent: int | None = 2) -> str:
        """Thread-safe JSON serialization of the get-state style report."""
        from ultralite_mk5_lib.report import state_report_to_json

        return state_report_to_json(self.snapshot(), indent=indent)

    def _scalar(self, key: str, index: int) -> Any | None:
        return self._props.get(key, {}).get(index)
