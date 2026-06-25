"""Importable entity constants, display names, and wire-index resolvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES
from ultralite_mk5_lib.entity_keys import (
    mix_bus_entity_key_part,
    mix_bus_fader_entity_key,
)
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
                if col.native_bus is not None and bus_name != col.native_bus:
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

MIX_INPUT_ENTITY_KEYS: tuple[str, ...] = tuple(
    sorted(ch.key for ch in MIX_INPUT_CHANNELS)
)

_METER_SLOT_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "meter"
}
_INPUT_GAIN_INDEX_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "input_gain"
}
_INPUT_48V_INDEX_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "input_48v"
}
_INPUT_PAD_INDEX_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "input_pad"
}
_OUTPUT_TRIM_INDEX_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "output_trim"
}
_MAIN_TRIM_INDEX_TO_KEY: dict[int, str] = {
    ref.index: key for key, ref in ENTITY_REGISTRY.items() if ref.kind == "main_trim"
}
_MIX_FADER_TO_KEY: dict[tuple[int, int], str] = {
    (ref.gain_ich, ref.gain_och): key
    for key, ref in ENTITY_REGISTRY.items()
    if ref.kind == "mix_fader" and ref.gain_ich is not None and ref.gain_och is not None
}
_MIX_INPUT_GAIN_ICH_TO_KEY: dict[int, str] = {
    ref.gain_ich: key
    for key, ref in ENTITY_REGISTRY.items()
    if ref.kind == "mix_input" and ref.gain_ich is not None
}
_BUS_FADER_TO_KEY: dict[int, str] = {
    ref.gain_och: key
    for key, ref in ENTITY_REGISTRY.items()
    if ref.kind == "bus_fader" and ref.gain_och is not None
}
_BUS_NAME_TO_KEY: dict[str, str] = {
    bus_name: mix_bus_entity_key_part(bus_name) for bus_name in MIX_BUS_MUTE_INDICES
}
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


def display_name(key: str) -> str:
    """Pretty CueMix-style label for an entity constant."""
    return resolve_entity(key).display


def meter_slot(key: str) -> int:
    """Meter array index for a METER_* constant."""
    ref = resolve_entity(key)
    if ref.kind != "meter":
        raise ValueError(f"{key!r} is not a meter entity")
    return ref.index


def mix_fader_flat_index(key: str) -> int:
    """kiMixFader flat index for a MIXBUSFADER_* crosspoint constant."""
    ref = resolve_entity(key)
    if ref.kind != "mix_fader":
        raise ValueError(f"{key!r} is not a mix fader entity")
    return ref.index


def property_index(key: str) -> tuple[str, int]:
    """Return (DeviceState props key, wire index) for an entity constant."""
    ref = resolve_entity(key)
    prop = _KIND_TO_PROP[ref.kind]
    if prop is None:
        raise ValueError(f"{key!r} is a meter entity; use meter_slot() instead")
    return prop, ref.index


def entity_key_for_meter_slot(slot: int) -> str | None:
    return _METER_SLOT_TO_KEY.get(slot)


def entity_key_for_input_gain(index: int) -> str | None:
    return _INPUT_GAIN_INDEX_TO_KEY.get(index)


def entity_key_for_input_48v(index: int) -> str | None:
    return _INPUT_48V_INDEX_TO_KEY.get(index)


def entity_key_for_input_pad(index: int) -> str | None:
    return _INPUT_PAD_INDEX_TO_KEY.get(index)


def entity_key_for_output_trim(index: int) -> str | None:
    return _OUTPUT_TRIM_INDEX_TO_KEY.get(index)


def entity_key_for_main_trim(index: int) -> str | None:
    return _MAIN_TRIM_INDEX_TO_KEY.get(index)


def entity_key_for_mix_bus(bus_name: str) -> str:
    return _BUS_NAME_TO_KEY[bus_name]


def entity_key_for_mix_column(column_key: str, bus_name: str) -> str:
    return _COLUMN_KEY_TO_MIX_KEY[(bus_name, column_key)]


def entity_key_for_mix_fader(bus_name: str, column_key: str) -> str:
    return entity_key_for_mix_column(column_key, bus_name)


def entity_key_for_mix_input(gain_ich: int) -> str | None:
    return _MIX_INPUT_GAIN_ICH_TO_KEY.get(gain_ich)
