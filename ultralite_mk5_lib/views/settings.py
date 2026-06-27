"""Device settings (sample rate, optical modes)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultralite_mk5_lib.protocol import (
    OPTICAL_INPUT_MODE_INDEX,
    OPTICAL_OUTPUT_MODE_INDEX,
    VALID_SAMPLE_RATES,
    make_optical_mode_frame,
    make_sample_rate_frame,
    optical_mode_from_props,
    parse_optical_mode,
)
from ultralite_mk5_lib.views.transport import send_binary, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5


class SettingsView:
    """Global device settings."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    @property
    def sample_rate(self) -> int | None:
        return self._device.state.props.get("sample_rate", {}).get(0)

    @sample_rate.setter
    def sample_rate(self, rate: int) -> None:
        if rate not in VALID_SAMPLE_RATES:
            raise ValueError(
                f"rate must be one of {VALID_SAMPLE_RATES}, got {rate}"
            )
        frame = make_sample_rate_frame(rate)
        send_binary(self._device, frame)
        send_prop_local(self._device, "sample_rate", 0, rate)

    @property
    def optical_input_mode(self) -> str | None:
        return self._device.state.optical_input_mode

    @optical_input_mode.setter
    def optical_input_mode(self, mode: str) -> None:
        wire = parse_optical_mode(mode)
        send_binary(
            self._device,
            make_optical_mode_frame(OPTICAL_INPUT_MODE_INDEX, wire),
        )
        send_prop_local(self._device, "optical_mode", OPTICAL_INPUT_MODE_INDEX, wire)

    @property
    def optical_output_mode(self) -> str | None:
        return self._device.state.optical_output_mode

    @optical_output_mode.setter
    def optical_output_mode(self, mode: str) -> None:
        wire = parse_optical_mode(mode)
        send_binary(
            self._device,
            make_optical_mode_frame(OPTICAL_OUTPUT_MODE_INDEX, wire),
        )
        send_prop_local(self._device, "optical_mode", OPTICAL_OUTPUT_MODE_INDEX, wire)
