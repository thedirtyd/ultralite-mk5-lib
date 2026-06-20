"""Input gain helpers (Inputs tab) from dev.js / iosetup.js."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultralite_mk5_lib.entity_keys import input_gain_entity_key

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


def _input_gain_channel(name: str, index: int, max_db: float) -> InputGainChannel:
    return InputGainChannel(name, index, max_db, input_gain_entity_key(name))


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
