"""Output trim and routing helpers from dev.js / iosetup.js."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ultralite_mk5_lib.entity_keys import output_trim_entity_key

# PatchBase + LocalOutputs from cuemix/www/dev.js (UltraLite mk5).
_PATCH_I2S = 32
_PATCH_DSP = 46

# kFPGAPatch indices for output destinations (OutputDestination.get_line/get_phone).
MONITOR_PATCH_DEST_LEFT = _PATCH_I2S + 0x6  # Main Out 1  -> 38
MONITOR_PATCH_DEST_RIGHT = _PATCH_I2S + 0x7  # Main Out 2 -> 39
PHONES_PATCH_DEST_LEFT = _PATCH_I2S + 0xA  # Phones L     -> 42
PHONES_PATCH_DEST_RIGHT = _PATCH_I2S + 0xB  # Phones R   -> 43

# koTrim array indices (LocalOutputs dac nibble -> koTrim slot).
PHONES_TRIM_INDEX_LEFT = 10
PHONES_TRIM_INDEX_RIGHT = 11
MAIN_TRIM_INDEX = 0
MUTE_ENABLE_INDEX = 0

# Attenuation trim range (koTrim / kMainTrim).
TRIM_MIN_DB = -100.0
TRIM_MAX_DB = 0.0

# Default kFPGAPatch meter slots when routing has not been received yet.
_DEFAULT_PATCH_METER_SLOTS: dict[int, int] = {
    MONITOR_PATCH_DEST_LEFT: _PATCH_DSP + 0,
    MONITOR_PATCH_DEST_RIGHT: _PATCH_DSP + 1,
    PHONES_PATCH_DEST_LEFT: _PATCH_DSP + 18,
    PHONES_PATCH_DEST_RIGHT: _PATCH_DSP + 19,
}


@dataclass(frozen=True, slots=True)
class OutputTrimChannel:
    """One line-output DAC trim on the Outputs tab (LineOut chIdx order)."""

    name: str
    trim_index: int
    key: str


def _output_trim_channel(name: str, trim_index: int) -> OutputTrimChannel:
    return OutputTrimChannel(name, trim_index, output_trim_entity_key(name))


# iosetup.js Outputs: o1..o10 -> analogOuts[0..9].dac
OUTPUT_TRIM_CHANNELS: tuple[OutputTrimChannel, ...] = (
    _output_trim_channel("Main Out 1", 6),
    _output_trim_channel("Main Out 2", 7),
    _output_trim_channel("Line Out 3", 8),
    _output_trim_channel("Line Out 4", 9),
    _output_trim_channel("Line Out 5", 0),
    _output_trim_channel("Line Out 6", 1),
    _output_trim_channel("Line Out 7", 2),
    _output_trim_channel("Line Out 8", 3),
    _output_trim_channel("Line Out 9", 4),
    _output_trim_channel("Line Out 10", 5),
)


@dataclass(frozen=True, slots=True)
class MonitorTrimChannel:
    """Monitor Trim section rows (Main Out, Phones)."""

    name: str
    key: str
    prop: str
    index: int


MONITOR_TRIM_CHANNELS: tuple[MonitorTrimChannel, ...] = (
    MonitorTrimChannel("Main Out", "VOLUME_MAIN", "main_trim", MAIN_TRIM_INDEX),
    MonitorTrimChannel("Phones", "VOLUME_PHONES", "output_trim", PHONES_TRIM_INDEX_LEFT),
)


def trim_byte_to_db(value: int | None) -> float | None:
    """
    Convert koTrim / kMainTrim byte to dB (iosetup.js IOKnobTextEdit).

    0 = 0 dB, 1..99 = -1..-99 dB, 100 = -inf.
    """
    if value is None:
        return None
    if value >= 100:
        return float("-inf")
    if value == 0:
        return 0.0
    return -float(value)


def build_output_trims(props: dict[str, dict[int, Any]]) -> list[tuple[str, float | None]]:
    """Line output koTrim rows for Output Trim table: (name, dB)."""
    output_trim = props.get("output_trim", {})
    return [
        (ch.name, trim_byte_to_db(output_trim.get(ch.trim_index)))
        for ch in OUTPUT_TRIM_CHANNELS
    ]


def build_monitors_trim(
    props: dict[str, dict[int, Any]],
) -> list[tuple[str, str, float | None, bool | None]]:
    """Monitor trim rows: (name, key, dB, mute). mute is hardware mute for Main Out."""
    output_trim = props.get("output_trim", {})
    main_trim = props.get("main_trim", {})
    mute_enable = props.get("mute_enable", {})

    mute_val = mute_enable.get(MUTE_ENABLE_INDEX)
    mute: bool | None = None if mute_val is None else bool(mute_val)

    rows: list[tuple[str, str, float | None, bool | None]] = []
    for ch in MONITOR_TRIM_CHANNELS:
        prop_dict = main_trim if ch.prop == "main_trim" else output_trim
        db = trim_byte_to_db(prop_dict.get(ch.index))
        row_mute = mute if ch.prop == "main_trim" else None
        rows.append((ch.name, ch.key, db, row_mute))
    return rows


def _patch_meter_slot(
    patch: dict[int, int],
    dest_index: int,
) -> int:
    if dest_index in patch:
        return int(patch[dest_index])
    return _DEFAULT_PATCH_METER_SLOTS[dest_index]


def _meter_db(meters: list[float], slot: int) -> float | None:
    if slot < 0 or slot >= len(meters):
        return None
    return meters[slot]


def build_output_monitoring(
    props: dict[str, dict[int, Any]],
    meters: list[float],
    *,
    meters_received: bool,
) -> dict[str, Any]:
    """Resolve Monitor / Phones output-section trim, mute, and meter levels."""
    fpga_patch = {int(k): int(v) for k, v in props.get("fpga_patch", {}).items()}
    output_trim = props.get("output_trim", {})
    main_trim = props.get("main_trim", {})
    mute_enable = props.get("mute_enable", {})

    monitor_slot_l = _patch_meter_slot(fpga_patch, MONITOR_PATCH_DEST_LEFT)
    monitor_slot_r = _patch_meter_slot(fpga_patch, MONITOR_PATCH_DEST_RIGHT)
    phones_slot_l = _patch_meter_slot(fpga_patch, PHONES_PATCH_DEST_LEFT)
    phones_slot_r = _patch_meter_slot(fpga_patch, PHONES_PATCH_DEST_RIGHT)

    monitor_meters: dict[str, float | None] | None
    phones_meters: dict[str, float | None] | None
    if meters_received:
        monitor_meters = {
            "L": _meter_db(meters, monitor_slot_l),
            "R": _meter_db(meters, monitor_slot_r),
        }
        phones_meters = {
            "L": _meter_db(meters, phones_slot_l),
            "R": _meter_db(meters, phones_slot_r),
        }
    else:
        monitor_meters = None
        phones_meters = None

    return {
        "monitor": {
            "trim_db": trim_byte_to_db(main_trim.get(MAIN_TRIM_INDEX)),
            "muted": (
                None
                if MUTE_ENABLE_INDEX not in mute_enable
                else bool(mute_enable[MUTE_ENABLE_INDEX])
            ),
            "meter_slots": {"L": monitor_slot_l, "R": monitor_slot_r},
            "meters_db": monitor_meters,
            "patch_source": {
                "L": fpga_patch.get(MONITOR_PATCH_DEST_LEFT),
                "R": fpga_patch.get(MONITOR_PATCH_DEST_RIGHT),
            },
        },
        "phones_output": {
            "trim_db": {
                "L": trim_byte_to_db(output_trim.get(PHONES_TRIM_INDEX_LEFT)),
                "R": trim_byte_to_db(output_trim.get(PHONES_TRIM_INDEX_RIGHT)),
            },
            "meter_slots": {"L": phones_slot_l, "R": phones_slot_r},
            "meters_db": phones_meters,
            "patch_source": {
                "L": fpga_patch.get(PHONES_PATCH_DEST_LEFT),
                "R": fpga_patch.get(PHONES_PATCH_DEST_RIGHT),
            },
        },
    }
