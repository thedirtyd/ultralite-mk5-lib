"""Encode set-pan entity keys to wire pan frames."""

from __future__ import annotations

from dataclasses import dataclass

from ultralite_mk5_lib.entities import resolve_entity
from ultralite_mk5_lib.protocol import make_mix_pan_frame

PAN_MIN = 0.0
PAN_MAX = 1.0
PAN_CENTER = 0.5
DEFAULT_PAN_VALUE = "center"

_PAN_ALIASES = {
    "center": PAN_CENTER,
    "c": PAN_CENTER,
    "l": PAN_MIN,
    "left": PAN_MIN,
    "r": PAN_MAX,
    "right": PAN_MAX,
}


@dataclass(frozen=True, slots=True)
class PanCommand:
    """Resolved pan write for one mix crosspoint entity key."""

    key: str
    prop_key: str
    index: int
    pan: float
    frame: bytes


def validate_mix_pan(value: float) -> float:
    """Validate pan is within CueMix 0.0 (L) .. 1.0 (R) range."""
    try:
        pan = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"pan must be a number between {PAN_MIN} and {PAN_MAX}, got {value!r}"
        ) from err
    if pan < PAN_MIN or pan > PAN_MAX:
        raise ValueError(f"pan must be between {PAN_MIN} and {PAN_MAX}, got {pan}")
    return pan


def parse_pan_value(token: str) -> float:
    """Parse numeric pan or aliases center/L/R."""
    normalized = token.strip().lower()
    if normalized in _PAN_ALIASES:
        return _PAN_ALIASES[normalized]
    try:
        return validate_mix_pan(float(normalized))
    except ValueError as err:
        raise ValueError(
            f"pan value must be {PAN_MIN}..{PAN_MAX}, center, L, or R, got {token!r}"
        ) from err


def resolve_mix_pan_entity(key: str) -> tuple[str, int]:
    """Resolve a MIXBUSFADER_* crosspoint entity key to its kiMixPan flat index."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "mix_fader":
        raise ValueError(
            f"{normalized!r} is not a mix crosspoint pan key; "
            "use MIXBUSFADER_* input/host/reverb crosspoint keys (not *_OUT)"
        )
    return normalized, ref.index


def prepare_pan_command(key: str, value: str | float | None = None) -> PanCommand:
    """Resolve entity key and pan token to a wire frame."""
    normalized, index = resolve_mix_pan_entity(key)
    if value is None:
        pan = parse_pan_value(DEFAULT_PAN_VALUE)
    elif isinstance(value, (int, float)):
        pan = validate_mix_pan(float(value))
    else:
        pan = parse_pan_value(str(value))
    frame = make_mix_pan_frame(index, pan)
    return PanCommand(
        key=normalized,
        prop_key="mix_pan",
        index=index,
        pan=pan,
        frame=frame,
    )


def format_pan_summary(command: PanCommand) -> str:
    return f"Set {command.key} pan {command.pan}"
