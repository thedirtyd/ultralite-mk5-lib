"""Structured device state report matching get-state display sections."""

from __future__ import annotations

from typing import Any

from ultralite_mk5_lib.ab_monitor import build_ab_monitor_state
from ultralite_mk5_lib.entity_keys import mix_bus_fader_entity_key
from ultralite_mk5_lib.eq import build_bus_eq_state, build_input_eq_state
from ultralite_mk5_lib.inputs import INPUT_GAIN_CHANNELS, build_input_gains, build_mic_pre_state
from ultralite_mk5_lib.mix_buses import build_mix_bus_fader_matrix, mix_fader_gain_to_db
from ultralite_mk5_lib.meters import iter_visible_meter_slots, resolve_meter_slot
from ultralite_mk5_lib.outputs import (
    MONITOR_TRIM_CHANNELS,
    OUTPUT_TRIM_CHANNELS,
    build_monitors_trim,
    build_output_trims,
)
from ultralite_mk5_lib.protocol import (
    optical_input_mode_from_snap,
    optical_input_mode_wire_from_snap,
    optical_output_mode_from_snap,
    optical_output_mode_wire_from_snap,
)
from ultralite_mk5_lib.state import (
    K_MIN_METER_DB,
    snapshot_to_json,
)


def _fpga_patch_from_snap(snap: dict[str, Any]) -> dict[int, int]:
    return {int(k): int(v) for k, v in snap.get("props", {}).get("fpga_patch", {}).items()}


def _build_meter_entries(snap: dict[str, Any]) -> list[dict[str, Any]]:
    meters = snap.get("meters", [])
    meters_received = bool(snap.get("meters_received"))
    fpga_patch = _fpga_patch_from_snap(snap)
    entries: list[dict[str, Any]] = []
    for entry in iter_visible_meter_slots(
        sample_rate=snap.get("sample_rate"),
        optical_input_mode=optical_input_mode_wire_from_snap(snap),
        optical_output_mode=optical_output_mode_wire_from_snap(snap),
    ):
        slot = resolve_meter_slot(entry, fpga_patch=fpga_patch)
        if not meters_received or slot < 0 or slot >= len(meters):
            db: float | None = None
        else:
            db = meters[slot]
            if db <= K_MIN_METER_DB:
                db = K_MIN_METER_DB
        entries.append(
            {
                "key": entry.key,
                "name": entry.name,
                "slot": slot,
                "db": db,
            }
        )
    return entries


def build_state_report(snap: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-serializable report of the get-state display contents."""
    props = snap.get("props", {})

    trim_by_key = {key: (name, db, mute) for name, key, db, mute in build_monitors_trim(props)}
    monitor_trim: list[dict[str, Any]] = []
    for ch in MONITOR_TRIM_CHANNELS:
        name, db, mute = trim_by_key[ch.key]
        row: dict[str, Any] = {"key": ch.key, "name": name, "db": db}
        if mute is not None:
            row["mute"] = mute
        monitor_trim.append(row)

    gain_by_name = {name: db for name, db, _min, _max in build_input_gains(props)}
    mic_pre_by_index = {row["index"]: row for row in build_mic_pre_state(props)}
    input_gain = []
    for ch in INPUT_GAIN_CHANNELS:
        row: dict[str, Any] = {
            "key": ch.key,
            "name": ch.name,
            "db": gain_by_name[ch.name],
        }
        mic_pre = mic_pre_by_index.get(ch.index)
        if mic_pre is not None:
            row["48v"] = mic_pre["48v"]
            row["pad"] = mic_pre["pad"]
            row["jack"] = mic_pre["jack"]
            row["key_48v"] = mic_pre["key_48v"]
            row["key_pad"] = mic_pre["key_pad"]
        input_gain.append(row)

    trim_by_name = {name: db for name, db in build_output_trims(props)}
    output_trim = [
        {"key": ch.key, "name": ch.name, "db": trim_by_name[ch.name]}
        for ch in OUTPUT_TRIM_CHANNELS
    ]

    matrix = snap.get("mix_bus_fader_matrix")
    if matrix is None:
        matrix = build_mix_bus_fader_matrix(
            props,
            sample_rate=snap.get("sample_rate"),
            optical_input_mode=optical_input_mode_wire_from_snap(snap),
        )

    mix_bus_faders: dict[str, Any] = {
        "columns": matrix.get("columns", []),
        "buses": [],
    }
    for bus in matrix.get("buses", []):
        fader_entries: list[dict[str, Any]] = []
        for col, cell in zip(matrix.get("columns", []), bus.get("faders", [])):
            entry: dict[str, Any] = {
                "key": mix_bus_fader_entity_key(bus["name"], col["label"]),
                "name": col["label"],
                "gain": cell.get("gain"),
            }
            db = cell.get("db")
            if db is None and cell.get("gain") is not None:
                db = mix_fader_gain_to_db(cell.get("gain"))
            if db is not None:
                entry["db"] = db
            channel_mute = cell.get("mute")
            if channel_mute is not None:
                entry["mute"] = bool(channel_mute)
            fader_entries.append(entry)
        row: dict[str, Any] = {
            "key": bus["key"],
            "name": bus["name"],
            "faders": fader_entries,
        }
        bus_mute = bus.get("mute")
        if bus_mute is not None:
            row["mute"] = bool(bus_mute)
        mix_bus_faders["buses"].append(row)

    return {
        "device": {
            "name": snap.get("device_name"),
            "api_version": snap.get("api_version"),
            "sample_rate": snap.get("sample_rate"),
            "optical_input_mode": optical_input_mode_from_snap(snap),
            "optical_output_mode": optical_output_mode_from_snap(snap),
            "frame_count": snap.get("frame_count", 0),
        },
        "ab_monitor": build_ab_monitor_state(props),
        "monitor_trim": monitor_trim,
        "input_gain": input_gain,
        "output_trim": output_trim,
        "input_eq": build_input_eq_state(props),
        "bus_eq": build_bus_eq_state(props),
        "mix_bus_faders": mix_bus_faders,
        "meters": _build_meter_entries(snap),
    }


def state_report_to_json(
    snap: dict[str, Any],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a get-state style report to JSON."""
    return snapshot_to_json(build_state_report(snap), indent=indent)
