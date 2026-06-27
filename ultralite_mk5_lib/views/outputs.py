"""Output trim handles (monitor section and line outputs)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultralite_mk5_lib.enums import LineOutputs, Monitors
from ultralite_mk5_lib.levels import LevelCommand, prepare_level_command
from ultralite_mk5_lib.outputs import (
    MAIN_TRIM_INDEX,
    MONITOR_TRIM_CHANNELS,
    MUTE_ENABLE_INDEX,
    OUTPUT_TRIM_CHANNELS,
    MonitorTrimChannel,
    OutputTrimChannel,
    trim_byte_to_db,
)

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

from ultralite_mk5_lib.views.transport import send_binary, send_prop_local


class MonitorTrimHandle:
    """Main Out or Phones monitor trim."""

    def __init__(self, device: UltraLiteMk5, channel: MonitorTrimChannel) -> None:
        self._device = device
        self._ch = channel

    @property
    def name(self) -> str:
        return self._ch.name

    @property
    def key(self) -> str:
        return self._ch.key

    @property
    def trim_db(self) -> float | None:
        props = self._device.state.props
        if self._ch.prop == "main_trim":
            raw = props.get("main_trim", {}).get(self._ch.index)
        else:
            raw = props.get("output_trim", {}).get(self._ch.index)
        return trim_byte_to_db(raw)

    @trim_db.setter
    def trim_db(self, value: float) -> None:
        self.set_trim_db(value)

    def set_trim_db(self, value: float) -> None:
        self.set_level_token(str(int(value) if value == int(value) else value))

    @property
    def muted(self) -> bool | None:
        if self._ch.prop != "main_trim":
            return None
        raw = self._device.state.props.get("mute_enable", {}).get(MUTE_ENABLE_INDEX)
        if raw is None:
            return None
        return bool(raw)

    def set_level_token(self, level: str) -> LevelCommand:
        command = prepare_level_command(self._ch.key, level)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            command.wire_value,
        )
        return command


class LineOutputTrimHandle:
    """One line output koTrim."""

    def __init__(self, device: UltraLiteMk5, channel: OutputTrimChannel) -> None:
        self._device = device
        self._ch = channel

    @property
    def name(self) -> str:
        return self._ch.name

    @property
    def key(self) -> str:
        return self._ch.key

    @property
    def trim_db(self) -> float | None:
        raw = self._device.state.props.get("output_trim", {}).get(self._ch.trim_index)
        return trim_byte_to_db(raw)

    @trim_db.setter
    def trim_db(self, value: float) -> None:
        self.set_trim_db(value)

    def set_trim_db(self, value: float) -> None:
        self.set_level_token(str(int(value) if value == int(value) else value))

    def set_level_token(self, level: str) -> LevelCommand:
        command = prepare_level_command(self._ch.key, level)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            command.wire_value,
        )
        return command


_MONITOR_BY_KIND = {ch.key: ch for ch in MONITOR_TRIM_CHANNELS}
_MONITOR_BY_ENUM = {
    Monitors.Main: MONITOR_TRIM_CHANNELS[0],
    Monitors.Phones: MONITOR_TRIM_CHANNELS[1],
}
_LINE_BY_TRIM_INDEX = {ch.trim_index: ch for ch in OUTPUT_TRIM_CHANNELS}


class _MonitorProxy:
    def __init__(self, view: OutputsView) -> None:
        self._view = view

    def __getitem__(self, monitor: Monitors) -> MonitorTrimHandle:
        return MonitorTrimHandle(self._view._device, _MONITOR_BY_ENUM[monitor])


class _LineProxy:
    def __init__(self, view: OutputsView) -> None:
        self._view = view

    def __getitem__(self, output: LineOutputs) -> LineOutputTrimHandle:
        ch = _LINE_BY_TRIM_INDEX[int(output)]
        return LineOutputTrimHandle(self._view._device, ch)

    def __iter__(self):
        for ch in OUTPUT_TRIM_CHANNELS:
            yield LineOutputTrimHandle(self._view._device, ch)


class OutputsView:
    """Output trims (monitor section and line outputs)."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    @property
    def monitor(self) -> _MonitorProxy:
        return _MonitorProxy(self)

    @property
    def line(self) -> _LineProxy:
        return _LineProxy(self)

    def trim_by_key(self, key: str) -> MonitorTrimHandle | LineOutputTrimHandle:
        normalized = key.strip().upper()
        if normalized in _MONITOR_BY_KIND:
            return MonitorTrimHandle(self._device, _MONITOR_BY_KIND[normalized])
        for ch in OUTPUT_TRIM_CHANNELS:
            if ch.key == normalized:
                return LineOutputTrimHandle(self._device, ch)
        raise ValueError(f"unknown output trim key {key!r}")
