"""Mix bus names and koBusMute indices for UltraLite mk5."""

from __future__ import annotations

# koBusMute indices (gainOCh) from dev.js mixOutputs / mixmgr.js.
# These are the mixer output-bus MUTE buttons (not per-input mix mutes).
MIX_BUS_MUTE_INDICES: dict[str, int] = {
    "main 1-2": 0,
    "phones": 10,
    "line 3-4": 2,
    "line 5-6": 4,
    "line 7-8": 6,
    "line 9-10": 8,
    "reverb": 12,
}

# Friendly display order for state reports and tables.
MIX_BUS_NAMES: tuple[str, ...] = tuple(MIX_BUS_MUTE_INDICES.keys())

REVERB_BUS_NAME = "reverb"
REVERB_BUS_MUTE_INDEX = MIX_BUS_MUTE_INDICES[REVERB_BUS_NAME]


def solo_bus_mute_indices(active_index: int) -> list[tuple[int, bool]]:
    """Return (index, muted) pairs to solo one output bus."""
    return [
        (index, index != active_index)
        for name, index in MIX_BUS_MUTE_INDICES.items()
        if name != REVERB_BUS_NAME
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
