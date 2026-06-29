"""Mix bus matrix handles (crosspoint faders, bus mute, solo, stereo)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Union

from ultralite_mk5_lib.buses import stereo_bus_muted
from ultralite_mk5_lib.entities import resolve_entity, resolve_stereo_input_gain_ich
from ultralite_mk5_lib.enums import Buses, InputPairs, Inputs
from ultralite_mk5_lib.mix_buses import (
    NUM_MIX_INPUTS,
    STEREO_CAPABLE_MAX_GAIN_ICH,
    db_to_linear_gain,
    mix_fader_gain_to_db,
    mix_fader_index,
)
from ultralite_mk5_lib.levels import LevelCommand, prepare_level_command
from ultralite_mk5_lib.mutes import MuteCommand, prepare_mute_command
from ultralite_mk5_lib.protocol import (
    make_bus_mute_frame,
    make_mix_fader_frame,
    make_mix_mute_frame,
    make_mix_solo_frame,
    make_mix_stereo_frame,
)
from ultralite_mk5_lib.views.transport import send_binary, send_bus_mute_local, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

ChannelSelector = Union[Inputs, InputPairs]


def _db_to_wire_gain(db: float) -> float:
    if db <= 0:
        return 0.0
    return db_to_linear_gain(db)


def _mix_stereo_linked(device: UltraLiteMk5, left_ich: int) -> bool:
    mix_stereo = device.state.props.get("mix_stereo", {})
    return bool(mix_stereo.get(left_ich & 0xFE, 0))


class CrosspointFader:
    """One kiMixFader crosspoint (input channel → output bus)."""

    def __init__(self, device: UltraLiteMk5, gain_ich: int, gain_och: int) -> None:
        self._device = device
        self._gain_ich = gain_ich
        self._gain_och = gain_och

    @property
    def gain_ich(self) -> int:
        return self._gain_ich

    @property
    def gain_och(self) -> int:
        return self._gain_och

    @property
    def flat_index(self) -> int:
        return mix_fader_index(self._gain_ich, self._gain_och)

    @property
    def linked(self) -> bool:
        if self._gain_ich > STEREO_CAPABLE_MAX_GAIN_ICH:
            return False
        return _mix_stereo_linked(self._device, self._gain_ich)

    @property
    def db(self) -> float | None:
        raw = self._device.state.props.get("mix_fader", {}).get(self.flat_index)
        return mix_fader_gain_to_db(raw)

    @db.setter
    def db(self, value: float) -> None:
        self.set_db(value)

    def set_db(self, value: float) -> None:
        self._write_wire_gain(_db_to_wire_gain(value), mirror_stereo=True)

    @property
    def muted(self) -> bool | None:
        mix_mutes = self._device.state.props.get("mix_mute", {})
        raw = mix_mutes.get(self.flat_index)
        if raw is None:
            return None
        return bool(raw)

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_muted(value)

    def set_muted(self, muted: bool) -> None:
        frame = make_mix_mute_frame(self.flat_index, muted)
        send_binary(self._device, frame)
        send_prop_local(self._device, "mix_mute", self.flat_index, 1 if muted else 0)

    @property
    def soloed(self) -> bool | None:
        mix_solos = self._device.state.props.get("mix_solo", {})
        raw = mix_solos.get(self.flat_index)
        if raw is None:
            return None
        return bool(raw)

    @soloed.setter
    def soloed(self, value: bool) -> None:
        self.set_soloed(value)

    def set_soloed(self, soloed: bool) -> None:
        frame = make_mix_solo_frame(self.flat_index, soloed)
        send_binary(self._device, frame)
        send_prop_local(self._device, "mix_solo", self.flat_index, 1 if soloed else 0)

    def set_level_token(self, level: str) -> LevelCommand:
        command = prepare_level_command(self._entity_key(), level)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            command.wire_value,
        )
        if self.linked and self._gain_ich % 2 == 0:
            right = CrosspointFader(self._device, self._gain_ich + 1, self._gain_och)
            right._write_wire_gain(float(command.wire_value), mirror_stereo=False)
        return command

    def set_mute_token(self, value: str | None = None) -> MuteCommand:
        command = prepare_mute_command(self._entity_key(), value)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            1 if command.muted else 0,
        )
        return command

    def _write_wire_gain(self, gain: float, *, mirror_stereo: bool) -> None:
        frame = make_mix_fader_frame(self.flat_index, gain)
        send_binary(self._device, frame)
        send_prop_local(self._device, "mix_fader", self.flat_index, gain)
        if (
            mirror_stereo
            and self.linked
            and self._gain_ich % 2 == 0
            and self._gain_ich + 1 <= STEREO_CAPABLE_MAX_GAIN_ICH
        ):
            right = CrosspointFader(self._device, self._gain_ich + 1, self._gain_och)
            right._write_wire_gain(gain, mirror_stereo=False)

    def _entity_key(self) -> str:
        from ultralite_mk5_lib.entities import _MIX_FADER_TO_KEY

        key = _MIX_FADER_TO_KEY.get((self._gain_ich, self._gain_och))
        if key is None:
            raise ValueError(
                f"no entity key for mix crosspoint ich={self._gain_ich} och={self._gain_och}"
            )
        return key


class StereoPairFader:
    """Stereo pair crosspoint — always writes L and R."""

    def __init__(self, device: UltraLiteMk5, left_ich: int, gain_och: int) -> None:
        self._device = device
        self._left_ich = left_ich
        self._gain_och = gain_och

    @property
    def left(self) -> CrosspointFader:
        return CrosspointFader(self._device, self._left_ich, self._gain_och)

    @property
    def right(self) -> CrosspointFader:
        return CrosspointFader(self._device, self._left_ich + 1, self._gain_och)

    @property
    def linked(self) -> bool:
        return _mix_stereo_linked(self._device, self._left_ich)

    @property
    def db(self) -> float | None:
        return self.left.db

    @db.setter
    def db(self, value: float) -> None:
        gain = _db_to_wire_gain(value)
        self.left._write_wire_gain(gain, mirror_stereo=False)
        self.right._write_wire_gain(gain, mirror_stereo=False)

    def set_level_token(self, level: str) -> LevelCommand:
        command = self.left.set_level_token(level)
        self.right._write_wire_gain(float(command.wire_value), mirror_stereo=False)
        return command


class OutFaderHandle:
    """Bus output level (koBusFader / Out column)."""

    def __init__(self, device: UltraLiteMk5, gain_och: int) -> None:
        self._device = device
        self._gain_och = gain_och

    @property
    def db(self) -> float | None:
        raw = self._device.state.props.get("bus_fader", {}).get(self._gain_och)
        return mix_fader_gain_to_db(raw)

    @db.setter
    def db(self, value: float) -> None:
        self.set_db(value)

    def set_db(self, value: float) -> None:
        from ultralite_mk5_lib.protocol import make_bus_fader_frame

        gain = _db_to_wire_gain(value)
        frame = make_bus_fader_frame(self._gain_och, gain)
        send_binary(self._device, frame)
        send_prop_local(self._device, "bus_fader", self._gain_och, gain)

    def set_level_token(self, level: str) -> LevelCommand:
        from ultralite_mk5_lib.entities import _BUS_FADER_TO_KEY

        key = _BUS_FADER_TO_KEY.get(self._gain_och)
        if key is None:
            raise ValueError(f"no bus out fader key for och={self._gain_och}")
        command = prepare_level_command(key, level)
        send_binary(self._device, command.frame)
        send_prop_local(
            self._device,
            command.prop_key,
            command.index,
            command.wire_value,
        )
        return command

    def set_mute_token(self, value: str | None = None) -> MuteCommand:
        from ultralite_mk5_lib.entities import _BUS_FADER_TO_KEY

        key = _BUS_FADER_TO_KEY.get(self._gain_och)
        if key is None:
            raise ValueError(f"no bus out fader key for och={self._gain_och}")
        command = prepare_mute_command(key, value)
        send_binary(self._device, command.frame)
        send_bus_mute_local(self._device, command.index, command.muted)
        return command


class BusChannelHandle:
    """One input column within a mix bus row."""

    def __init__(
        self,
        device: UltraLiteMk5,
        gain_ich: int,
        gain_och: int,
        *,
        pair: bool = False,
    ) -> None:
        self._device = device
        self._gain_ich = gain_ich
        self._gain_och = gain_och
        self._pair = pair

    @property
    def fader(self) -> CrosspointFader | StereoPairFader:
        if self._pair:
            return StereoPairFader(self._device, self._gain_ich, self._gain_och)
        return CrosspointFader(self._device, self._gain_ich, self._gain_och)


class _ChannelProxy:
    def __init__(self, bus: BusView) -> None:
        self._bus = bus

    def __getitem__(self, selector: ChannelSelector) -> BusChannelHandle:
        return self._bus._channel(selector)


class StereoLinkHandle:
    """Global kiMixStereo link for one input pair."""

    def __init__(self, device: UltraLiteMk5, left_ich: int) -> None:
        self._device = device
        self._left_ich = left_ich & 0xFE

    @property
    def linked(self) -> bool:
        return _mix_stereo_linked(self._device, self._left_ich)

    @linked.setter
    def linked(self, value: bool) -> None:
        self.set_linked(value)

    def set_linked(self, linked: bool) -> None:
        frame = make_mix_stereo_frame(self._left_ich, linked)
        send_binary(self._device, frame)
        send_prop_local(self._device, "mix_stereo", self._left_ich, 1 if linked else 0)

    def set_mode(self, mode: str) -> None:
        mode_lower = mode.strip().lower()
        if mode_lower not in ("stereo", "mono"):
            raise ValueError(f"mode must be 'stereo' or 'mono', got {mode!r}")
        self.set_linked(mode_lower == "stereo")


class _StereoProxy:
    def __init__(self, mix: MixView) -> None:
        self._mix = mix

    def __getitem__(self, input_id: Inputs | int) -> StereoLinkHandle:
        left_ich = int(input_id) & 0xFE
        return StereoLinkHandle(self._mix._device, left_ich)


class BusView:
    """One mix output bus row."""

    def __init__(self, device: UltraLiteMk5, bus: Buses) -> None:
        self._device = device
        self._gain_och = int(bus)

    @property
    def channel(self) -> _ChannelProxy:
        return _ChannelProxy(self)

    def __getitem__(self, selector: ChannelSelector) -> BusChannelHandle:
        return self._channel(selector)

    @property
    def out(self) -> OutFaderHandle:
        return OutFaderHandle(self._device, self._gain_och)

    @property
    def muted(self) -> bool | None:
        bus_mute = self._device.state.props.get("bus_mute", {})
        return stereo_bus_muted(bus_mute, self._gain_och)

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_muted(value)

    def set_muted(self, muted: bool) -> None:
        frame = make_bus_mute_frame(self._gain_och, muted)
        send_binary(self._device, frame)
        send_bus_mute_local(self._device, self._gain_och, muted)

    def solo(self) -> None:
        from ultralite_mk5_lib.mutes import resolve_solo_bus_entity
        from ultralite_mk5_lib.entities import _BUS_FADER_TO_KEY

        key = _BUS_FADER_TO_KEY.get(self._gain_och)
        if key is None:
            raise ValueError(f"no bus out key for och={self._gain_och}")
        _, active_index = resolve_solo_bus_entity(key)
        from ultralite_mk5_lib.buses import solo_bus_mute_indices

        pairs = solo_bus_mute_indices(active_index)
        payload = b"".join(make_bus_mute_frame(index, muted) for index, muted in pairs)
        send_binary(self._device, payload)
        for index, muted in pairs:
            send_bus_mute_local(self._device, index, muted)

    def clear_solos(self) -> None:
        """Clear all kiMixSolo flags on this bus (CueMix clearBusSolos)."""
        start = mix_fader_index(0, self._gain_och)
        payload = b"".join(
            make_mix_solo_frame(start + c, False) for c in range(NUM_MIX_INPUTS)
        )
        send_binary(self._device, payload)
        for c in range(NUM_MIX_INPUTS):
            send_prop_local(self._device, "mix_solo", start + c, 0)

    def _channel(self, selector: ChannelSelector) -> BusChannelHandle:
        if isinstance(selector, InputPairs):
            return BusChannelHandle(
                self._device,
                int(selector),
                self._gain_och,
                pair=True,
            )
        return BusChannelHandle(self._device, int(selector), self._gain_och)


class MixView:
    """Mix bus matrix."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    def __getitem__(self, bus: Buses) -> BusView:
        return BusView(self._device, bus)

    @property
    def stereo(self) -> _StereoProxy:
        return _StereoProxy(self)

    def fader_by_key(self, key: str) -> CrosspointFader | OutFaderHandle:
        ref = resolve_entity(key.strip().upper())
        if ref.kind == "mix_fader":
            if ref.gain_ich is None or ref.gain_och is None:
                raise ValueError(f"mix fader {key!r} missing ich/och")
            return CrosspointFader(self._device, ref.gain_ich, ref.gain_och)
        if ref.kind == "bus_fader":
            if ref.gain_och is None:
                raise ValueError(f"bus fader {key!r} missing och")
            return OutFaderHandle(self._device, ref.gain_och)
        raise ValueError(f"{key!r} is not a mix fader entity")

    def set_stereo_mode(self, key: str, mode: str) -> None:
        gain_ich = resolve_stereo_input_gain_ich(key.strip().upper())
        StereoLinkHandle(self._device, gain_ich).set_mode(mode)
