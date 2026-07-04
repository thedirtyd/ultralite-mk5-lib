"""Wire protocol helpers for MOTU Gen5 / UltraLite mk5 WebSocket control."""

from __future__ import annotations

import struct
from typing import Any

from ultralite_mk5_lib.meters import OPTICAL_MODE_ADAT, OPTICAL_MODE_TOSLINK

# kSampleRate in dev.js — id 10, index 0, kTInt32
K_SAMPLE_RATE_ID = 10

# koBusMute in dev.js — id 1028, kTByte, one entry per mix output channel
K_BUS_MUTE_ID = 1028

# kiMixStereo in dev.js — id 1000, kTByte
K_MIX_STEREO_ID = 1000

# kiMixFader / koBusFader in dev.js — id 1016 / 1027, kTFloat (8.24)
K_MIX_FADER_ID = 1016
K_BUS_FADER_ID = 1027

# kiGain / kPad / k48V / koTrim / kMainTrim in dev.js
K_INPUT_GAIN_ID = 5001
K_INPUT_PAD_ID = 5003
K_INPUT_48V_ID = 5004
K_OUTPUT_TRIM_ID = 5000
K_MAIN_TRIM_ID = 5011

# kiMixSolo in dev.js
K_MIX_SOLO_ID = 1018

# kiMixMute in dev.js
K_MIX_MUTE_ID = 1019

# kiEQ* / koEQ* in dev.js
K_INPUT_EQ_MODE_ID = 1002
K_INPUT_EQ_BYPASS_ID = 1003
K_INPUT_EQ_FREQ_ID = 1004
K_INPUT_EQ_GAIN_ID = 1005
K_INPUT_EQ_Q_ID = 1006
K_BUS_EQ_MODE_ID = 1022
K_BUS_EQ_BYPASS_ID = 1023
K_BUS_EQ_FREQ_ID = 1024
K_BUS_EQ_GAIN_ID = 1025
K_BUS_EQ_Q_ID = 1026

# kOpticalMode in dev.js — id 5006, kTByte; [0]=input, [1]=output (ADAT/TOSlink)
K_OPTICAL_MODE_ID = 5006
OPTICAL_INPUT_MODE_INDEX = 0
OPTICAL_OUTPUT_MODE_INDEX = 1

K824_DIVISOR = 0x01000000

VALID_SAMPLE_RATES = (44100, 48000, 88200, 96000, 176400, 192000)

_KHZ_THRESHOLD = 1000


def sample_rate_choices_text() -> str:
    khz = ", ".join(f"{rate / 1000:g}" for rate in VALID_SAMPLE_RATES)
    hz = ", ".join(str(rate) for rate in VALID_SAMPLE_RATES)
    return f"{khz} kHz or {hz} Hz"


def parse_sample_rate(value: str | float | int) -> int:
    """Parse sample rate from Hz (44100) or kHz (44.1, 48, 192)."""
    try:
        rate = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid sample rate {value!r}") from exc

    hz = int(round(rate)) if rate >= _KHZ_THRESHOLD else int(round(rate * 1000))
    if hz not in VALID_SAMPLE_RATES:
        raise ValueError(
            f"sample rate must be one of {sample_rate_choices_text()}, got {value!r}"
        )
    return hz


_OPTICAL_MODE_NAMES = {
    OPTICAL_MODE_ADAT: "adat",
    OPTICAL_MODE_TOSLINK: "toslink",
}


def optical_mode_choices_text() -> str:
    return "adat, toslink"


def parse_optical_mode(value: str) -> int:
    """Parse optical input/output mode from adat or toslink."""
    normalized = value.strip().lower()
    for wire, name in _OPTICAL_MODE_NAMES.items():
        if normalized == name:
            return wire
    raise ValueError(
        f"optical mode must be one of {optical_mode_choices_text()}, got {value!r}"
    )


def format_optical_mode(mode: int) -> str:
    """Format wire optical mode value as adat or toslink."""
    try:
        return _OPTICAL_MODE_NAMES[mode]
    except KeyError as exc:
        raise ValueError(f"unknown optical mode wire value {mode}") from exc


def normalize_optical_mode(value: str) -> str:
    """Parse and return canonical optical mode name (adat or toslink)."""
    return format_optical_mode(parse_optical_mode(value))


def optical_mode_wire_from_props(
    props: dict[str, dict[int, Any]],
    index: int,
) -> int | None:
    """Return raw kOpticalMode wire value for one index, or None until received."""
    return props.get("optical_mode", {}).get(index)


def optical_mode_from_props(
    props: dict[str, dict[int, Any]],
    index: int,
) -> str | None:
    """Return adat/toslink for one kOpticalMode index, or None until received."""
    wire = optical_mode_wire_from_props(props, index)
    if wire is None:
        return None
    return format_optical_mode(wire)


def optical_input_mode_wire_from_snap(snap: dict[str, Any]) -> int | None:
    return optical_mode_wire_from_props(snap.get("props", {}), OPTICAL_INPUT_MODE_INDEX)


def optical_output_mode_wire_from_snap(snap: dict[str, Any]) -> int | None:
    return optical_mode_wire_from_props(snap.get("props", {}), OPTICAL_OUTPUT_MODE_INDEX)


