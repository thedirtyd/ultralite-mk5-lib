"""Input and bus EQ catalog, validation, and state-report builders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Literal

from ultralite_mk5_lib.entity_keys import bus_eq_entity_key, input_eq_entity_key
from ultralite_mk5_lib.inputs import INPUT_GAIN_CHANNELS
from ultralite_mk5_lib.mix_buses import _make_stereo_label

EQBlock = Literal["input", "output"]

INPUT_EQ_BANDS_COUNT = 4
BUS_EQ_BANDS_COUNT = 3

FREQ_MIN = 20
FREQ_MAX = 20000
GAIN_MIN = -20.0
GAIN_MAX = 20.0
Q_MIN = 0.45
Q_MAX = 10.0

# Pairable analog input eq indices (Mic 1/2, Line 3/4 … 7/8).
INPUT_EQ_STEREO_PAIR_MAX_INDEX = 7

BAND1_MODES = (0, 1, 3)  # peak, low shelf, high pass
BAND_MIDDLE_MODES = (0,)  # peak only
BAND_LAST_INPUT_MODES = (0, 2)  # peak, high shelf (4-band input)
BAND_LAST_OUTPUT_MODES = (0, 2)  # peak, high shelf (3-band output)


class EQMode(IntEnum):
    PEAK = 0
    LOW_SHELF = 1
    HIGH_SHELF = 2
    HIGH_PASS = 3


_MODE_TOKENS: dict[EQMode, str] = {
    EQMode.PEAK: "peak",
    EQMode.LOW_SHELF: "lowshelf",
    EQMode.HIGH_SHELF: "highshelf",
    EQMode.HIGH_PASS: "highpass",
}

_TOKEN_TO_MODE: dict[str, EQMode] = {v: k for k, v in _MODE_TOKENS.items()}


@dataclass(frozen=True, slots=True)
class EQBandSpec:
    """One EQ band entity (five wire properties share flat_index)."""

    key: str
    block: EQBlock
    channel_name: str
    channel_eq_index: int
    band: int
    num_bands: int
    flat_index: int
    allowed_modes: tuple[int, ...]
    display: str
    stereo_left_eq_index: int | None = None
    is_stereo_right: bool = False

    @property
    def locked_mode(self) -> int | None:
        if len(self.allowed_modes) == 1:
            return self.allowed_modes[0]
        return None


@dataclass(frozen=True, slots=True)
class BusEQChannel:
    """One mix output bus EQ block (3 bands)."""

    name: str
    eq_index: int


BUS_EQ_CHANNELS: tuple[BusEQChannel, ...] = (
    BusEQChannel("Main 1-2", 0),
    BusEQChannel("Line 3-4", 2),
    BusEQChannel("Line 5-6", 4),
    BusEQChannel("Line 7-8", 6),
    BusEQChannel("Line 9-10", 8),
    BusEQChannel("Phones", 10),
    BusEQChannel("Reverb", 11),
)

INPUT_EQ_PROP_KEYS = {
    "mode": "input_eq_mode",
    "bypass": "input_eq_bypass",
    "freq": "input_eq_freq",
    "gain": "input_eq_gain",
    "q": "input_eq_q",
}

BUS_EQ_PROP_KEYS = {
    "mode": "bus_eq_mode",
    "bypass": "bus_eq_bypass",
    "freq": "bus_eq_freq",
    "gain": "bus_eq_gain",
    "q": "bus_eq_q",
}


def _band_modes(block: EQBlock, band: int, num_bands: int) -> tuple[int, ...]:
    last_band = num_bands - 1
    if band == 0:
        return BAND1_MODES
    if band == last_band:
        return BAND_LAST_INPUT_MODES if block == "input" else BAND_LAST_OUTPUT_MODES
    return BAND_MIDDLE_MODES


def _flat_index(eq_index: int, band: int, num_bands: int) -> int:
    return eq_index * num_bands + band


def _input_stereo_metadata(eq_index: int) -> tuple[int | None, bool]:
    if eq_index > INPUT_EQ_STEREO_PAIR_MAX_INDEX:
        return None, False
    left = eq_index & 0xFE
    return left, eq_index % 2 == 1


def _build_input_eq_bands() -> tuple[EQBandSpec, ...]:
    bands: list[EQBandSpec] = []
    for ch in INPUT_GAIN_CHANNELS:
        left_idx, is_right = _input_stereo_metadata(ch.index)
        for band in range(1, INPUT_EQ_BANDS_COUNT + 1):
            band_idx = band - 1
            modes = _band_modes("input", band_idx, INPUT_EQ_BANDS_COUNT)
            flat = _flat_index(ch.index, band_idx, INPUT_EQ_BANDS_COUNT)
            key = input_eq_entity_key(ch.name, band)
            bands.append(
                EQBandSpec(
                    key=key,
                    block="input",
                    channel_name=ch.name,
                    channel_eq_index=ch.index,
                    band=band,
                    num_bands=INPUT_EQ_BANDS_COUNT,
                    flat_index=flat,
                    allowed_modes=modes,
                    display=f"{ch.name} B{band}",
                    stereo_left_eq_index=left_idx,
                    is_stereo_right=is_right,
                )
            )
    return tuple(bands)


def _build_bus_eq_bands() -> tuple[EQBandSpec, ...]:
    bands: list[EQBandSpec] = []
    for bus in BUS_EQ_CHANNELS:
        for band in range(1, BUS_EQ_BANDS_COUNT + 1):
            band_idx = band - 1
            modes = _band_modes("output", band_idx, BUS_EQ_BANDS_COUNT)
            flat = _flat_index(bus.eq_index, band_idx, BUS_EQ_BANDS_COUNT)
            key = bus_eq_entity_key(bus.name, band)
            bands.append(
                EQBandSpec(
                    key=key,
                    block="output",
                    channel_name=bus.name,
                    channel_eq_index=bus.eq_index,
                    band=band,
                    num_bands=BUS_EQ_BANDS_COUNT,
                    flat_index=flat,
                    allowed_modes=modes,
                    display=f"{bus.name} B{band}",
                )
            )
    return tuple(bands)


INPUT_EQ_BANDS: tuple[EQBandSpec, ...] = _build_input_eq_bands()
BUS_EQ_BANDS: tuple[EQBandSpec, ...] = _build_bus_eq_bands()
EQ_BAND_REGISTRY: dict[str, EQBandSpec] = {
    spec.key: spec for spec in (*INPUT_EQ_BANDS, *BUS_EQ_BANDS)
}
EQ_BAND_KEYS: tuple[str, ...] = tuple(sorted(EQ_BAND_REGISTRY))


def prop_keys_for_block(block: EQBlock) -> dict[str, str]:
    return INPUT_EQ_PROP_KEYS if block == "input" else BUS_EQ_PROP_KEYS


def resolve_eq_band(key: str) -> EQBandSpec:
    normalized = key.strip().upper()
    try:
        return EQ_BAND_REGISTRY[normalized]
    except KeyError as exc:
        raise ValueError(
            f"unknown EQ band key {key!r}; run list-entities to see INPUTEQ_* / BUSEQ_* keys"
        ) from exc


def format_mode(mode: int | None) -> str | None:
    if mode is None:
        return None
    try:
        return _MODE_TOKENS[EQMode(mode)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"unknown EQ mode wire value {mode}") from exc


def parse_mode(value: str) -> EQMode:
    normalized = value.strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "peak": EQMode.PEAK,
        "lowshelf": EQMode.LOW_SHELF,
        "low": EQMode.LOW_SHELF,
        "highshelf": EQMode.HIGH_SHELF,
        "high": EQMode.HIGH_SHELF,
        "highpass": EQMode.HIGH_PASS,
        "hp": EQMode.HIGH_PASS,
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in _TOKEN_TO_MODE:
        return _TOKEN_TO_MODE[normalized]
    raise ValueError(
        "curve must be one of peak, lowshelf, highshelf, highpass "
        f"(got {value!r})"
    )


def clamp_freq(value: float | int) -> int:
    return int(max(FREQ_MIN, min(FREQ_MAX, round(float(value)))))


def clamp_gain(value: float) -> float:
    return max(GAIN_MIN, min(GAIN_MAX, float(value)))


def parse_eq_gain_token(token: str) -> float:
    """Parse set-eq gain: plain dB (-6) or with suffix (-6db)."""
    raw = token.strip()
    if not raw:
        raise ValueError("gain value is required")
    lower = raw.lower()
    if lower.endswith("db"):
        num_part = raw[:-2].strip()
        if not num_part:
            raise ValueError(f"invalid gain token {token!r}")
        try:
            return float(num_part)
        except ValueError as exc:
            raise ValueError(f"invalid dB value in {token!r}") from exc
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid gain token {token!r}") from exc


def clamp_q(value: float) -> float:
    return max(Q_MIN, min(Q_MAX, float(value)))


def gain_applies(mode: int | None) -> bool:
    return mode != EQMode.HIGH_PASS


def q_applies(mode: int | None) -> bool:
    return mode == EQMode.PEAK


def curve_editable(spec: EQBandSpec) -> bool:
    return spec.locked_mode is None


def input_pair_linked(spec: EQBandSpec, props: dict[str, dict[int, Any]]) -> bool:
    if spec.block != "input" or spec.stereo_left_eq_index is None:
        return False
    mix_stereo = props.get("mix_stereo", {})
    return bool(mix_stereo.get(spec.stereo_left_eq_index, 0))


def input_eq_hidden_in_report(spec: EQBandSpec, props: dict[str, dict[int, Any]]) -> bool:
    return spec.is_stereo_right and input_pair_linked(spec, props)


def stereo_paired_input_eq_warning(spec: EQBandSpec, props: dict[str, dict[int, Any]]) -> str | None:
    if not input_eq_hidden_in_report(spec, props):
        return None
    return (
        "input pair is in stereo mode; R channel EQ changes are stored "
        "but have no effect on audio until unlinked"
    )


def _prop_value(props: dict[str, dict[int, Any]], prop_key: str, index: int) -> Any | None:
    return props.get(prop_key, {}).get(index)


def _band_state(spec: EQBandSpec, props: dict[str, dict[int, Any]]) -> dict[str, Any]:
    keys = prop_keys_for_block(spec.block)
    idx = spec.flat_index
    bypass = _prop_value(props, keys["bypass"], idx)
    mode_raw = _prop_value(props, keys["mode"], idx)
    mode = int(mode_raw) if mode_raw is not None else None
    freq = _prop_value(props, keys["freq"], idx)
    gain = _prop_value(props, keys["gain"], idx)
    q = _prop_value(props, keys["q"], idx)
    locked = spec.locked_mode
    curve = format_mode(locked if locked is not None else mode)
    return {
        "key": spec.key,
        "name": spec.display,
        "channel": spec.channel_name,
        "band": spec.band,
        "enabled": (not bool(bypass)) if bypass is not None else None,
        "curve": curve,
        "curve_locked": locked is not None,
        "freq_hz": int(freq) if freq is not None else None,
        "gain_db": float(gain) if gain is not None else None,
        "gain_applies": gain_applies(mode),
        "q": float(q) if q is not None else None,
        "q_applies": q_applies(mode),
    }


def _input_channel_display_name(spec: EQBandSpec, props: dict[str, dict[int, Any]]) -> str:
    if spec.stereo_left_eq_index is None:
        return spec.channel_name
    if not input_pair_linked(spec, props):
        return spec.channel_name
    if spec.is_stereo_right:
        return spec.channel_name
    right_name = next(
        (
            ch.name
            for ch in INPUT_GAIN_CHANNELS
            if ch.index == spec.channel_eq_index + 1
        ),
        None,
    )
    if right_name is None:
        return spec.channel_name
    return _make_stereo_label(spec.channel_name, right_name)


def build_input_eq_state(props: dict[str, dict[int, Any]]) -> list[dict[str, Any]]:
    """Per-band input EQ rows; omits R channels while their pair is stereo-linked."""
    rows: list[dict[str, Any]] = []
    for spec in INPUT_EQ_BANDS:
        if input_eq_hidden_in_report(spec, props):
            continue
        row = _band_state(spec, props)
        row["channel"] = _input_channel_display_name(spec, props)
        rows.append(row)
    return rows


def build_bus_eq_state(props: dict[str, dict[int, Any]]) -> list[dict[str, Any]]:
    return [_band_state(spec, props) for spec in BUS_EQ_BANDS]


for _spec in EQ_BAND_REGISTRY.values():
    globals()[_spec.key] = _spec.flat_index
