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


def input_monitor_button_state(
    props: dict[str, dict[int, Any]],
    gain_ich: int,
    gain_och: int,
) -> InputMonitorState:
    """Mirror CueMix home.js getChInputMonitorState (excluding talkback disabled)."""
    validate_input_monitor_index(gain_ich)
    flat = mix_fader_index(gain_ich, gain_och)

    mix_faders = props.get("mix_fader", {})
    mix_mutes = props.get("mix_mute", {})
    mix_pans = props.get("mix_pan", {})
    mix_stereo = props.get("mix_stereo", {})

    fader = mix_faders.get(flat)
    if fader is None or fader <= 0:
        return "off"

    stereo = bool(mix_stereo.get(gain_ich, 0))
    mute = mix_mutes.get(flat, 0)
    pan = mix_pans.get(flat, PAN_CENTER)

    rounded_fader = round(100 * float(fader)) / 100
    if (
        not stereo
        and mute == 0
        and pan is not None
        and math.isclose(float(pan), PAN_CENTER, abs_tol=1e-4)
        and rounded_fader == _FADER_ON_GAIN
    ):
        return "on"
    return "edited"


def set_input_monitor(
    device: Any,
    gain_ich: int,
    gain_och: int,
    *,
    enabled: bool,
) -> None:
    """Apply CueMix enableInputMonitorState for one analog input on one monitor bus."""
    validate_input_monitor_index(gain_ich)
    fader = device.mix[Buses(gain_och)].channel[gain_ich].fader

    if not enabled:
        fader._write_wire_gain(0.0, mirror_stereo=False)
        return

    device.mix.stereo[gain_ich & 0xFE].set_linked(False)
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
