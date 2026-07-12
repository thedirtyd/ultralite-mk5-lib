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
    mix_input_entity_key,
)
from ultralite_mk5_lib.meters import (
    optical_input_meter_count,
    sample_rate_index,
)

NUM_MIX_INPUTS = 32

ColumnKind = Literal["input", "reverb", "host", "out"]

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

_HOST_LEFT_ICH_TO_LABEL: dict[int, str] = {
    18: "Host 1-2",
    28: "Host Phones",
    20: "Host 3-4",
    22: "Host 5-6",
    24: "Host 7-8",
    26: "Host 9-10",
}

_HOST_CHANNEL_LABELS: dict[int, tuple[str, str]] = {
    18: ("Host 1", "Host 2"),
    20: ("Host 3", "Host 4"),
    22: ("Host 5", "Host 6"),
    24: ("Host 7", "Host 8"),
    26: ("Host 9", "Host 10"),
    28: ("Host Phones 1", "Host Phones 2"),
}

_HOST_NATIVE_BUS: dict[int, str | None] = {
    18: None,
    20: "line 3-4",
    22: "line 5-6",
    24: "line 7-8",
    26: "line 9-10",
    28: "phones",
}

_SPDIF_NUM_CH = (2, 2, 2, 2, 0, 0)
_REVERB_NUM_CH = (2, 2, 2, 2, 0, 0)
# kiMixStereo indices for linkable pairs (mic through host returns; reverb excluded).
STEREO_CAPABLE_MAX_GAIN_ICH = 29


@dataclass(frozen=True, slots=True)
class MixMatrixColumn:
    """One column in the mix-bus fader matrix."""

    column_id: str
    label: str
    kind: ColumnKind
    key: str
    gain_ich: int | None = None
    native_bus: str | None = None
    stereo_left_ich: int | None = None
    stereo_label: str | None = None


def _make_stereo_label(left: str, right: str) -> str:
    """Combine left/right labels (e.g. Optical 1 + Optical 2 → Optical 1-2)."""
    i = 0
    limit = min(len(left), len(right))
    while i < limit and left[i] == right[i]:
        i += 1
    return f"{left[:i]}{left[i:]}-{right[i:]}"


def _is_stereo_capable(col: MixMatrixColumn) -> bool:
    return (
        col.kind in ("input", "host")
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
            if left_col.kind == "host":
                stereo_label = _HOST_LEFT_ICH_TO_LABEL.get(left_ich)
            else:
                stereo_label = _make_stereo_label(left_col.label, right_col.label)
        updated.append(
            replace(
                col,
                stereo_left_ich=left_ich,
                stereo_label=stereo_label,
            )
        )
    return tuple(updated)


def _mix_column(
    label: str,
    column_id: str,
    kind: ColumnKind,
    gain_ich: int | None = None,
    *,
    native_bus: str | None = None,
) -> MixMatrixColumn:
    return MixMatrixColumn(
        column_id,
        label,
        kind,
        mix_channel_entity_key_part(label),
        gain_ich,
        native_bus,
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
        cols, prefix="mic", label_prefix="Mic In ", start_ich=0, count=2
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
        _append_mono_channels(
            cols, prefix="spdif", label_prefix="S/PDIF ", start_ich=8, count=2
        )

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

    for left_ich in _HOST_LEFT_ICH_TO_LABEL:
        left_label, right_label = _HOST_CHANNEL_LABELS[left_ich]
        native = _HOST_NATIVE_BUS[left_ich]
        cols.append(
            _mix_column(
                left_label,
                f"host-{left_ich}-l",
                "host",
                left_ich,
                native_bus=native,
            )
        )
        cols.append(
            _mix_column(
                right_label,
                f"host-{left_ich}-r",
                "host",
                left_ich + 1,
                native_bus=native,
            )
        )
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


@dataclass(frozen=True, slots=True)
class MixInputChannel:
    """One stereo-capable mix input row (kiMixStereo / global input channel)."""

    name: str
    gain_ich: int
    key: str


def _mix_input_channel(col: MixMatrixColumn) -> MixInputChannel:
    assert col.gain_ich is not None
    return MixInputChannel(col.label, col.gain_ich, mix_input_entity_key(col.label))


MIX_HOST_INPUT_CHANNELS: tuple[MixInputChannel, ...] = tuple(
    MixInputChannel(label, ich, mix_input_entity_key(label))
    for ich, label in _HOST_LEFT_ICH_TO_LABEL.items()
)

MIX_INPUT_CHANNELS: tuple[MixInputChannel, ...] = (
    tuple(
        _mix_input_channel(col)
        for col in FULL_MIX_MATRIX_COLUMNS
        if col.kind == "input" and col.gain_ich is not None
    )
    + MIX_HOST_INPUT_CHANNELS
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


def _mix_channel_soloed(
    mix_solos: dict[int, int],
    gain_ich: int | None,
    gain_och: int,
) -> bool | None:
    if gain_ich is None:
        return None
    value = mix_solos.get(mix_fader_index(gain_ich, gain_och))
    if value is None:
        return None
    return bool(value)


def _mix_channel_pan(
    mix_pans: dict[int, float],
    gain_ich: int | None,
    gain_och: int,
) -> float | None:
    if gain_ich is None:
        return None
    value = mix_pans.get(mix_fader_index(gain_ich, gain_och))
    if value is None:
        return None
    return float(value)


def _fader_cell(
    *,
    gain: float | None,
    muted: bool | None,
    soloed: bool | None = None,
    pan: float | None = None,
) -> dict[str, Any]:
    cell: dict[str, Any] = {"gain": gain}
    db = mix_fader_gain_to_db(gain)
    if db is not None:
        cell["db"] = db
    if muted is not None:
        cell["mute"] = bool(muted)
    if soloed is not None:
        cell["solo"] = bool(soloed)
    if pan is not None:
        cell["pan"] = pan
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
    if col.native_bus is not None:
        entry["native_bus"] = col.native_bus
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

    Column order matches CueMix: inputs, reverb, host returns, bus out.
    """
    mix_faders = props.get("mix_fader", {})
    mix_mutes = props.get("mix_mute", {})
    mix_solos = props.get("mix_solo", {})
    mix_pans = props.get("mix_pan", {})
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
        faders: list[dict[str, Any]] = []

        for col in matrix_columns:
            if col.kind in ("input", "reverb"):
                ich = col.gain_ich
                faders.append(
                    _fader_cell(
                        gain=_gain_at(ich, gain_och),
                        muted=_mix_channel_muted(mix_mutes, ich, gain_och),
                        soloed=_mix_channel_soloed(mix_solos, ich, gain_och),
                        pan=_mix_channel_pan(mix_pans, ich, gain_och),
                    )
                )
            elif col.kind == "host":
                if col.native_bus is not None and bus_name != col.native_bus:
                    faders.append({"hidden": True})
                else:
                    assert col.gain_ich is not None
                    faders.append(
                        _fader_cell(
                            gain=_gain_at(col.gain_ich, gain_och),
                            muted=_mix_channel_muted(mix_mutes, col.gain_ich, gain_och),
                            soloed=_mix_channel_soloed(
                                mix_solos, col.gain_ich, gain_och
                            ),
                            pan=_mix_channel_pan(mix_pans, col.gain_ich, gain_och),
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
