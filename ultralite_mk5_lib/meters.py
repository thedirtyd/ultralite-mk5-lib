"""Meter slot index → name mapping for UltraLite mk5 (CueMix UI locations)."""

from __future__ import annotations

from dataclasses import dataclass

from ultralite_mk5_lib.entity_keys import meter_entity_key

# display_index: Inputs bank, then Mix, then Outputs (matches CueMix tabs).
_GROUP_INPUTS = 100
_GROUP_MIX = 200
_GROUP_OUTPUTS = 300
_UNKNOWN_DISPLAY_BASE = 10_000


@dataclass(frozen=True, slots=True)
class MeterSlot:
    """One meter array index with a CueMix-oriented label and table sort order."""

    slot: int
    name: str
    display_index: int
    key: str


def _meter_slots() -> tuple[MeterSlot, ...]:
    """Ordered catalog (cuemix/www/iosetup.js + main.js + dev.js, UltraLite mk5)."""
    slots: list[MeterSlot] = []
    order = _GROUP_INPUTS

    def add(slot: int, name: str) -> None:
        nonlocal order
        slots.append(MeterSlot(slot, name, order, meter_entity_key(name)))
        order += 1

    for slot, name in (
        (37, "Inputs - Mic/Line In 1"),
        (32, "Inputs - Mic/Line In 2"),
        (38, "Inputs - Line In 3"),
        (39, "Inputs - Line In 4"),
        (35, "Inputs - Line In 5"),
        (36, "Inputs - Line In 6"),
        (33, "Inputs - Line In 7"),
        (34, "Inputs - Line In 8"),
    ):
        add(slot, name)

    add(44, "Inputs - S/PDIF In L")
    add(45, "Inputs - S/PDIF In R")
    for i in range(8):
        add(24 + i, f"Inputs - Optical {i + 1}")

    order = _GROUP_MIX
    add(0, "Mix - USB Host In 1")
    add(1, "Mix - USB Host In 2")
    for slot, name in (
        (50, "Mix - Mic/Line In 1 post-FX"),
        (51, "Mix - Mic/Line In 2 post-FX"),
        (52, "Mix - Line In 3 post-FX"),
        (53, "Mix - Line In 4 post-FX"),
        (58, "Mix - Line In 5 post-FX"),
        (59, "Mix - Line In 6 post-FX"),
        (60, "Mix - Line In 7 post-FX"),
        (61, "Mix - Line In 8 post-FX"),
    ):
        add(slot, name)
    add(68, "Mix - Reverb wet")

    order = _GROUP_OUTPUTS
    for slot, name in (
        (46, "Outputs - Main Out 1 mix"),
        (47, "Outputs - Main Out 2 mix"),
        (48, "Outputs - Line Out 3 mix"),
        (49, "Outputs - Line Out 4 mix"),
        (54, "Outputs - Line Out 5 mix"),
        (55, "Outputs - Line Out 6 mix"),
        (56, "Outputs - Line Out 7 mix"),
        (57, "Outputs - Line Out 8 mix"),
        (62, "Outputs - Line Out 9 mix"),
        (63, "Outputs - Line Out 10 mix"),
        (64, "Outputs - Phones mix L"),
        (65, "Outputs - Phones mix R"),
    ):
        add(slot, name)

    return tuple(slots)


METER_SLOTS: tuple[MeterSlot, ...] = _meter_slots()

METER_SLOT_NAMES: dict[int, str] = {entry.slot: entry.name for entry in METER_SLOTS}

METER_DISPLAY_INDEX: dict[int, int] = {entry.slot: entry.display_index for entry in METER_SLOTS}


def meter_sort_key(slot: int) -> tuple[int, int]:
    """Sort key for meter tables: catalog order, then unseen slots by index."""
    return (METER_DISPLAY_INDEX.get(slot, _UNKNOWN_DISPLAY_BASE + slot), slot)


def resolve_meter_slot_name(slot: int) -> str:
    """Resolve a meter array index to a human-readable label."""
    return METER_SLOT_NAMES.get(slot, f"slot {slot}")


# Optical input taps (PatchBase.adat); visibility follows kOpticalMode[0] + kSampleRate.
OPTICAL_METER_BASE = 24
OPTICAL_METER_COUNT = 8
OPTICAL_MODE_ADAT = 0
OPTICAL_MODE_TOSLINK = 1

_SAMPLE_RATE_ORDER = (44100, 48000, 88200, 96000, 176400, 192000)
_ADAT_OPTICAL_CH = (8, 8, 4, 4, 0, 0)
_TOSLINK_OPTICAL_CH = (2, 2, 2, 2, 0, 0)


def sample_rate_index(sample_rate: int | None) -> int:
    """Index into dev.js numCh tables; defaults to 48 kHz."""
    if sample_rate is None:
        return 1
    try:
        return _SAMPLE_RATE_ORDER.index(sample_rate)
    except ValueError:
        return 1


def optical_input_meter_count(
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
) -> int:
    """Active optical input meter channels (CueMix dev.js adatInfo / tosInfo)."""
    sri = sample_rate_index(sample_rate)
    if optical_input_mode == OPTICAL_MODE_TOSLINK:
        return _TOSLINK_OPTICAL_CH[sri]
    return _ADAT_OPTICAL_CH[sri]


def meter_slot_visible(
    slot: int,
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
) -> bool:
    """Whether a catalog slot should appear given optical mode and sample rate."""
    if slot < OPTICAL_METER_BASE or slot >= OPTICAL_METER_BASE + OPTICAL_METER_COUNT:
        return True
    ch_index = slot - OPTICAL_METER_BASE
    return ch_index < optical_input_meter_count(
        sample_rate=sample_rate,
        optical_input_mode=optical_input_mode,
    )


def iter_visible_meter_slots(
    *,
    sample_rate: int | None = None,
    optical_input_mode: int | None = None,
):
    """Yield METER_SLOTS entries filtered for current optical input configuration."""
    for entry in METER_SLOTS:
        if meter_slot_visible(
            entry.slot,
            sample_rate=sample_rate,
            optical_input_mode=optical_input_mode,
        ):
            yield entry
