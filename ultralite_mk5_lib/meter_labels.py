"""Snapshot-aware meter display names for layout-active catalog entries."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from ultralite_mk5_lib.entities import display_name, resolve_entity
from ultralite_mk5_lib.meters import (
    METER_SLOTS,
    iter_visible_meter_slots,
    optical_input_meter_count,
    optical_output_meter_count,
    spdif_output_meter_count,
)
from ultralite_mk5_lib.mix_buses import FULL_MIX_MATRIX_COLUMNS, MixMatrixColumn
from ultralite_mk5_lib.outputs import OUTPUT_TRIM_CHANNELS
from ultralite_mk5_lib.protocol import (
    optical_input_mode_wire_from_snap,
    optical_output_mode_wire_from_snap,
)

_METER_KEY_BY_CATALOG_NAME = {entry.name: entry.key for entry in METER_SLOTS}


class MeterNameEntry(TypedDict):
    """Per-meter display labels: mono always; stereo when pairable."""

    mono: str
    stereo: NotRequired[str]


def _mix_stereo_props(snapshot: dict[str, Any]) -> dict[int, int]:
    return snapshot.get("props", {}).get("mix_stereo", {})


def _column_by_gain_ich(gain_ich: int) -> MixMatrixColumn | None:
    for col in FULL_MIX_MATRIX_COLUMNS:
        if col.gain_ich == gain_ich:
            return col
    return None


def _stereo_linked(col: MixMatrixColumn, mix_stereo: dict[int, int]) -> bool:
    if col.stereo_left_ich is None:
        return False
    return bool(mix_stereo.get(col.stereo_left_ich, 0))


def _meter_column_label(col: MixMatrixColumn, mix_stereo: dict[int, int]) -> str:
    """Column label with stereo combined name on both L and R when linked."""
    label = col.label
    left_ich = col.stereo_left_ich
    if left_ich is not None:
        left_col = _column_by_gain_ich(left_ich)
        if (
            left_col is not None
            and left_col.stereo_label is not None
            and _stereo_linked(left_col, mix_stereo)
        ):
            label = left_col.stereo_label
    return label


def _build_gain_ich_to_meter_keys() -> dict[int, frozenset[str]]:
    name_to_key = {entry.name: entry.key for entry in METER_SLOTS}
    mapping: dict[int, set[str]] = {}
    for col in FULL_MIX_MATRIX_COLUMNS:
        if col.kind != "input" or col.gain_ich is None:
            continue
        keys: set[str] = set()
        for meter_name in (
            f"Inputs - {col.label}",
            f"Mix - {col.label} post-FX",
        ):
            key = name_to_key.get(meter_name)
            if key is not None:
                keys.add(key)
        if keys:
            mapping[col.gain_ich] = keys
    return {ich: frozenset(keys) for ich, keys in mapping.items()}


_GAIN_ICH_TO_METER_KEYS: dict[int, frozenset[str]] = _build_gain_ich_to_meter_keys()


def _output_trim_meter_label(key: str) -> str | None:
    for ch in OUTPUT_TRIM_CHANNELS:
        if _METER_KEY_BY_CATALOG_NAME.get(f"Outputs - {ch.name} mix") == key:
            return ch.name
    phones = {
        _METER_KEY_BY_CATALOG_NAME["Outputs - Phones mix L"]: "Phones L",
        _METER_KEY_BY_CATALOG_NAME["Outputs - Phones mix R"]: "Phones R",
    }
    return phones.get(key)


def iter_layout_meter_keys(snapshot: dict[str, Any]) -> tuple[str, ...]:
    """All METER_* keys active for current sample rate and optical layout."""
    return tuple(
        entry.key
        for entry in iter_visible_meter_slots(
            sample_rate=snapshot.get("sample_rate"),
            optical_input_mode=optical_input_mode_wire_from_snap(snapshot),
            optical_output_mode=optical_output_mode_wire_from_snap(snapshot),
        )
    )


def _meter_name_entry_for_column(
    col: MixMatrixColumn,
    *,
    prefix: str,
    suffix: str = "",
) -> MeterNameEntry:
    """Build mono/stereo labels for an input-tap or mix-post-FX meter column."""
    entry: MeterNameEntry = {"mono": f"{prefix}{col.label}{suffix}"}
    left_ich = col.stereo_left_ich
    if left_ich is not None:
        left_col = _column_by_gain_ich(left_ich)
        if left_col is not None and left_col.stereo_label is not None:
            entry["stereo"] = f"{prefix}{left_col.stereo_label}{suffix}"
    return entry


def meter_name_entry(key: str, snapshot: dict[str, Any]) -> MeterNameEntry:
    """Mono label per key; optional stereo label when the meter is pairable."""
    ref = resolve_entity(key)
    if ref.kind != "meter":
        return {"mono": display_name(key)}

    out_trim = _output_trim_meter_label(key)
    if out_trim is not None:
        return {"mono": out_trim}

    for gain_ich, meter_keys in _GAIN_ICH_TO_METER_KEYS.items():
        if key not in meter_keys:
            continue
        col = _column_by_gain_ich(gain_ich)
        if col is None:
            break
        if ref.display.startswith("Inputs - "):
            return _meter_name_entry_for_column(col, prefix="Inputs - ")
        if ref.display.startswith("Mix - ") and ref.display.endswith(" post-FX"):
            return _meter_name_entry_for_column(
                col,
                prefix="Mix - ",
                suffix=" post-FX",
            )
        break

    return {"mono": display_name(key)}


def meter_display_name(key: str, snapshot: dict[str, Any]) -> str:
    """Snapshot-aware display label; stereo pairs share one name on L and R."""
    ref = resolve_entity(key)
    if ref.kind != "meter":
        return display_name(key)

    out_trim = _output_trim_meter_label(key)
    if out_trim is not None:
        return out_trim

    mix_stereo = _mix_stereo_props(snapshot)
    for gain_ich, meter_keys in _GAIN_ICH_TO_METER_KEYS.items():
        if key not in meter_keys:
            continue
        col = _column_by_gain_ich(gain_ich)
        if col is None:
            break
        label = _meter_column_label(col, mix_stereo)
        if ref.display.startswith("Inputs - "):
            return f"Inputs - {label}"
        if ref.display.startswith("Mix - ") and ref.display.endswith(" post-FX"):
            return f"Mix - {label} post-FX"
        break

    return display_name(key)


def build_meter_names(snapshot: dict[str, Any]) -> dict[str, MeterNameEntry]:
    """Layout-active meter key -> mono label and optional stereo label."""
    return {
        key: meter_name_entry(key, snapshot)
        for key in iter_layout_meter_keys(snapshot)
    }


def digital_meter_layout(snapshot: dict[str, Any]) -> dict[str, int]:
    """Active digital I/O meter channel counts for current device layout."""
    sample_rate = snapshot.get("sample_rate")
    return {
        "spdif_in": 2,
        "optical_in": optical_input_meter_count(
            sample_rate=sample_rate,
            optical_input_mode=optical_input_mode_wire_from_snap(snapshot),
        ),
        "spdif_out": spdif_output_meter_count(sample_rate=sample_rate),
        "optical_out": optical_output_meter_count(
            sample_rate=sample_rate,
            optical_output_mode=optical_output_mode_wire_from_snap(snapshot),
        ),
    }