def optical_input_mode_from_snap(snap: dict[str, Any]) -> str | None:
    return optical_mode_from_props(snap.get("props", {}), OPTICAL_INPUT_MODE_INDEX)


def optical_output_mode_from_snap(snap: dict[str, Any]) -> str | None:
    return optical_mode_from_props(snap.get("props", {}), OPTICAL_OUTPUT_MODE_INDEX)


LOCALHOSTS = frozenset({"127.0.0.1", "localhost"})


def build_ws_url(target: str, port: int | None, serial: str | None) -> str:
    """Build ws:// URL from a full URL or host + optional port/serial."""
    if target.startswith("ws://") or target.startswith("wss://"):
        return target

    host = target
    if port is None:
        port = 1281 if serial or host.lower() in LOCALHOSTS else 1280

    url = f"ws://{host}:{port}"
    if serial:
        url += f"/{serial.lstrip('/')}"
    return url


def make_int32_property(prop_id: int, index: int, value: int) -> bytes:
    """Build outbound device message (CreateDeviceMessage / kTInt32)."""
    return struct.pack(">HHHi", prop_id, index, 4, value)


def make_byte_property(prop_id: int, index: int, value: int) -> bytes:
    """Build outbound device message (CreateDeviceMessage / kTByte)."""
    return struct.pack(">HHHB", prop_id, index, 1, value & 0xFF)


def gain_to_824(gain: float) -> int:
    """Encode linear gain as 8.24 fixed point (CueMix To824)."""
    return int(round(gain * K824_DIVISOR))


def make_float_property(prop_id: int, index: int, gain: float) -> bytes:
    """Build outbound device message (CreateDeviceMessage / kTFloat)."""
    return struct.pack(">HHHi", prop_id, index, 4, gain_to_824(gain))


def make_mix_fader_frame(index: int, gain: float) -> bytes:
    return make_float_property(K_MIX_FADER_ID, index, gain)


def make_mix_stereo_frame(index: int, stereo: bool) -> bytes:
    return make_byte_property(K_MIX_STEREO_ID, index, 1 if stereo else 0)


def make_bus_fader_frame(index: int, gain: float) -> bytes:
    return make_float_property(K_BUS_FADER_ID, index, gain)


def make_input_gain_frame(index: int, value: int) -> bytes:
    return make_byte_property(K_INPUT_GAIN_ID, index, value)


def make_input_pad_frame(index: int, on: bool) -> bytes:
    return make_byte_property(K_INPUT_PAD_ID, index, 1 if on else 0)


def make_input_48v_frame(index: int, on: bool) -> bytes:
    return make_byte_property(K_INPUT_48V_ID, index, 1 if on else 0)


def make_output_trim_frame(index: int, value: int) -> bytes:
    return make_byte_property(K_OUTPUT_TRIM_ID, index, value)


def make_main_trim_frame(index: int, value: int) -> bytes:
    return make_byte_property(K_MAIN_TRIM_ID, index, value)


def make_sample_rate_frame(rate: int) -> bytes:
    return make_int32_property(K_SAMPLE_RATE_ID, 0, rate)


def make_optical_mode_frame(index: int, mode: int) -> bytes:
    return make_byte_property(K_OPTICAL_MODE_ID, index, mode)


def make_bus_mute_frame(index: int, muted: bool) -> bytes:
    return make_byte_property(K_BUS_MUTE_ID, index, 1 if muted else 0)


def make_mix_solo_frame(index: int, soloed: bool) -> bytes:
    return make_byte_property(K_MIX_SOLO_ID, index, 1 if soloed else 0)


def make_mix_mute_frame(index: int, muted: bool) -> bytes:
    return make_byte_property(K_MIX_MUTE_ID, index, 1 if muted else 0)


def make_input_eq_mode_frame(index: int, mode: int) -> bytes:
    return make_byte_property(K_INPUT_EQ_MODE_ID, index, mode)


def make_input_eq_bypass_frame(index: int, bypass: int) -> bytes:
    return make_byte_property(K_INPUT_EQ_BYPASS_ID, index, bypass)


def make_input_eq_freq_frame(index: int, hz: int) -> bytes:
    return make_int32_property(K_INPUT_EQ_FREQ_ID, index, hz)


def make_input_eq_gain_frame(index: int, db: float) -> bytes:
    return make_float_property(K_INPUT_EQ_GAIN_ID, index, db)


def make_input_eq_q_frame(index: int, q: float) -> bytes:
    return make_float_property(K_INPUT_EQ_Q_ID, index, q)


def make_bus_eq_mode_frame(index: int, mode: int) -> bytes:
    return make_byte_property(K_BUS_EQ_MODE_ID, index, mode)


def make_bus_eq_bypass_frame(index: int, bypass: int) -> bytes:
    return make_byte_property(K_BUS_EQ_BYPASS_ID, index, bypass)


def make_bus_eq_freq_frame(index: int, hz: int) -> bytes:
    return make_int32_property(K_BUS_EQ_FREQ_ID, index, hz)


def make_bus_eq_gain_frame(index: int, db: float) -> bytes:
    return make_float_property(K_BUS_EQ_GAIN_ID, index, db)


def make_bus_eq_q_frame(index: int, q: float) -> bytes:
    return make_float_property(K_BUS_EQ_Q_ID, index, q)
