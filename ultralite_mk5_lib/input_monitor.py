"""CueMix HOME tab input monitoring (direct-to-main/phones mix preset)."""

from __future__ import annotations

import math
from typing import Any, Literal

from ultralite_mk5_lib.enums import Buses
from ultralite_mk5_lib.mix_buses import mix_fader_index
from ultralite_mk5_lib.pans import PAN_CENTER

InputMonitorState = Literal["off", "on", "edited"]

# CueMix dev.js mixOutputs — mains.iBus / phones.iBus
INPUT_MONITOR_MAIN_OCH = 0
INPUT_MONITOR_PHONES_OCH = 10

_ANALOG_INPUT_MAX_INDEX = 7
_FADER_ON_GAIN = 1.0


def input_monitor_gain_och(bus: str) -> int:
    """Map websocket bus name to mix output channel index."""
    normalized = bus.strip().lower()
    if normalized == "main":
        return INPUT_MONITOR_MAIN_OCH
    if normalized == "phones":
        return INPUT_MONITOR_PHONES_OCH
    raise ValueError(f"input monitor bus must be 'main' or 'phones', got {bus!r}")


def validate_input_monitor_index(gain_ich: int) -> None:
    if gain_ich < 0 or gain_ich > _ANALOG_INPUT_MAX_INDEX:
        raise ValueError(
            f"input monitor input index must be 0–{_ANALOG_INPUT_MAX_INDEX}, got {gain_ich}"
        )


def _analog_left_ich(gain_ich: int) -> int:
    return gain_ich & 0xFE


def _analog_pair_linked(props: dict[str, dict[int, Any]], gain_ich: int) -> bool:
    mix_stereo = props.get("mix_stereo", {})
    return bool(mix_stereo.get(_analog_left_ich(gain_ich), 0))


def _crosspoint_at_monitor_preset(
    props: dict[str, dict[int, Any]],
    gain_ich: int,
    gain_och: int,
    *,
    check_pan: bool,
) -> bool:
    flat = mix_fader_index(gain_ich, gain_och)
    mix_faders = props.get("mix_fader", {})
    mix_mutes = props.get("mix_mute", {})
    mix_pans = props.get("mix_pan", {})

    fader = mix_faders.get(flat)
    if fader is None or fader <= 0:
        return False
    if mix_mutes.get(flat, 0) != 0:
        return False

    rounded_fader = round(100 * float(fader)) / 100
    if rounded_fader != _FADER_ON_GAIN:
        return False

    if check_pan:
        pan = mix_pans.get(flat, PAN_CENTER)
        if pan is None or not math.isclose(float(pan), PAN_CENTER, abs_tol=1e-4):
            return False
    return True


def _pair_button_state(
    props: dict[str, dict[int, Any]],
    left_ich: int,
    gain_och: int,
) -> InputMonitorState:
    """Aggregate monitor state for a stereo-linked analog pair."""
    right_ich = left_ich + 1
    left_flat = mix_fader_index(left_ich, gain_och)
    right_flat = mix_fader_index(right_ich, gain_och)
    mix_faders = props.get("mix_fader", {})

    left_fader = mix_faders.get(left_flat)
    right_fader = mix_faders.get(right_flat)
    left_off = left_fader is None or left_fader <= 0
    right_off = right_fader is None or right_fader <= 0

    if left_off and right_off:
        return "off"

    if (
        not left_off
        and not right_off
        and _crosspoint_at_monitor_preset(props, left_ich, gain_och, check_pan=False)
        and _crosspoint_at_monitor_preset(props, right_ich, gain_och, check_pan=False)
    ):
        return "on"
    return "edited"


def input_monitor_button_state(
    props: dict[str, dict[int, Any]],
    gain_ich: int,
    gain_och: int,
) -> InputMonitorState:
    """Return monitor button state for one analog input on one monitor bus.

    When the input pair is stereo-linked, both members report the same
    aggregate state: off when both crosspoints are off, on when both are at
    the monitor preset, and edited otherwise.
    """
    validate_input_monitor_index(gain_ich)
    if _analog_pair_linked(props, gain_ich):
        return _pair_button_state(props, _analog_left_ich(gain_ich), gain_och)

    flat = mix_fader_index(gain_ich, gain_och)
    fader = props.get("mix_fader", {}).get(flat)
    if fader is None or fader <= 0:
        return "off"
    if _crosspoint_at_monitor_preset(props, gain_ich, gain_och, check_pan=True):
        return "on"
    return "edited"


def set_input_monitor(
    device: Any,
    gain_ich: int,
    gain_och: int,
    *,
    enabled: bool,
) -> None:
    """Apply CueMix enableInputMonitorState for one analog input on one monitor bus.

    When the input pair is stereo-linked, either member toggles both crosspoints
    atomically and the stereo link is preserved.
    """
    validate_input_monitor_index(gain_ich)
    bus = device.mix[Buses(gain_och)]
    left_ich = _analog_left_ich(gain_ich)
    linked = bool(device.state.props.get("mix_stereo", {}).get(left_ich, 0))

    if linked:
        left_fader = bus.channel[left_ich].fader
        right_fader = bus.channel[left_ich + 1].fader
        if not enabled:
            left_fader._write_wire_gain(0.0, mirror_stereo=True)
            return

        for fader in (left_fader, right_fader):
            fader.set_muted(False)
            fader.set_soloed(False)
        left_fader._write_wire_gain(_FADER_ON_GAIN, mirror_stereo=True)
        return

    fader = bus.channel[gain_ich].fader
    if not enabled:
        fader._write_wire_gain(0.0, mirror_stereo=False)
        return

    fader.set_pan(PAN_CENTER)
    fader.set_muted(False)
    fader.set_soloed(False)
    fader._write_wire_gain(_FADER_ON_GAIN, mirror_stereo=False)


_INPUT_MONITOR_ON = frozenset({"on", "true", "1", "enable", "enabled"})
_INPUT_MONITOR_OFF = frozenset({"off", "false", "0", "disable", "disabled"})
DEFAULT_INPUT_MONITOR_VALUE = "toggle"


def resolve_input_monitor_enabled(
    value: str | None,
    *,
    current: InputMonitorState,
) -> bool:
    """Map CLI/card token to enabled flag; default toggle matches card click."""
    if value is None:
        normalized = DEFAULT_INPUT_MONITOR_VALUE
    else:
        normalized = value.strip().lower()
    if normalized == "toggle":
        return current == "off"
    if normalized in _INPUT_MONITOR_ON:
        return True
    if normalized in _INPUT_MONITOR_OFF:
        return False
    raise ValueError(
        f"input monitor value must be on/off/toggle, got {value!r}"
    )
