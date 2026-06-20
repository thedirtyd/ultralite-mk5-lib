"""Stable entity constant names (ENTITYTYPE_NAME) for meters, faders, and trims."""

from __future__ import annotations

import re

_KEY_PART_RE = re.compile(r"[^A-Za-z0-9]+")
_DIGIT_RE = re.compile(r"\d+")


def _pad_single_digit_numbers(label: str) -> str:
    """Zero-pad standalone single-digit channel numbers (1 -> 01) before slugging."""

    def repl(match: re.Match[str]) -> str:
        digits = match.group(0)
        if len(digits) == 1:
            return f"0{digits}"
        return digits

    return _DIGIT_RE.sub(repl, label)


def normalize_key_part(label: str) -> str:
    """Uppercase slug with no interior underscores (spaces, /, - removed)."""
    padded = _pad_single_digit_numbers(label)
    return _KEY_PART_RE.sub("", padded).upper()


_METER_CATEGORY_MAP = {
    "INPUTS": "INPUT",
    "MIX": "MIX",
    "OUTPUTS": "OUTPUT",
}


def meter_entity_key(display_name: str) -> str:
    """CueMix meter label -> METER_{CATEGORY}_{NAME}."""
    category, _, name = display_name.partition(" - ")
    cat = _METER_CATEGORY_MAP.get(normalize_key_part(category), normalize_key_part(category))
    return f"METER_{cat}_{normalize_key_part(name)}"


def input_gain_entity_key(channel_name: str) -> str:
    return f"INPUTGAIN_{normalize_key_part(channel_name)}"


def output_trim_entity_key(channel_name: str) -> str:
    return f"OUTPUTTRIM_{normalize_key_part(channel_name)}"


def volume_entity_key(monitor_name: str) -> str:
    return f"VOLUME_{normalize_key_part(monitor_name)}"


def mix_bus_entity_key_part(bus_name: str) -> str:
    return normalize_key_part(bus_name)


def mix_channel_entity_key_part(label: str) -> str:
    if label == "Out":
        return "OUT"
    return normalize_key_part(label)


def mix_bus_fader_entity_key(bus_name: str, channel_label: str) -> str:
    bus_part = mix_bus_entity_key_part(bus_name)
    ch_part = mix_channel_entity_key_part(channel_label)
    return f"MIXBUSFADER_{bus_part}_{ch_part}"
