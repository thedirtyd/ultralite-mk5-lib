"""EQ band handles (input and bus)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ultralite_mk5_lib.eq import (
    BUS_EQ_BANDS,
    EQBandSpec,
    INPUT_EQ_BANDS,
    clamp_freq,
    clamp_gain,
    clamp_q,
    curve_editable,
    format_mode,
    gain_applies,
    input_pair_linked,
    parse_eq_gain_token,
    parse_mode,
    prop_keys_for_block,
    q_applies,
    resolve_eq_band,
)
from ultralite_mk5_lib.protocol import (
    make_bus_eq_bypass_frame,
    make_bus_eq_freq_frame,
    make_bus_eq_gain_frame,
    make_bus_eq_mode_frame,
    make_bus_eq_q_frame,
    make_input_eq_bypass_frame,
    make_input_eq_freq_frame,
    make_input_eq_gain_frame,
    make_input_eq_mode_frame,
    make_input_eq_q_frame,
)
from ultralite_mk5_lib.views.transport import send_binary, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

EQParam = Literal["enable", "freq", "gain", "q", "curve"]


def _frame_builders(spec: EQBandSpec):
    if spec.block == "input":
        return {
            "mode": make_input_eq_mode_frame,
            "bypass": make_input_eq_bypass_frame,
            "freq": make_input_eq_freq_frame,
            "gain": make_input_eq_gain_frame,
            "q": make_input_eq_q_frame,
        }
    return {
        "mode": make_bus_eq_mode_frame,
        "bypass": make_bus_eq_bypass_frame,
        "freq": make_bus_eq_freq_frame,
        "gain": make_bus_eq_gain_frame,
        "q": make_bus_eq_q_frame,
    }


class EQBandHandle:
    """One EQ band (mode, enable, freq, gain, Q)."""

    def __init__(self, device: UltraLiteMk5, spec: EQBandSpec) -> None:
        self._device = device
        self._spec = spec

    @property
    def key(self) -> str:
        return self._spec.key

    @property
    def spec(self) -> EQBandSpec:
        return self._spec

    def _props(self) -> dict[str, dict]:
        return self._device.state.props

    def _prop_keys(self) -> dict[str, str]:
        return prop_keys_for_block(self._spec.block)

    def _idx(self) -> int:
        return self._spec.flat_index

    def _mode_raw(self) -> int | None:
        raw = self._props().get(self._prop_keys()["mode"], {}).get(self._idx())
        return int(raw) if raw is not None else None

    @property
    def enabled(self) -> bool | None:
        bypass = self._props().get(self._prop_keys()["bypass"], {}).get(self._idx())
        if bypass is None:
            return None
        return not bool(bypass)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.set_enabled(value)

    def set_enabled(self, value: bool) -> None:
        self._write_bypass(0 if value else 1)

    @property
    def freq_hz(self) -> int | None:
        raw = self._props().get(self._prop_keys()["freq"], {}).get(self._idx())
        return int(raw) if raw is not None else None

    @freq_hz.setter
    def freq_hz(self, value: int | float) -> None:
        self.set_freq_hz(value)

    def set_freq_hz(self, value: int | float) -> None:
        freq = clamp_freq(value)
        self._write("freq", freq, wire_value=freq)

    @property
    def gain_db(self) -> float | None:
        raw = self._props().get(self._prop_keys()["gain"], {}).get(self._idx())
        return float(raw) if raw is not None else None

    @gain_db.setter
    def gain_db(self, value: float) -> None:
        self.set_gain_db(value)

    def set_gain_db(self, value: float) -> None:
        if not gain_applies(self._mode_raw()):
            raise ValueError(
                f"Gain not applicable: {self._spec.key} curve is "
                f"{format_mode(self._mode_raw())}; no change made."
            )
        gain = clamp_gain(value)
        self._write("gain", gain, wire_value=gain)

    @property
    def q(self) -> float | None:
        raw = self._props().get(self._prop_keys()["q"], {}).get(self._idx())
        return float(raw) if raw is not None else None

    @q.setter
    def q(self, value: float) -> None:
        self.set_q(value)

    def set_q(self, value: float) -> None:
        if not q_applies(self._mode_raw()):
            raise ValueError(
                f"Q not applicable: {self._spec.key} curve is "
                f"{format_mode(self._mode_raw())}; no change made."
            )
        q_val = clamp_q(value)
        self._write("q", q_val, wire_value=q_val)

    @property
    def curve_type(self) -> str | None:
        mode = self._mode_raw()
        if mode is None:
            return None
        locked = self._spec.locked_mode
        return format_mode(locked if locked is not None else mode)

    @curve_type.setter
    def curve_type(self, value: str) -> None:
        self.set_curve_type(value)

    def set_curve_type(self, value: str) -> None:
        if not curve_editable(self._spec):
            locked = format_mode(self._spec.locked_mode)
            raise ValueError(
                f"Curve type is locked to {locked} on {self._spec.key}; no change made."
            )
        mode = int(parse_mode(value))
        if mode not in self._spec.allowed_modes:
            allowed = ", ".join(format_mode(m) for m in self._spec.allowed_modes)
            raise ValueError(
                f"Curve {format_mode(mode)} not allowed on {self._spec.key}; "
                f"allowed: {allowed}."
            )
        self._write("mode", mode, wire_value=mode)

    def set_param(self, param: EQParam, value: str) -> None:
        param_norm = param.strip().lower()
        if param_norm == "enable":
            self.set_enabled(_parse_bool(value))
        elif param_norm == "freq":
            self.set_freq_hz(float(value))
        elif param_norm == "gain":
            self.set_gain_db(parse_eq_gain_token(value))
        elif param_norm == "q":
            self.set_q(float(value))
        elif param_norm == "curve":
            self.set_curve_type(value)
        else:
            raise ValueError(
                f"unknown EQ param {param!r}; use enable, freq, gain, q, or curve"
            )

    def _write_bypass(self, bypass: int) -> None:
        self._write("bypass", bypass, wire_value=bypass)

    def _write(self, field: str, wire_arg: object, *, wire_value: object) -> None:
        builders = _frame_builders(self._spec)
        prop_keys = self._prop_keys()
        idx = self._idx()
        frame = builders[field](idx, wire_arg)  # type: ignore[operator]
        send_binary(self._device, frame)
        send_prop_local(self._device, prop_keys[field], idx, wire_value)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("1", "true", "on", "enable", "enabled", "yes"):
        return True
    if normalized in ("0", "false", "off", "disable", "disabled", "no"):
        return False
    raise ValueError(f"expected on/off boolean, got {value!r}")


class EQView:
    """Input and bus EQ bands."""

    def __init__(self, device: UltraLiteMk5) -> None:
        self._device = device

    def __getitem__(self, key: str) -> EQBandHandle:
        return EQBandHandle(self._device, resolve_eq_band(key))

    def by_key(self, key: str) -> EQBandHandle:
        return self[key]

    def input_bands(self):
        for spec in INPUT_EQ_BANDS:
            yield EQBandHandle(self._device, spec)

    def bus_bands(self):
        for spec in BUS_EQ_BANDS:
            yield EQBandHandle(self._device, spec)

    def input_pair_linked(self, spec: EQBandSpec) -> bool:
        return input_pair_linked(spec, self._device.state.props)
