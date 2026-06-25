"""Input gain helpers (Inputs tab) from dev.js / iosetup.js."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultralite_mk5_lib.entity_keys import (
    input_48v_entity_key,
    input_gain_entity_key,
    input_pad_entity_key,
)

# kiGain indices and per-channel max (iosetup.js ctrlInfo).
MIC_GAIN_MAX_DB = 74.0
LINE_GAIN_MAX_DB = 20.0


@dataclass(frozen=True, slots=True)
class InputGainChannel:
    """One analog input gain knob on the Inputs tab."""

    name: str
    index: int
    max_db: float
    key: str


@dataclass(frozen=True, slots=True)
class MicPreChannel:
    """Mic preamp controls (48V, pad) for Mic/Line In 1–2."""

    name: str
    index: int
    key_48v: str
    key_pad: str


def _input_gain_channel(name: str, index: int, max_db: float) -> InputGainChannel:
    return InputGainChannel(name, index, max_db, input_gain_entity_key(name))


def _mic_pre_channel(name: str, index: int) -> MicPreChannel:
    return MicPreChannel(
        name,
        index,
        input_48v_entity_key(name),
        input_pad_entity_key(name),
    )


# Order matches iosetup.js Inputs view (Mic 1-2, then Line 3-8).
INPUT_GAIN_CHANNELS: tuple[InputGainChannel, ...] = (
    _input_gain_channel("Mic/Line In 1", 0, MIC_GAIN_MAX_DB),
    _input_gain_channel("Mic/Line In 2", 1, MIC_GAIN_MAX_DB),
    _input_gain_channel("Line In 3", 2, LINE_GAIN_MAX_DB),
    _input_gain_channel("Line In 4", 3, LINE_GAIN_MAX_DB),
    _input_gain_channel("Line In 5", 4, LINE_GAIN_MAX_DB),
    _input_gain_channel("Line In 6", 5, LINE_GAIN_MAX_DB),
    _input_gain_channel("Line In 7", 6, LINE_GAIN_MAX_DB),
    _input_gain_channel("Line In 8", 7, LINE_GAIN_MAX_DB),
)

MIC_PRE_CHANNELS: tuple[MicPreChannel, ...] = (
    _mic_pre_channel("Mic/Line In 1", 0),
    _mic_pre_channel("Mic/Line In 2", 1),
)


def input_gain_byte_to_db(value: int | None) -> float | None:
    """Convert kiGain byte to dB (stored as 0..max positive gain)."""
    if value is None:
        return None
    return float(value)


def build_input_gains(props: dict[str, dict[int, Any]]) -> list[tuple[str, float | None, float, float]]:
    """Rows for Input Gain table: (name, dB, min_db, max_db)."""
    gains = props.get("input_gain", {})
    rows: list[tuple[str, float | None, float, float]] = []
    for ch in INPUT_GAIN_CHANNELS:
        rows.append(
            (
                ch.name,
                input_gain_byte_to_db(gains.get(ch.index)),
                0.0,
                ch.max_db,
            )
        )
    return rows


def _byte_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _jack_mode(value: Any) -> str | None:
    if value is None:
        return None
    return "mic" if int(value) == 0 else "line"


def build_mic_pre_state(
    props: dict[str, dict[int, Any]],
) -> list[dict[str, Any]]:
    """Per-mic-pre rows: name, 48v, pad, jack mode."""
    input_48v = props.get("input_48v", {})
    input_pad = props.get("input_pad", {})
    jack_detect = props.get("jack_detect", {})
    rows: list[dict[str, Any]] = []
    for ch in MIC_PRE_CHANNELS:
        rows.append(
            {
                "name": ch.name,
                "index": ch.index,
                "key_48v": ch.key_48v,
                "key_pad": ch.key_pad,
                "48v": _byte_bool(input_48v.get(ch.index)),
                "pad": _byte_bool(input_pad.get(ch.index)),
                "jack": _jack_mode(jack_detect.get(ch.index)),
            }
        )
    return rows
