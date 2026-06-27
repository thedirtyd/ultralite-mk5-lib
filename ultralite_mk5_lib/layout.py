"""Device layout, visibility, and change fingerprints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ultralite_mk5_lib.buses import MIX_BUS_MUTE_INDICES
from ultralite_mk5_lib.entities import (
    DISPLAY_NAMES,
    entity_key_for_mix_fader,
    resolve_entity,
)
from ultralite_mk5_lib.meters import iter_visible_meter_slots
from ultralite_mk5_lib.mix_buses import MixMatrixColumn, mix_matrix_columns
from ultralite_mk5_lib.protocol import (
    optical_input_mode_wire_from_snap,
    optical_output_mode_wire_from_snap,
)

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5


def fpga_patch_from_props(props: dict[str, dict[int, Any]]) -> dict[int, int]:
    return {int(k): int(v) for k, v in props.get("fpga_patch", {}).items()}


def _mix_stereo_hidden(col: MixMatrixColumn, mix_stereo: dict[int, int]) -> bool:
    if col.stereo_left_ich is None or col.gain_ich is None:
        return False
    return col.gain_ich % 2 == 1 and bool(mix_stereo.get(col.stereo_left_ich, 0))


class LayoutView:
    """Mix/meter layout derived from live device state."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    def _snap(self) -> dict[str, Any]:
        return self._device.state.snapshot()

    def columns(self) -> tuple[MixMatrixColumn, ...]:
        snap = self._snap()
        return mix_matrix_columns(
            sample_rate=snap.get("sample_rate"),
            optical_input_mode=optical_input_mode_wire_from_snap(snap),
        )

    def visible_fader_keys(self) -> list[str]:
        snap = self._snap()
        props = snap.get("props", {})
        mix_stereo = props.get("mix_stereo", {})
        keys: list[str] = []
        for bus_name in MIX_BUS_MUTE_INDICES:
            if bus_name == "reverb":
                continue
            for col in self.columns():
                if _mix_stereo_hidden(col, mix_stereo):
                    continue
                if col.kind == "host" and col.native_bus is not None and bus_name != col.native_bus:
                    continue
                if col.kind == "out":
                    from ultralite_mk5_lib.entities import _BUS_FADER_TO_KEY

                    key = _BUS_FADER_TO_KEY.get(MIX_BUS_MUTE_INDICES[bus_name])
                    if key:
                        keys.append(key)
                    continue
                if col.gain_ich is None:
                    continue
                keys.append(entity_key_for_mix_fader(bus_name, col.key))
        return keys

    def visible_meter_keys(self) -> list[str]:
        snap = self._snap()
        return [entry.key for entry in iter_visible_meter_slots(
            sample_rate=snap.get("sample_rate"),
            optical_input_mode=optical_input_mode_wire_from_snap(snap),
            optical_output_mode=optical_output_mode_wire_from_snap(snap),
        )]

    def fingerprint(self) -> tuple[Any, ...]:
        snap = self._snap()
        props = snap.get("props", {})
        return (
            snap.get("sample_rate"),
            optical_input_mode_wire_from_snap(snap),
            optical_output_mode_wire_from_snap(snap),
            tuple(sorted(props.get("mix_stereo", {}).items())),
            tuple(sorted(fpga_patch_from_props(props).items())),
        )

    def props_fingerprint(self) -> tuple[Any, ...]:
        props = self._snap().get("props", {})
        keys = (
            "sample_rate",
            "optical_mode",
            "mix_stereo",
            "bus_mute",
            "bus_fader",
            "mix_fader",
            "main_trim",
            "output_trim",
            "input_gain",
            "input_48v",
            "input_pad",
            "jack_detect",
            "fpga_patch",
        )
        return tuple(
            (key, tuple(sorted(props.get(key, {}).items())))
            for key in keys
            if key in props
        )

    def display_name(self, key: str) -> str:
        normalized = key.strip().upper()
        if normalized in DISPLAY_NAMES:
            return DISPLAY_NAMES[normalized]
        return resolve_entity(normalized).display
