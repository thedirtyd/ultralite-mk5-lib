"""Encode set-solo entity keys to wire solo frames."""

from __future__ import annotations

from dataclasses import dataclass

from ultralite_mk5_lib.entities import resolve_entity
from ultralite_mk5_lib.protocol import make_mix_solo_frame

_SOLO_ON = frozenset({"solo", "on", "true", "1"})
_SOLO_OFF = frozenset({"unsolo", "off", "false", "0"})
DEFAULT_SOLO_VALUE = "solo"


@dataclass(frozen=True, slots=True)
class SoloCommand:
    """Resolved solo write for one mix crosspoint entity key."""

    key: str
    prop_key: str
    index: int
    soloed: bool
    frame: bytes


def parse_solo_value(token: str) -> bool:
    """Parse solo/on/true/1 or unsolo/off/false/0."""
    normalized = token.strip().lower()
    if normalized in _SOLO_ON:
        return True
    if normalized in _SOLO_OFF:
        return False
    raise ValueError(
        f"solo value must be solo/on/true/1 or unsolo/off/false/0, got {token!r}"
    )


def resolve_mix_solo_entity(key: str) -> tuple[str, int]:
    """Resolve a MIXBUSFADER_* crosspoint entity key to its kiMixSolo flat index."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "mix_fader":
        raise ValueError(
            f"{normalized!r} is not a mix crosspoint solo key; "
            "use MIXBUSFADER_* input/host/reverb crosspoint keys (not *_OUT)"
        )
    return normalized, ref.index


def resolve_clear_mix_solo_entity(key: str) -> tuple[str, int]:
    """Resolve a MIXBUSFADER_*_OUT entity key to its koBusMute / gainOCh index."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "bus_fader":
        raise ValueError(
            f"{normalized!r} is not an output-bus key; "
            "use MIXBUSFADER_*_OUT (see list-entities)"
        )
    if ref.gain_och is None:
        raise ValueError(f"bus fader entity {normalized!r} has no bus index")
    return normalized, ref.gain_och


def prepare_solo_command(key: str, value: str | None = None) -> SoloCommand:
    """Resolve entity key and solo token to a wire frame."""
    normalized, index = resolve_mix_solo_entity(key)
    soloed = parse_solo_value(value if value is not None else DEFAULT_SOLO_VALUE)
    frame = make_mix_solo_frame(index, soloed)
    return SoloCommand(
        key=normalized,
        prop_key="mix_solo",
        index=index,
        soloed=soloed,
        frame=frame,
    )


def format_solo_summary(command: SoloCommand) -> str:
    state = "soloed" if command.soloed else "unsoloed"
    return f"Set {command.key} {state}"
