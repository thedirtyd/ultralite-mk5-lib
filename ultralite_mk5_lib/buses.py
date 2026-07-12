"""Mix bus naming and koBusMute helpers for UltraLite mk5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BusKind = Literal["main", "line", "phones", "reverb"]


@dataclass(frozen=True, slots=True)
class MixBusRow:
    """One visible mix bus row (tab/strip) in the current layout."""

    name: str
    gain_och: int
    kind: BusKind
    pair_left_och: int
    pair_right_och: int | None = None
    stereo_linked: bool = True
    is_pair_right: bool = False


_LINE_BUS_LEFT_TO_CHAN: dict[int, int] = {
    2: 3,
    4: 5,
    6: 7,
    8: 9,
}

_FIXED_STEREO_ROWS: tuple[MixBusRow, ...] = (
    MixBusRow(
        name="main 1-2",
        gain_och=0,
        kind="main",
        pair_left_och=0,
        pair_right_och=1,
        stereo_linked=True,
    ),
    MixBusRow(
        name="phones",
        gain_och=10,
        kind="phones",
        pair_left_och=10,
        pair_right_och=11,
        stereo_linked=True,
    ),
)

REVERB_BUS_NAME = "reverb"
REVERB_BUS_MUTE_INDEX = 12

_REVERB_ROW = MixBusRow(
    name=REVERB_BUS_NAME,
    gain_och=REVERB_BUS_MUTE_INDEX,
    kind="reverb",
    pair_left_och=12,
    pair_right_och=13,
    stereo_linked=True,
)

# Entity/export map: include both paired and mono line bus names.
MIX_BUS_MUTE_INDICES: dict[str, int] = {
    "main 1-2": 0,
    "phones": 10,
    "line 3/4": 2,
    "line 3": 2,
    "line 4": 3,
    "line 5/6": 4,
    "line 5": 4,
    "line 6": 5,
    "line 7/8": 6,
    "line 7": 6,
    "line 8": 7,
    "line 9/10": 8,
    "line 9": 8,
    "line 10": 9,
    REVERB_BUS_NAME: REVERB_BUS_MUTE_INDEX,
}

# Friendly default order for static exports.
MIX_BUS_NAMES: tuple[str, ...] = (
    "main 1-2",
    "phones",
    "line 3/4",
    "line 5/6",
    "line 7/8",
    "line 9/10",
    REVERB_BUS_NAME,
)

# Active solo targets (physical output rows); reverb excluded.
SOLO_BUS_MUTE_INDICES: tuple[int, ...] = (0, 10, 2, 3, 4, 5, 6, 7, 8, 9)


def _line_pair_name(left: int, *, linked: bool, right: bool = False) -> str:
    first = _LINE_BUS_LEFT_TO_CHAN[left]
    if linked:
        return f"line {first}/{first + 1}"
    if right:
        return f"line {first + 1}"
    return f"line {first}"


def _line_pair_linked(bus_stereo: dict[int, int], left: int) -> bool:
    # CueMix defaults line output pairs to linked stereo until koMixStereo arrives.
    return bool(bus_stereo.get(left, 1))


def iter_active_mix_bus_rows(bus_stereo: dict[int, int]) -> tuple[MixBusRow, ...]:
    """Visible output bus rows for current koMixStereo state."""
    rows: list[MixBusRow] = list(_FIXED_STEREO_ROWS)
    for left in sorted(_LINE_BUS_LEFT_TO_CHAN):
        right = left + 1
        linked = _line_pair_linked(bus_stereo, left)
        if linked:
            rows.append(
                MixBusRow(
                    name=_line_pair_name(left, linked=True),
                    gain_och=left,
                    kind="line",
                    pair_left_och=left,
                    pair_right_och=right,
                    stereo_linked=True,
                )
            )
            continue
        rows.extend(
            (
                MixBusRow(
                    name=_line_pair_name(left, linked=False, right=False),
                    gain_och=left,
                    kind="line",
                    pair_left_och=left,
                    pair_right_och=right,
                    stereo_linked=False,
                    is_pair_right=False,
                ),
                MixBusRow(
                    name=_line_pair_name(left, linked=False, right=True),
                    gain_och=right,
                    kind="line",
                    pair_left_och=left,
                    pair_right_och=right,
                    stereo_linked=False,
                    is_pair_right=True,
                ),
            )
        )
    rows.append(_REVERB_ROW)
    return tuple(rows)


def resolve_bus_stereo_left_gain_och(gain_och: int) -> int:
    """Return koMixStereo left gain_och for a line output row."""
    left = gain_och & 0xFE
    if left not in _LINE_BUS_LEFT_TO_CHAN:
        raise ValueError(
            f"gain_och {gain_och} is not a stereo-configurable line output bus"
        )
    return left


def output_bus_write_ignored(
    gain_och: int,
    bus_stereo: dict[int, int],
) -> bool:
    """True when writes to this output bus should be ignored while paired."""
    if gain_och % 2 == 0:
        return False
    left = gain_och - 1
    if left not in _LINE_BUS_LEFT_TO_CHAN:
        return False
    return _line_pair_linked(bus_stereo, left)


def bus_row_muted(indices: dict[int, int], row: MixBusRow) -> bool | None:
    """Return mute state for one visible mix bus row."""
    value = indices.get(row.gain_och)
    if row.stereo_linked and row.pair_right_och is not None:
        right = indices.get(row.pair_right_och)
        if value is None and right is None:
            return None
        return bool(value or 0) or bool(right or 0)
    if value is None:
        return None
    return bool(value)


def solo_bus_mute_indices(active_index: int) -> list[tuple[int, bool]]:
    """Return (index, muted) pairs to solo one output bus."""
    return [
        (index, index != active_index)
        for index in SOLO_BUS_MUTE_INDICES
    ]


def stereo_bus_muted(indices: dict[int, int], left_index: int) -> bool | None:
    """
    Return koBusMute state for a stereo bus (gainOCh = left channel index).

    CueMix binds the bus-strip MUTE to the left index only, but the device may
    hold mute bytes for both channels; treat the bus as muted if either is set.
    """
    left = indices.get(left_index)
    right = indices.get(left_index + 1)
    if left is None and right is None:
        return None
    return bool(left or 0) or bool(right or 0)
