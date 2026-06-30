"""Encode 48V phantom power and pad entity keys to wire frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultralite_mk5_lib.entities import EntityRef, resolve_entity
from ultralite_mk5_lib.protocol import make_input_48v_frame, make_input_pad_frame

_TOGGLE_ON = frozenset({"on", "true", "1"})
_TOGGLE_OFF = frozenset({"off", "false", "0"})
DEFAULT_TOGGLE_VALUE = "on"

_MIC_PRE_MAX_INDEX = 1


@dataclass(frozen=True, slots=True)
class InputToggleCommand:
    """Resolved 48V or pad write for one entity key."""

    key: str
    prop_key: str
    index: int
    on: bool
    frame: bytes


def parse_toggle_value(token: str) -> bool:
    """Parse on/true/1 or off/false/0."""
    normalized = token.strip().lower()
    if normalized in _TOGGLE_ON:
        return True
    if normalized in _TOGGLE_OFF:
        return False
    raise ValueError(
        f"toggle value must be on/true/1 or off/false/0, got {token!r}"
    )


def _validate_mic_pre_index(key: str, index: int) -> None:
    if index > _MIC_PRE_MAX_INDEX:
        raise ValueError(
            f"{key!r} is only valid for Mic In 1–2 (indices 0–1)"
        )


def _validate_mic_jack(
    key: str,
    index: int,
    jack_detect: dict[int, Any] | None,
) -> None:
    if jack_detect is None:
        return
    if jack_detect.get(index, 0) == 1:
        raise ValueError(
            f"{key!r} cannot be changed while a line/instrument jack is detected"
        )


def _toggle_target_for_entity(ref: EntityRef) -> tuple[str, int]:
    if ref.kind == "input_48v":
        return "input_48v", ref.index
    if ref.kind == "input_pad":
        return "input_pad", ref.index
    raise ValueError(f"entity {ref.display!r} is not an input 48V or pad key")


def build_input_toggle_frame(prop_key: str, index: int, on: bool) -> bytes:
    if prop_key == "input_48v":
        return make_input_48v_frame(index, on)
    if prop_key == "input_pad":
        return make_input_pad_frame(index, on)
    raise ValueError(f"unsupported input toggle property {prop_key!r}")


def prepare_48v_command(
    key: str,
    value: str | None = None,
    *,
    jack_detect: dict[int, Any] | None = None,
) -> InputToggleCommand:
    """Resolve INPUT48V_* entity key and toggle token to a wire frame."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "input_48v":
        raise ValueError(f"{normalized!r} is not an INPUT48V_* entity key")
    _validate_mic_pre_index(normalized, ref.index)
    _validate_mic_jack(normalized, ref.index, jack_detect)
    on = parse_toggle_value(value if value is not None else DEFAULT_TOGGLE_VALUE)
    prop_key, index = _toggle_target_for_entity(ref)
    frame = build_input_toggle_frame(prop_key, index, on)
    return InputToggleCommand(
        key=normalized,
        prop_key=prop_key,
        index=index,
        on=on,
        frame=frame,
    )


def prepare_pad_command(
    key: str,
    value: str | None = None,
    *,
    jack_detect: dict[int, Any] | None = None,
) -> InputToggleCommand:
    """Resolve INPUTPAD_* entity key and toggle token to a wire frame."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "input_pad":
        raise ValueError(f"{normalized!r} is not an INPUTPAD_* entity key")
    _validate_mic_pre_index(normalized, ref.index)
    _validate_mic_jack(normalized, ref.index, jack_detect)
    on = parse_toggle_value(value if value is not None else DEFAULT_TOGGLE_VALUE)
    prop_key, index = _toggle_target_for_entity(ref)
    frame = build_input_toggle_frame(prop_key, index, on)
    return InputToggleCommand(
        key=normalized,
        prop_key=prop_key,
        index=index,
        on=on,
        frame=frame,
    )


def format_input_toggle_summary(command: InputToggleCommand) -> str:
    label = "48V" if command.prop_key == "input_48v" else "pad"
    state = "on" if command.on else "off"
    return f"Set {command.key} {label} {state}"
