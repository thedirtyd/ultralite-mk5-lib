"""Encode set-mute entity keys to wire mute frames."""

from __future__ import annotations

from dataclasses import dataclass

from ultralite_mk5_lib.buses import REVERB_BUS_MUTE_INDEX
from ultralite_mk5_lib.entities import EntityRef, resolve_entity
from ultralite_mk5_lib.protocol import (
    make_bus_mute_frame,
    make_mix_mute_frame,
)

_MUTE_ON = frozenset({"mute", "on", "true", "1"})
_MUTE_OFF = frozenset({"unmute", "off", "false", "0"})
DEFAULT_MUTE_VALUE = "mute"


@dataclass(frozen=True, slots=True)
class MuteCommand:
    """Resolved mute write for one entity key."""

    key: str
    prop_key: str
    index: int
    muted: bool
    frame: bytes


def parse_mute_value(token: str) -> bool:
    """Parse mute/on/true/1 or unmute/off/false/0."""
    normalized = token.strip().lower()
    if normalized in _MUTE_ON:
        return True
    if normalized in _MUTE_OFF:
        return False
    raise ValueError(
        f"mute value must be mute/on/true/1 or unmute/off/false/0, got {token!r}"
    )


def mute_target_for_entity(key: str, ref: EntityRef) -> tuple[str, int]:
    """Map entity key + ref to DeviceState prop key and wire index."""
    if ref.kind == "mix_fader":
        return "mix_mute", ref.index
    if ref.kind == "bus_fader":
        if ref.gain_och is None:
            raise ValueError(f"bus fader entity {key!r} has no bus index")
        return "bus_mute", ref.gain_och
    raise ValueError(
        f"{key!r} cannot be muted with set-mute; use MIXBUSFADER_* keys"
    )


def build_mute_frame(prop_key: str, index: int, muted: bool) -> bytes:
    if prop_key == "mix_mute":
        return make_mix_mute_frame(index, muted)
    if prop_key == "bus_mute":
        return make_bus_mute_frame(index, muted)
    raise ValueError(f"unsupported mute property {prop_key!r}")


def resolve_bus_mute_entity(key: str) -> tuple[str, int]:
    """Resolve a MIXBUSFADER_*_OUT entity key to its koBusMute index."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "bus_fader":
        raise ValueError(
            f"{normalized!r} is not an output-bus mute key; "
            "use MIXBUSFADER_*_OUT (see list-entities)"
        )
    if ref.gain_och is None:
        raise ValueError(f"bus fader entity {normalized!r} has no bus index")
    return normalized, ref.gain_och


def resolve_solo_bus_entity(key: str) -> tuple[str, int]:
    """Resolve a MIXBUSFADER_*_OUT entity key to its koBusMute index."""
    normalized, index = resolve_bus_mute_entity(key)
    if index == REVERB_BUS_MUTE_INDEX:
        raise ValueError("Reverb is not a valid target for solo")
    return normalized, index


def prepare_mute_command(key: str, value: str | None = None) -> MuteCommand:
    """Resolve entity key and mute token to a wire frame."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    muted = parse_mute_value(value if value is not None else DEFAULT_MUTE_VALUE)
    prop_key, index = mute_target_for_entity(normalized, ref)
    frame = build_mute_frame(prop_key, index, muted)
    return MuteCommand(
        key=normalized,
        prop_key=prop_key,
        index=index,
        muted=muted,
        frame=frame,
    )


def format_mute_summary(command: MuteCommand) -> str:
    state = "muted" if command.muted else "unmuted"
    return f"Set {command.key} {state}"
