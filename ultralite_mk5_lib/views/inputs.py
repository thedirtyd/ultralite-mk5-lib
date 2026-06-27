"""Input channel handles (gain, phantom, pad)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultralite_mk5_lib.enums import Inputs
from ultralite_mk5_lib.input_toggles import (
    InputToggleCommand,
    prepare_48v_command,
    prepare_pad_command,
)
from ultralite_mk5_lib.inputs import (
    INPUT_GAIN_CHANNELS,
    MIC_PRE_CHANNELS,
    InputGainChannel,
    MicPreChannel,
    input_gain_byte_to_db,
)
from ultralite_mk5_lib.levels import LevelCommand, prepare_level_command
from ultralite_mk5_lib.views.transport import send_binary, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5


class InputChannel:
    """One analog input gain channel."""

    def __init__(self, device: UltraLiteMk5, channel: InputGainChannel) -> None:
        self._device = device
        self._ch = channel

    @property
    def name(self) -> str:
        return self._ch.name

    @property
    def key(self) -> str:
        return self._ch.key

    @property
    def index(self) -> int:
        return self._ch.index

    @property
    def gain_db(self) -> float | None:
        raw = self._device.state.props.get("input_gain", {}).get(self._ch.index)
        return input_gain_byte_to_db(raw)

    @gain_db.setter
    def gain_db(self, value: float) -> None:
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


class MicInputChannel(InputChannel):
    """Mic/Line In 1–2 with phantom power and pad."""

    def __init__(
        self,
        device: UltraLiteMk5,
        channel: InputGainChannel,
        pre: MicPreChannel,
    ) -> None:
        super().__init__(device, channel)
        self._pre = pre

    @property
    def jack(self) -> str | None:
        raw = self._device.state.props.get("jack_detect", {}).get(self._pre.index)
        if raw is None:
            return None
        return "mic" if int(raw) == 0 else "line"

    @property
    def phantom(self) -> bool | None:
        raw = self._device.state.props.get("input_48v", {}).get(self._pre.index)
        if raw is None:
            return None
        return bool(raw)

    @phantom.setter
    def phantom(self, on: bool) -> None:
        self.set_phantom_token("on" if on else "off")

    @property
    def pad(self) -> bool | None:
        raw = self._device.state.props.get("input_pad", {}).get(self._pre.index)
        if raw is None:
            return None
        return bool(raw)

    @pad.setter
    def pad(self, on: bool) -> None:
        self.set_pad_token("on" if on else "off")

    def set_phantom_token(self, value: str | None = None) -> InputToggleCommand:
        jack_detect = self._device.state.props.get("jack_detect")
        command = prepare_48v_command(self._pre.key_48v, value, jack_detect=jack_detect)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            1 if command.on else 0,
        )
        return command

    def set_pad_token(self, value: str | None = None) -> InputToggleCommand:
        jack_detect = self._device.state.props.get("jack_detect")
        command = prepare_pad_command(self._pre.key_pad, value, jack_detect=jack_detect)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            1 if command.on else 0,
        )
        return command


class InputsView:
    """Analog input channels on the Inputs tab."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    def __getitem__(self, input_id: Inputs | int) -> InputChannel:
        return self._channel_for_index(int(input_id))

    def __iter__(self):
        for ch in INPUT_GAIN_CHANNELS:
            yield self._channel_for_catalog(ch)

    @property
    def mic_pre(self):
        for ch in MIC_PRE_CHANNELS:
            gain = next(c for c in INPUT_GAIN_CHANNELS if c.index == ch.index)
            yield MicInputChannel(self._device, gain, ch)

    def by_key(self, key: str) -> InputChannel:
        normalized = key.strip().upper()
        for ch in INPUT_GAIN_CHANNELS:
            if ch.key == normalized:
                return self._channel_for_catalog(ch)
        raise ValueError(f"unknown input gain key {key!r}")

    def _channel_for_index(self, index: int) -> InputChannel:
        for ch in INPUT_GAIN_CHANNELS:
            if ch.index == index:
                return self._channel_for_catalog(ch)
        raise ValueError(f"unknown input index {index}")

    def _channel_for_catalog(self, ch: InputGainChannel) -> InputChannel:
        for pre in MIC_PRE_CHANNELS:
            if pre.index == ch.index:
                return MicInputChannel(self._device, ch, pre)
        return InputChannel(self._device, ch)
