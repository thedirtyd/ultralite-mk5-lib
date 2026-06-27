"""Meter peak handles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from ultralite_mk5_lib.enums import InputMeters, MixMeters, OutputMeters
from ultralite_mk5_lib.meters import (
    METER_SLOTS,
    MeterSlot,
    iter_visible_meter_slots,
    meter_entry_visible,
    resolve_meter_slot,
)
from ultralite_mk5_lib.protocol import (
    OPTICAL_INPUT_MODE_INDEX,
    OPTICAL_OUTPUT_MODE_INDEX,
    optical_mode_wire_from_props,
)
from ultralite_mk5_lib.state import K_MIN_METER_DB

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

E = TypeVar("E")


def _fpga_patch_from_props(props: dict) -> dict[int, int]:
    return {int(k): int(v) for k, v in props.get("fpga_patch", {}).items()}


def _slot_for_input_meter(member: InputMeters) -> MeterSlot | None:
    slot_val = int(member)
    for entry in METER_SLOTS:
        if entry.slot == slot_val:
            return entry
    return None


def _slot_for_mix_meter(member: MixMeters) -> MeterSlot | None:
    slot_val = int(member)
    for entry in METER_SLOTS:
        if entry.slot == slot_val:
            return entry
    return None


_OUTPUT_METER_SENTINELS: dict[OutputMeters, str] = {
    OutputMeters.SpdifOutL: "Outputs - S/PDIF Out L",
    OutputMeters.SpdifOutR: "Outputs - S/PDIF Out R",
    OutputMeters.OpticalOut01: "Outputs - Optical Out 1",
    OutputMeters.OpticalOut02: "Outputs - Optical Out 2",
    OutputMeters.OpticalOut03: "Outputs - Optical Out 3",
    OutputMeters.OpticalOut04: "Outputs - Optical Out 4",
    OutputMeters.OpticalOut05: "Outputs - Optical Out 5",
    OutputMeters.OpticalOut06: "Outputs - Optical Out 6",
    OutputMeters.OpticalOut07: "Outputs - Optical Out 7",
    OutputMeters.OpticalOut08: "Outputs - Optical Out 8",
}


def _slot_for_output_meter(member: OutputMeters) -> MeterSlot | None:
    slot_val = int(member)
    if slot_val >= 0:
        for entry in METER_SLOTS:
            if entry.slot == slot_val:
                return entry
        return None
    name = _OUTPUT_METER_SENTINELS.get(member)
    if name is None:
        return None
    for entry in METER_SLOTS:
        if entry.name == name:
            return entry
    return None


class MeterHandle:
    def __init__(self, device: UltraLiteMk5, entry: MeterSlot, resolved_slot: int) -> None:
        self._device = device
        self._entry = entry
        self._slot = resolved_slot

    @property
    def name(self) -> str:
        return self._entry.name

    @property
    def key(self) -> str:
        return self._entry.key

    @property
    def slot(self) -> int:
        return self._slot

    @property
    def db(self) -> float | None:
        if not self._device.state.meters_received:
            return None
        meters = self._device.state.meters
        if self._slot < 0 or self._slot >= len(meters):
            return None
        value = meters[self._slot]
        if value <= K_MIN_METER_DB:
            return K_MIN_METER_DB
        return value

    @property
    def visible(self) -> bool:
        props = self._device.state.props
        sample_rate = props.get("sample_rate", {}).get(0)
        return meter_entry_visible(
            self._entry,
            sample_rate=sample_rate,
            optical_input_mode=optical_mode_wire_from_props(
                props, OPTICAL_INPUT_MODE_INDEX
            ),
            optical_output_mode=optical_mode_wire_from_props(
                props, OPTICAL_OUTPUT_MODE_INDEX
            ),
        )


class MeterGroupView(Generic[E]):
    def __init__(
        self,
        device: UltraLiteMk5,
        *,
        resolver,
    ) -> None:
        self._device = device
        self._resolver = resolver

    def __getitem__(self, member: E) -> MeterHandle:
        entry = self._resolver(member)
        if entry is None:
            raise ValueError(f"unknown meter {member!r}")
        fpga = _fpga_patch_from_props(self._device.state.props)
        slot = resolve_meter_slot(entry, fpga_patch=fpga)
        return MeterHandle(self._device, entry, slot)

    @property
    def visible(self) -> list[MeterHandle]:
        props = self._device.state.props
        sample_rate = props.get("sample_rate", {}).get(0)
        fpga = _fpga_patch_from_props(props)
        handles: list[MeterHandle] = []
        for entry in iter_visible_meter_slots(
            sample_rate=sample_rate,
            optical_input_mode=optical_mode_wire_from_props(
                props, OPTICAL_INPUT_MODE_INDEX
            ),
            optical_output_mode=optical_mode_wire_from_props(
                props, OPTICAL_OUTPUT_MODE_INDEX
            ),
        ):
            prefix = entry.name.partition(" - ")[0]
            if not self._group_matches(prefix):
                continue
            slot = resolve_meter_slot(entry, fpga_patch=fpga)
            handles.append(MeterHandle(self._device, entry, slot))
        return handles

    def _group_matches(self, prefix: str) -> bool:
        raise NotImplementedError


class InputMeterGroupView(MeterGroupView[InputMeters]):
    def _group_matches(self, prefix: str) -> bool:
        return prefix == "Inputs"


class MixMeterGroupView(MeterGroupView[MixMeters]):
    def _group_matches(self, prefix: str) -> bool:
        return prefix == "Mix"


class OutputMeterGroupView(MeterGroupView[OutputMeters]):
    def _group_matches(self, prefix: str) -> bool:
        return prefix == "Outputs"


class MetersView:
    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    @property
    def input(self) -> InputMeterGroupView:
        return InputMeterGroupView(self._device, resolver=_slot_for_input_meter)

    @property
    def mix(self) -> MixMeterGroupView:
        return MixMeterGroupView(self._device, resolver=_slot_for_mix_meter)

    @property
    def output(self) -> OutputMeterGroupView:
        return OutputMeterGroupView(self._device, resolver=_slot_for_output_meter)

    @property
    def visible(self) -> list[MeterHandle]:
        return self.input.visible + self.mix.visible + self.output.visible

    @property
    def received(self) -> bool:
        return self._device.state.meters_received

    @property
    def all_db(self) -> list[float]:
        return self._device.state.meters

    def by_key(self, key: str) -> MeterHandle:
        normalized = key.strip().upper()
        for entry in METER_SLOTS:
            if entry.key == normalized:
                fpga = _fpga_patch_from_props(self._device.state.props)
                slot = resolve_meter_slot(entry, fpga_patch=fpga)
                return MeterHandle(self._device, entry, slot)
        raise ValueError(f"unknown meter key {key!r}")
