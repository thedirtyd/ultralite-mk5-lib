"""Importable entity constants, display names, and wire-index resolvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES, resolve_bus_stereo_left_gain_och
from ultralite_mk5_lib.entity_keys import mix_bus_fader_entity_key
from ultralite_mk5_lib.inputs import INPUT_GAIN_CHANNELS, MIC_PRE_CHANNELS
from ultralite_mk5_lib.meters import METER_SLOTS
from ultralite_mk5_lib.mix_buses import (
    BUS_HOST_GAIN_ICH,
    FULL_MIX_MATRIX_COLUMNS,
    MIX_INPUT_CHANNELS,
    STEREO_CAPABLE_MAX_GAIN_ICH,
    mix_fader_index,
)
from ultralite_mk5_lib.outputs import MONITOR_TRIM_CHANNELS, OUTPUT_TRIM_CHANNELS

EntityKind = Literal[
    "meter",
    "mix_fader",
    "mix_input",
    "bus_fader",
    "input_gain",
    "input_48v",
    "input_pad",
    "output_trim",
    "main_trim",
]

_KIND_TO_PROP: dict[EntityKind, str | None] = {
    "meter": None,
    "mix_fader": "mix_fader",
    "bus_fader": "bus_fader",
    "input_gain": "input_gain",
    "input_48v": "input_48v",
    "input_pad": "input_pad",
    "output_trim": "output_trim",
    "main_trim": "main_trim",
}


@dataclass(frozen=True, slots=True)
class EntityRef:
    """Wire target for one importable entity constant."""

    kind: EntityKind
    index: int
    display: str
    gain_ich: int | None = None
    gain_och: int | None = None


def _register(
    registry: dict[str, EntityRef],
    key: str,
    ref: EntityRef,
) -> None:
    if key in registry:
        raise ValueError(f"duplicate entity key {key!r}")
    registry[key] = ref


def _build_registry() -> dict[str, EntityRef]:
    registry: dict[str, EntityRef] = {}

    for entry in METER_SLOTS:
        _register(
            registry,
            entry.key,
            EntityRef("meter", entry.slot, entry.name),
        )

    for ch in INPUT_GAIN_CHANNELS:
        _register(
            registry,
            ch.key,
            EntityRef("input_gain", ch.index, ch.name),
        )

    for ch in MIC_PRE_CHANNELS:
        _register(
            registry,
            ch.key_48v,
            EntityRef("input_48v", ch.index, f"{ch.name} 48V"),
        )
        _register(
            registry,
            ch.key_pad,
            EntityRef("input_pad", ch.index, f"{ch.name} Pad"),
        )

    for ch in OUTPUT_TRIM_CHANNELS:
        _register(
            registry,
            ch.key,
            EntityRef("output_trim", ch.trim_index, ch.name),
        )

    for ch in MONITOR_TRIM_CHANNELS:
        kind: EntityKind = "main_trim" if ch.prop == "main_trim" else "output_trim"
        _register(
            registry,
            ch.key,
            EntityRef(kind, ch.index, ch.name),
        )

    for ch in MIX_INPUT_CHANNELS:
        _register(
            registry,
            ch.key,
            EntityRef("mix_input", ch.gain_ich, ch.name, gain_ich=ch.gain_ich),
        )

    for bus_name, gain_och in MIX_BUS_MUTE_INDICES.items():
        for col in FULL_MIX_MATRIX_COLUMNS:
            key = mix_bus_fader_entity_key(bus_name, col.label)
            if col.kind == "out":
                _register(
                    registry,
                    key,
                    EntityRef("bus_fader", gain_och, col.label, gain_och=gain_och),
                )
            elif col.kind == "host":
                if col.gain_ich is None:
                    continue
                if col.native_och is not None and gain_och != col.native_och:
                    continue
                _register(
                    registry,
                    key,
                    EntityRef(
                        "mix_fader",
                        mix_fader_index(col.gain_ich, gain_och),
                        col.label,
                        gain_ich=col.gain_ich,
                        gain_och=gain_och,
                    ),
                )
            elif col.kind in ("input", "reverb"):
                ich = col.gain_ich
                if ich is None:
                    continue
                _register(
                    registry,
                    key,
                    EntityRef(
                        "mix_fader",
                        mix_fader_index(ich, gain_och),
                        col.label,
                        gain_ich=ich,
                        gain_och=gain_och,
                    ),
                )

    for bus_name, gain_och in MIX_BUS_MUTE_INDICES.items():
        host_ich = BUS_HOST_GAIN_ICH.get(bus_name)
        if host_ich is None:
            continue
        _register(
            registry,
            mix_bus_fader_entity_key(bus_name, "Host L"),
            EntityRef(
                "mix_fader",
                mix_fader_index(host_ich, gain_och),
                "Host L",
                gain_ich=host_ich,
                gain_och=gain_och,
            ),
        )
        _register(
            registry,
            mix_bus_fader_entity_key(bus_name, "Host R"),
            EntityRef(
                "mix_fader",
                mix_fader_index(host_ich + 1, gain_och),
                "Host R",
                gain_ich=host_ich + 1,
                gain_och=gain_och,
            ),
        )

    return registry


ENTITY_REGISTRY: dict[str, EntityRef] = _build_registry()
DISPLAY_NAMES: dict[str, str] = {key: ref.display for key, ref in ENTITY_REGISTRY.items()}
ALL_ENTITY_KEYS: tuple[str, ...] = tuple(sorted(ENTITY_REGISTRY))

SOLO_OUTPUT_BUS_KEYS: tuple[str, ...] = tuple(
    key
    for key, ref in sorted(ENTITY_REGISTRY.items())
    if ref.kind == "bus_fader" and key != "MIXBUSFADER_REVERB_OUT"
)

SET_SOLO_ENTITY_KEYS: tuple[str, ...] = tuple(
    key
    for key, ref in sorted(ENTITY_REGISTRY.items())
    if ref.kind == "mix_fader"
)

SET_PAN_ENTITY_KEYS: tuple[str, ...] = SET_SOLO_ENTITY_KEYS

CLEAR_MIX_SOLO_KEYS: tuple[str, ...] = tuple(
    key
    for key, ref in sorted(ENTITY_REGISTRY.items())
    if ref.kind == "bus_fader"
)

MIX_INPUT_ENTITY_KEYS: tuple[str, ...] = tuple(
    sorted(ch.key for ch in MIX_INPUT_CHANNELS)
)

SET_LEVEL_ENTITY_KEYS: tuple[str, ...] = tuple(
    key
    for key, ref in sorted(ENTITY_REGISTRY.items())
    if ref.kind in ("input_gain", "main_trim", "output_trim", "mix_fader", "bus_fader")
)

SET_MUTE_ENTITY_KEYS: tuple[str, ...] = tuple(
    key
    for key, ref in sorted(ENTITY_REGISTRY.items())
    if ref.kind in ("mix_fader", "bus_fader")
)

INPUT_48V_ENTITY_KEYS: tuple[str, ...] = tuple(ch.key_48v for ch in MIC_PRE_CHANNELS)

INPUT_PAD_ENTITY_KEYS: tuple[str, ...] = tuple(ch.key_pad for ch in MIC_PRE_CHANNELS)

SET_CHANNEL_MODE_ENTITY_KEYS: tuple[str, ...] = tuple(
    sorted(
        {
            *MIX_INPUT_ENTITY_KEYS,
            *(
                key
                for key, ref in ENTITY_REGISTRY.items()
                if ref.kind == "mix_fader"
                and ref.gain_ich is not None
                and ref.gain_ich <= STEREO_CAPABLE_MAX_GAIN_ICH
            ),
            *(
                key
                for key, ref in ENTITY_REGISTRY.items()
                if ref.kind == "bus_fader"
                and ref.gain_och is not None
                and 2 <= ref.gain_och <= 9
            ),
        }
    )
)

def _split_mix_bus_fader_key(key: str) -> tuple[str, str]:
    prefix = "MIXBUSFADER_"
    if not key.startswith(prefix):
        return "", ""
    rest = key[len(prefix) :]
    bus_part, _, channel_part = rest.partition("_")
    return bus_part, channel_part


_PAIRED_BUS_PARTS: frozenset[str] = frozenset(
    _split_mix_bus_fader_key(mix_bus_fader_entity_key(bus_name, "Out"))[0]
    for bus_name in MIX_BUS_MUTE_INDICES
    if "-" in bus_name
)


def _mix_fader_key_preference_score(key: str) -> tuple[int, int, str]:
    bus_part, channel_part = _split_mix_bus_fader_key(key)
    host_lr = channel_part in {"HOSTL", "HOSTR"}
    paired_bus = bus_part in _PAIRED_BUS_PARTS
    return (
        1 if host_lr else 0,
        0 if paired_bus else 1,
        key,
    )


def prefer_canonical_mix_fader_key(a: str, b: str) -> str:
    """Return deterministic canonical key when two mix_fader aliases collide."""
    a_ref = ENTITY_REGISTRY.get(a)
    b_ref = ENTITY_REGISTRY.get(b)
    if a_ref is None or b_ref is None:
        raise ValueError("unknown mix_fader key")
    if a_ref.kind != "mix_fader" or b_ref.kind != "mix_fader":
        raise ValueError("prefer_canonical_mix_fader_key expects mix_fader keys")
    if (
        a_ref.gain_ich,
        a_ref.gain_och,
    ) != (
        b_ref.gain_ich,
        b_ref.gain_och,
    ):
        raise ValueError("mix_fader keys must target the same wire cell")
    return min((a, b), key=_mix_fader_key_preference_score)


_MIX_FADER_TO_KEY: dict[tuple[int, int], str] = {}
for _key, _ref in ENTITY_REGISTRY.items():
    if _ref.kind != "mix_fader" or _ref.gain_ich is None or _ref.gain_och is None:
        continue
    _cell = (_ref.gain_ich, _ref.gain_och)
    _existing = _MIX_FADER_TO_KEY.get(_cell)
    if _existing is None:
        _MIX_FADER_TO_KEY[_cell] = _key
        continue
    _MIX_FADER_TO_KEY[_cell] = prefer_canonical_mix_fader_key(_existing, _key)

_BUS_FADER_TO_KEY: dict[int, str] = {}
for _key, _ref in ENTITY_REGISTRY.items():
    if _ref.kind != "bus_fader" or _ref.gain_och is None:
        continue
    _BUS_FADER_TO_KEY.setdefault(_ref.gain_och, _key)
_COLUMN_KEY_TO_MIX_KEY: dict[tuple[str, str], str] = {
    (bus_name, col.key): mix_bus_fader_entity_key(bus_name, col.label)
    for bus_name in MIX_BUS_MUTE_INDICES
    for col in FULL_MIX_MATRIX_COLUMNS
}

for _key, _ref in ENTITY_REGISTRY.items():
    globals()[_key] = _ref.index


def resolve_entity(key: str) -> EntityRef:
    """Return metadata for an entity constant name."""
    try:
        return ENTITY_REGISTRY[key]
    except KeyError as exc:
        raise ValueError(
            f"unknown entity key {key!r}; run list-entities to see valid keys"
        ) from exc


def resolve_stereo_input_gain_ich(key: str) -> int:
    """
    Return mix input row index (gain_ich) for stereo-mode commands.

    Accepts ``MIXINPUT_*`` keys or stereo-capable ``MIXBUSFADER_*`` crosspoints.
    """
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind == "mix_input":
        assert ref.gain_ich is not None
        return ref.gain_ich
    if ref.kind == "mix_fader":
        if ref.gain_ich is None or ref.gain_ich > STEREO_CAPABLE_MAX_GAIN_ICH:
            raise ValueError(
                f"{normalized!r} is not a stereo-capable input channel; "
                "use MIXINPUT_* or a MIXBUSFADER_* input crosspoint key"
            )
        return ref.gain_ich
    raise ValueError(
        f"{normalized!r} is not a mix input entity; "
        "use MIXINPUT_* or a MIXBUSFADER_* input crosspoint key"
    )


def resolve_stereo_bus_gain_och(key: str) -> int:
    """
    Return output-bus left gain_och for output stereo-mode commands.

    Accepts ``MIXBUSFADER_*_OUT`` keys for line output buses.
    """
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind != "bus_fader" or ref.gain_och is None:
        raise ValueError(
            f"{normalized!r} is not an output-bus entity; use MIXBUSFADER_*_OUT keys"
        )
    try:
        return resolve_bus_stereo_left_gain_och(ref.gain_och)
    except ValueError as exc:
        raise ValueError(
            f"{normalized!r} is not a stereo-configurable line output bus"
        ) from exc


def display_name(key: str) -> str:
    """Pretty CueMix-style label for an entity constant."""
    return resolve_entity(key).display


def meter_slot(key: str) -> int:
    """Meter array index for a METER_* constant."""
    ref = resolve_entity(key)
    if ref.kind != "meter":
        raise ValueError(f"{key!r} is not a meter entity")
    return ref.index


def property_index(key: str) -> tuple[str, int]:
    """Return (DeviceState props key, wire index) for an entity constant."""
    ref = resolve_entity(key)
    prop = _KIND_TO_PROP[ref.kind]
    if prop is None:
        raise ValueError(f"{key!r} is a meter entity; use meter_slot() instead")
    return prop, ref.index


def mix_fader_cell(key: str) -> tuple[int, int]:
    """Return (gain_ich, gain_och) for a mix_fader entity key."""
    ref = resolve_entity(key)
    if ref.kind != "mix_fader" or ref.gain_ich is None or ref.gain_och is None:
        raise ValueError(f"{key!r} is not a mix fader entity")
    return ref.gain_ich, ref.gain_och


def iter_canonical_mix_fader_keys() -> tuple[str, ...]:
    """One deterministic mix_fader key per physical wire cell."""
    return tuple(sorted(_MIX_FADER_TO_KEY.values()))


def iter_canonical_bus_fader_keys() -> tuple[str, ...]:
    """One deterministic bus_fader key per output bus row."""
    return tuple(sorted(_BUS_FADER_TO_KEY.values()))


def entity_key_for_mix_fader(bus_name: str, column_key: str) -> str:
    return _COLUMN_KEY_TO_MIX_KEY[(bus_name, column_key)]
