"""Mix bus tab layout and kiMixFader / koBusFader matrix (from dev.js / mixmgr.js)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Literal

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES, stereo_bus_muted
from ultralite_mk5_lib.entity_keys import (
    mix_bus_entity_key_part,
    mix_bus_fader_entity_key,
    mix_channel_entity_key_part,
)
from ultralite_mk5_lib.meters import (
    optical_input_meter_count,
    sample_rate_index,
)

NUM_MIX_INPUTS = 32

ColumnKind = Literal["input", "reverb", "host_l", "host_r", "out"]

# Host-return kiMixFader input rows (mixOutputs iGain + bankChNum) per bus tab.
BUS_HOST_GAIN_ICH: dict[str, int | None] = {
    "main 1-2": 18,
    "line 3-4": 20,
    "line 5-6": 22,
    "line 7-8": 24,
    "line 9-10": 26,
    "phones": 28,
    "reverb": None,
}

_SPDIF_NUM_CH = (2, 2, 2, 2, 0, 0)
_REVERB_NUM_CH = (2, 2, 2, 2, 0, 0)
# kiMixStereo indices for linkable input pairs (mic through optical/toslink).
STEREO_CAPABLE_MAX_GAIN_ICH = 17


@dataclass(frozen=True, slots=True)
class MixMatrixColumn:
    """One column in the mix-bus fader matrix."""

    column_id: str
    label: str
    kind: ColumnKind
    key: str
    gain_ich: int | None = None
    stereo_left_ich: int | None = None
    stereo_label: str | None = None


def _make_stereo_label(left: str, right: str) -> str:
    """Combine left/right labels (e.g. Optical 1 + Optical 2 → Optical 1/2)."""
    i = 0
    limit = min(len(left), len(right))
    while i < limit and left[i] == right[i]:
        i += 1
    return f"{left[:i]}{left[i:]}/{right[i:]}"


def _is_stereo_capable(col: MixMatrixColumn) -> bool:
    return (
        col.kind == "input"
        and col.gain_ich is not None
        and col.gain_ich <= STEREO_CAPABLE_MAX_GAIN_ICH
    )


def _apply_stereo_metadata(
    cols: tuple[MixMatrixColumn, ...],
) -> tuple[MixMatrixColumn, ...]:
    """Fill stereo_left_ich and stereo_label for linkable input pairs."""
    by_ich = {c.gain_ich: c for c in cols if c.gain_ich is not None}
    updated: list[MixMatrixColumn] = []
    for col in cols:
        if not _is_stereo_capable(col):
            updated.append(col)
            continue
        assert col.gain_ich is not None
        left_ich = col.gain_ich & 0xFE
        right_col = by_ich.get(left_ich + 1)
        left_col = by_ich.get(left_ich)
        stereo_label = None
        if col.gain_ich == left_ich and right_col is not None and left_col is not None:
            stereo_label = _make_stereo_label(left_col.label, right_col.label)
        updated.append(
            replace(
                col,
                stereo_left_ich=left_ich,
                stereo_label=stereo_label,
            )
        )
    return tuple(updated)


def _mix_column(label: str, column_id: str, kind: ColumnKind, gain_ich: int | None = None) -> MixMatrixColumn:
    return MixMatrixColumn(
        column_id,
        label,
        kind,
        mix_channel_entity_key_part(label),
        gain_ich,
    )


def _append_mono_channels(
    cols: list[MixMatrixColumn],
    *,
    prefix: str,
    label_prefix: str,
    start_ich: int,
    count: int,
) -> None:
    for offset in range(count):
        n = offset + 1
        ich = start_ich + offset
        cols.append(
            _mix_column(
                f"{label_prefix}{n}",
                f"{prefix}-{n}",
                "input",
                ich,
            )
        )


def _mix_matrix_columns(
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
) -> tuple[MixMatrixColumn, ...]:
    """Column layout matching CueMix bus strip order (host L/R before Out)."""
    sri = sample_rate_index(sample_rate)
    cols: list[MixMatrixColumn] = []

    _append_mono_channels(
        cols, prefix="mic", label_prefix="Mic/Line In ", start_ich=0, count=2
    )
    for line_num in range(3, 9):
        cols.append(
            _mix_column(
                f"Line In {line_num}",
                f"line-{line_num}",
                "input",
                line_num - 1,
            )
        )

    if _SPDIF_NUM_CH[sri] > 0:
        cols.append(_mix_column("S/PDIF In L", "spdif-1", "input", 8))
        cols.append(_mix_column("S/PDIF In R", "spdif-2", "input", 9))

    optical_ch = optical_input_meter_count(
        sample_rate=sample_rate,
        optical_input_mode=optical_input_mode,
    )
    if optical_ch > 0:
        _append_mono_channels(
            cols,
            prefix="opt",
            label_prefix="Optical ",
            start_ich=10,
            count=optical_ch,
        )

    if _REVERB_NUM_CH[sri] > 0:
        cols.append(_mix_column("Reverb", "reverb", "reverb", 30))

    cols.append(_mix_column("Host L", "host-l", "host_l"))
    cols.append(_mix_column("Host R", "host-r", "host_r"))
    cols.append(_mix_column("Out", "bus-out", "out"))
    return _apply_stereo_metadata(tuple(cols))


def mix_matrix_columns(
    *,
    sample_rate: int | None,
    optical_input_mode: int | None,
) -> tuple[MixMatrixColumn, ...]:
    """Column layout matching CueMix bus strip order (host L/R before Out)."""
    return _mix_matrix_columns(
        sample_rate=sample_rate,
        optical_input_mode=optical_input_mode,
    )


# Full matrix at 48 kHz ADAT — all entity constants exist regardless of runtime visibility.
FULL_MIX_MATRIX_COLUMNS: tuple[MixMatrixColumn, ...] = mix_matrix_columns(
    sample_rate=48000,
    optical_input_mode=0,
)


def mix_fader_index(gain_ich: int, gain_och: int) -> int:
    """kiMixFader flat index: output bus row × 32 inputs + input channel."""
    return gain_och * NUM_MIX_INPUTS + gain_ich


def mix_fader_gain_to_db(gain: float | None) -> float | None:
    """Map kiMixFader / koBusFader linear gain to dB."""
    if gain is None:
        return None
    if gain <= 0:
        return float("-inf")
    return 20.0 * math.log10(gain)


FADER_GAIN_MIN = 0.0
FADER_GAIN_MAX = 4.0


def db_to_linear_gain(db: float) -> float:
    """Map dB to kiMixFader / koBusFader linear gain."""
    return 10.0 ** (db / 20.0)


def _mix_channel_muted(
    mix_mutes: dict[int, int],
    gain_ich: int | None,
    gain_och: int,
) -> bool | None:
    if gain_ich is None:
        return None
    value = mix_mutes.get(mix_fader_index(gain_ich, gain_och))
    if value is None:
        return None
    return bool(value)


def _fader_cell(
    *,
    gain: float | None,
    muted: bool | None,
) -> dict[str, Any]:
    cell: dict[str, Any] = {"gain": gain}
    db = mix_fader_gain_to_db(gain)
    if db is not None:
        cell["db"] = db
    if muted is not None:
        cell["mute"] = bool(muted)
    return cell


def _column_entry(
    col: MixMatrixColumn,
    mix_stereo: dict[int, int],
) -> dict[str, Any]:
    """Build one matrix column dict including stereo link metadata."""
    entry: dict[str, Any] = {
        "id": col.column_id,
        "label": col.label,
        "kind": col.kind,
        "key": col.key,
    }
    if col.stereo_left_ich is None:
        return entry

    entry["stereo_left_ich"] = col.stereo_left_ich
    linked = bool(mix_stereo.get(col.stereo_left_ich, 0))
    entry["stereo_linked"] = linked
    if col.stereo_label is not None:
        entry["stereo_label"] = col.stereo_label
    ich = col.gain_ich
    if ich is not None and ich % 2 == 1 and linked:
        entry["stereo_hidden"] = True
    return entry


def build_mix_bus_fader_matrix(
    props: dict[str, dict[int, Any]],
    *,
    sample_rate: int | None = None,
    optical_input_mode: int | None = None,
) -> dict[str, Any]:
    """
    Build mix-bus fader matrix: one row per mix bus tab.

    Column order matches CueMix: inputs, reverb, host L/R, bus out.
    """
    mix_faders = props.get("mix_fader", {})
    mix_mutes = props.get("mix_mute", {})
    mix_stereo = props.get("mix_stereo", {})
    bus_faders = props.get("bus_fader", {})
    bus_mute_indices = props.get("bus_mute", {})

    matrix_columns = mix_matrix_columns(
        sample_rate=sample_rate,
        optical_input_mode=optical_input_mode,
    )

    columns: list[dict[str, Any]] = [
        _column_entry(c, mix_stereo) for c in matrix_columns
    ]

    def _gain_at(gain_ich: int | None, gain_och: int) -> float | None:
        if gain_ich is None:
            return None
        return mix_faders.get(mix_fader_index(gain_ich, gain_och))

    buses: list[dict[str, Any]] = []
    for bus_name, gain_och in MIX_BUS_MUTE_INDICES.items():
        host_ich = BUS_HOST_GAIN_ICH.get(bus_name)
        faders: list[dict[str, Any]] = []

        for col in matrix_columns:
            if col.kind in ("input", "reverb"):
                ich = col.gain_ich
                faders.append(
                    _fader_cell(
                        gain=_gain_at(ich, gain_och),
                        muted=_mix_channel_muted(mix_mutes, ich, gain_och),
                    )
                )
            elif col.kind == "host_l":
                faders.append(
                    _fader_cell(
                        gain=_gain_at(host_ich, gain_och),
                        muted=_mix_channel_muted(mix_mutes, host_ich, gain_och),
                    )
                )
            elif col.kind == "host_r":
                host_r = None if host_ich is None else host_ich + 1
                faders.append(
                    _fader_cell(
                        gain=_gain_at(host_r, gain_och),
                        muted=_mix_channel_muted(mix_mutes, host_r, gain_och),
                    )
                )
            elif col.kind == "out":
                bus_mute = stereo_bus_muted(bus_mute_indices, gain_och)
                faders.append(
                    _fader_cell(
                        gain=bus_faders.get(gain_och),
                        muted=bus_mute,
                    )
                )

        bus_mute = stereo_bus_muted(bus_mute_indices, gain_och)
        buses.append(
            {
                "name": bus_name,
                "key": mix_bus_entity_key_part(bus_name),
                "gain_och": gain_och,
                "mute": bus_mute,
                "faders": faders,
            }
        )

    return {
        "columns": columns,
        "buses": buses,
    }
