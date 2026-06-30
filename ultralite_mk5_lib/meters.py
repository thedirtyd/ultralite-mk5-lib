"""Meter slot index → name mapping for UltraLite mk5 (CueMix UI locations)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ultralite_mk5_lib.entity_keys import meter_entity_key

# display_index: Inputs bank, then Mix, then Outputs (matches CueMix tabs).
_GROUP_INPUTS = 100
_GROUP_MIX = 200
_GROUP_OUTPUTS = 300
_UNKNOWN_DISPLAY_BASE = 10_000

# PatchBase + output destinations (cuemix/www/dev.js, UltraLite mk5).
_PATCH_ZERO = 23
_PATCH_SPDIF = 44
SPDIF_OUT_PATCH_DEST_LEFT = _PATCH_SPDIF
SPDIF_OUT_PATCH_DEST_RIGHT = _PATCH_SPDIF + 1
OPTICAL_OUT_PATCH_BASE = 24
_DEFAULT_USB_SPDIF_OUT = 12
_DEFAULT_USB_OPTICAL_OUT = 14

# analogIns[].source in dev.js (line inputs 1–8 meter taps).
_ANALOG_IN_SOURCES = (37, 32, 38, 39, 35, 36, 33, 34)

_DEFAULT_PATCH_METER_SLOTS: dict[int, int] = {
    SPDIF_OUT_PATCH_DEST_LEFT: _DEFAULT_USB_SPDIF_OUT,
    SPDIF_OUT_PATCH_DEST_RIGHT: _DEFAULT_USB_SPDIF_OUT + 1,
}


@dataclass(frozen=True, slots=True)
class MeterSlot:
    """One meter catalog entry with a CueMix-oriented label and table sort order."""

    slot: int
    name: str
    display_index: int
    key: str
    patch_dest: int | None = None
    optical_out_channel: int | None = None


def _meter_slots() -> tuple[MeterSlot, ...]:
    """Ordered catalog (cuemix/www/iosetup.js + main.js + dev.js, UltraLite mk5)."""
    slots: list[MeterSlot] = []
    order = _GROUP_INPUTS

    def add(slot: int, name: str) -> None:
        nonlocal order
        slots.append(MeterSlot(slot, name, order, meter_entity_key(name)))
        order += 1

    def add_spdif_out(name: str, patch_dest: int) -> None:
        nonlocal order
        slots.append(
            MeterSlot(
                -1,
                name,
                order,
                meter_entity_key(name),
                patch_dest=patch_dest,
            )
        )
        order += 1

    def add_optical_out(channel: int) -> None:
        nonlocal order
        name = f"Outputs - Optical Out {channel}"
        slots.append(
            MeterSlot(
                -1,
                name,
                order,
                meter_entity_key(name),
                optical_out_channel=channel - 1,
            )
        )
        order += 1

    for slot, name in (
        (37, "Inputs - Mic In 1"),
        (32, "Inputs - Mic In 2"),
        (38, "Inputs - Line In 3"),
        (39, "Inputs - Line In 4"),
        (35, "Inputs - Line In 5"),
        (36, "Inputs - Line In 6"),
        (33, "Inputs - Line In 7"),
        (34, "Inputs - Line In 8"),
    ):
        add(slot, name)

    add(44, "Inputs - S/PDIF 1")
    add(45, "Inputs - S/PDIF 2")
    for i in range(8):
        add(24 + i, f"Inputs - Optical {i + 1}")

    order = _GROUP_MIX
    add(0, "Mix - USB Host In 1")
    add(1, "Mix - USB Host In 2")
    for slot, name in (
        (50, "Mix - Mic In 1 post-FX"),
        (51, "Mix - Mic In 2 post-FX"),
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

    add_spdif_out("Outputs - S/PDIF Out L", SPDIF_OUT_PATCH_DEST_LEFT)
    add_spdif_out("Outputs - S/PDIF Out R", SPDIF_OUT_PATCH_DEST_RIGHT)
    for i in range(1, 9):
        add_optical_out(i)

    return tuple(slots)


METER_SLOTS: tuple[MeterSlot, ...] = _meter_slots()

METER_SLOT_NAMES: dict[int, str] = {
    entry.slot: entry.name for entry in METER_SLOTS if entry.slot >= 0
}

METER_DISPLAY_INDEX: dict[int, int] = {
    entry.slot: entry.display_index for entry in METER_SLOTS if entry.slot >= 0
}


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
_SPDIF_NUM_CH = (2, 2, 2, 2, 0, 0)


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


def optical_output_meter_count(
    *,
    sample_rate: int | None,
    optical_output_mode: int | None,
) -> int:
    """Active optical output meter channels (kOpticalMode[1] + sample rate)."""
    sri = sample_rate_index(sample_rate)
    if optical_output_mode == OPTICAL_MODE_TOSLINK:
        return _TOSLINK_OPTICAL_CH[sri]
    return _ADAT_OPTICAL_CH[sri]


def spdif_output_meter_count(*, sample_rate: int | None) -> int:
    """Active S/PDIF output meter channels (disabled at 4x sample rates)."""
    return _SPDIF_NUM_CH[sample_rate_index(sample_rate)]


def _patch_meter_slot(
    fpga_patch: dict[int, int],
    dest_index: int,
) -> int:
    if dest_index in fpga_patch:
        return int(fpga_patch[dest_index])
    return _DEFAULT_PATCH_METER_SLOTS[dest_index]


def _optical_index_getter(patch: int) -> Callable[[int], int]:
    """iosetup.js get_optical_index_getter for UltraLite mk5 line-input expansion."""
    try:
        start = _ANALOG_IN_SOURCES.index(patch)
    except ValueError:
        return lambda index: patch + index

    def getter(index: int) -> int:
        source_index = start + index
        if source_index >= len(_ANALOG_IN_SOURCES):
            return _PATCH_ZERO
        return _ANALOG_IN_SOURCES[source_index]

    return getter


def _optical_out_meter_slot(
    fpga_patch: dict[int, int],
    channel_index: int,
) -> int:
    if OPTICAL_OUT_PATCH_BASE in fpga_patch:
        base_patch = int(fpga_patch[OPTICAL_OUT_PATCH_BASE])
    else:
        base_patch = _DEFAULT_USB_OPTICAL_OUT
    return _optical_index_getter(base_patch)(channel_index)


def resolve_meter_slot(
    entry: MeterSlot,
    *,
    fpga_patch: dict[int, int] | None = None,
) -> int:
    """Resolve catalog entry to a live meter array index."""
    patch = fpga_patch or {}
    if entry.patch_dest is not None:
        return _patch_meter_slot(patch, entry.patch_dest)
    if entry.optical_out_channel is not None:
        return _optical_out_meter_slot(patch, entry.optical_out_channel)
    return entry.slot


def meter_entry_visible(
    entry: MeterSlot,
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
    optical_output_mode: int | None = None,
) -> bool:
    """Whether a catalog entry should appear given optical mode and sample rate."""
    if entry.patch_dest == SPDIF_OUT_PATCH_DEST_LEFT:
        return spdif_output_meter_count(sample_rate=sample_rate) > 0
    if entry.patch_dest == SPDIF_OUT_PATCH_DEST_RIGHT:
        return spdif_output_meter_count(sample_rate=sample_rate) > 1
    if entry.optical_out_channel is not None:
        return entry.optical_out_channel < optical_output_meter_count(
            sample_rate=sample_rate,
            optical_output_mode=optical_output_mode,
        )
    if (
        OPTICAL_METER_BASE <= entry.slot < OPTICAL_METER_BASE + OPTICAL_METER_COUNT
        and entry.name.startswith("Inputs - Optical ")
    ):
        ch_index = entry.slot - OPTICAL_METER_BASE
        return ch_index < optical_input_meter_count(
            sample_rate=sample_rate,
            optical_input_mode=optical_input_mode,
        )
    return True


def meter_slot_visible(
    slot: int,
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
    optical_output_mode: int | None = None,
) -> bool:
    """Whether a static catalog slot should appear (legacy slot-based API)."""
    for entry in METER_SLOTS:
        if entry.slot == slot:
            return meter_entry_visible(
                entry,
                sample_rate=sample_rate,
                optical_input_mode=optical_input_mode,
                optical_output_mode=optical_output_mode,
            )
    return True


def iter_visible_meter_slots(
    *,
    sample_rate: int | None = None,
    optical_input_mode: int | None = None,
    optical_output_mode: int | None = None,
):
    """Yield METER_SLOTS entries filtered for current device configuration."""
    for entry in METER_SLOTS:
        if meter_entry_visible(
            entry,
            sample_rate=sample_rate,
            optical_input_mode=optical_input_mode,
            optical_output_mode=optical_output_mode,
        ):
            yield entry
