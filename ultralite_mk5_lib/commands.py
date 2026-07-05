"""CLI command routing through domain views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultralite_mk5_lib.entities import resolve_entity
from ultralite_mk5_lib.input_toggles import InputToggleCommand
from ultralite_mk5_lib.levels import LevelCommand
from ultralite_mk5_lib.mutes import MuteCommand, prepare_mute_command, resolve_solo_bus_entity
from ultralite_mk5_lib.pans import (
    PanCommand,
    prepare_pan_command,
)
from ultralite_mk5_lib.solos import (
    SoloCommand,
    prepare_solo_command,
    resolve_clear_mix_solo_entity,
)
from ultralite_mk5_lib.views.transport import send_binary, send_bus_mute_local, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5


def apply_set_level(device: UltraLiteMk5, key: str, level: str) -> LevelCommand:
    """Route set-level by entity kind to the matching domain handle."""
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind == "input_gain":
        return device.inputs.by_key(normalized).set_level_token(level)
    if ref.kind in ("main_trim", "output_trim"):
        return device.outputs.trim_by_key(normalized).set_level_token(level)
    if ref.kind in ("mix_fader", "bus_fader"):
        return device.mix.fader_by_key(normalized).set_level_token(level)
    raise ValueError(
        f"{normalized!r} cannot be set with set-level; "
        "use MIXBUSFADER_*, INPUTGAIN_*, VOLUME_*, or OUTPUTTRIM_* keys"
    )


def apply_set_mute(device: UltraLiteMk5, key: str, value: str | None = None) -> MuteCommand:
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind == "mix_fader":
        return device.mix.fader_by_key(normalized).set_mute_token(value)
    if ref.kind == "bus_fader":
        return device.mix.fader_by_key(normalized).set_mute_token(value)
    command = prepare_mute_command(normalized, value)
    send_binary(device, command.frame)
    if command.prop_key == "bus_mute":
        send_bus_mute_local(device, command.index, command.muted)
    else:
        send_prop_local(
            device,
            command.prop_key,
            command.index,
            1 if command.muted else 0,
        )
    return command


def apply_solo_output_bus(device: UltraLiteMk5, key: str) -> None:
    _, active_index = resolve_solo_bus_entity(key)
    from ultralite_mk5_lib.buses import solo_bus_mute_indices
    from ultralite_mk5_lib.protocol import make_bus_mute_frame

    pairs = solo_bus_mute_indices(active_index)
    payload = b"".join(make_bus_mute_frame(index, muted) for index, muted in pairs)
    send_binary(device, payload)
    for index, muted in pairs:
        send_bus_mute_local(device, index, muted)


def apply_set_solo(
    device: UltraLiteMk5,
    key: str,
    value: str | None = None,
) -> SoloCommand:
    """Solo or unsolo one mix crosspoint (kiMixSolo)."""
    command = prepare_solo_command(key, value)
    send_binary(device, command.frame)
    send_prop_local(
        device,
        command.prop_key,
        command.index,
        1 if command.soloed else 0,
    )
    return command


def apply_set_pan(
    device: UltraLiteMk5,
    key: str,
    value: str | float | None = None,
) -> PanCommand:
    """Set pan on one mix crosspoint (kiMixPan)."""
    command = prepare_pan_command(key, value)
    device.mix.fader_by_key(command.key).set_pan(command.pan)
    return command


def apply_clear_mix_solo(device: UltraLiteMk5, key: str) -> None:
    """Clear all kiMixSolo flags on one mix output bus."""
    from ultralite_mk5_lib.enums import Buses

    _, gain_och = resolve_clear_mix_solo_entity(key)
    device.mix[Buses(gain_och)].clear_solos()


def apply_set_input_48v(
    device: UltraLiteMk5,
    key: str,
    value: str | None = None,
) -> InputToggleCommand:
    normalized = key.strip().upper()
    from ultralite_mk5_lib.inputs import MIC_PRE_CHANNELS
    from ultralite_mk5_lib.views.inputs import MicInputChannel

    for pre in MIC_PRE_CHANNELS:
        if pre.key_48v == normalized:
            ch = device.inputs[pre.index]
            if not isinstance(ch, MicInputChannel):
                raise ValueError(f"{key!r} is not a mic pre channel")
            return ch.set_phantom_token(value)
    raise ValueError(f"unknown 48V key {key!r}")


def apply_set_input_pad(
    device: UltraLiteMk5,
    key: str,
    value: str | None = None,
) -> InputToggleCommand:
    normalized = key.strip().upper()
    from ultralite_mk5_lib.inputs import MIC_PRE_CHANNELS
    from ultralite_mk5_lib.views.inputs import MicInputChannel

    for pre in MIC_PRE_CHANNELS:
        if pre.key_pad == normalized:
            ch = device.inputs[pre.index]
            if not isinstance(ch, MicInputChannel):
                raise ValueError(f"{key!r} is not a mic pre channel")
            return ch.set_pad_token(value)
    raise ValueError(f"unknown pad key {key!r}")


def apply_set_channel_stereo_mode(device: UltraLiteMk5, key: str, mode: str) -> None:
    device.mix.set_stereo_mode(key, mode)


def apply_set_eq(device: UltraLiteMk5, key: str, param: str, value: str) -> None:
    device.eq.by_key(key).set_param(param, value)


def apply_set_sample_rate(device: UltraLiteMk5, rate: int) -> None:
    device.settings.sample_rate = rate


def apply_set_optical_input_mode(device: UltraLiteMk5, mode: str) -> None:
    device.settings.optical_input_mode = mode


def apply_set_optical_output_mode(device: UltraLiteMk5, mode: str) -> None:
    device.settings.optical_output_mode = mode


def apply_set_input_monitor(
    device: UltraLiteMk5,
    bus: str,
    input_index: int,
    value: str | None = None,
) -> "InputMonitorState":
    """Enable, disable, or toggle HOME-tab input monitoring on main or phones."""
    from ultralite_mk5_lib.input_monitor import (
        input_monitor_button_state,
        input_monitor_gain_och,
        resolve_input_monitor_enabled,
        set_input_monitor,
        validate_input_monitor_index,
    )

    gain_och = input_monitor_gain_och(bus)
    validate_input_monitor_index(input_index)
    current = input_monitor_button_state(device.state.props, input_index, gain_och)
    enabled = resolve_input_monitor_enabled(value, current=current)
    set_input_monitor(device, input_index, gain_och, enabled=enabled)
    return input_monitor_button_state(device.state.props, input_index, gain_och)
