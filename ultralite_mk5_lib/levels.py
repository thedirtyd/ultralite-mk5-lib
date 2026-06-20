"""Encode CLI level tokens to wire values per entity kind."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ultralite_mk5_lib.entities import EntityKind, EntityRef, resolve_entity
from ultralite_mk5_lib.inputs import INPUT_GAIN_CHANNELS
from ultralite_mk5_lib.mix_buses import (
    FADER_GAIN_MAX,
    FADER_GAIN_MIN,
    db_to_linear_gain,
    mix_fader_gain_to_db,
)
from ultralite_mk5_lib.outputs import TRIM_MAX_DB, TRIM_MIN_DB, trim_byte_to_db
from ultralite_mk5_lib.protocol import (
    make_bus_fader_frame,
    make_input_gain_frame,
    make_main_trim_frame,
    make_mix_fader_frame,
    make_output_trim_frame,
)

SETTABLE_LEVEL_KINDS: frozenset[EntityKind] = frozenset(
    {"mix_fader", "bus_fader", "input_gain", "main_trim", "output_trim"}
)

LevelMode = Literal["gain", "db"]


def parse_level_token(token: str) -> tuple[LevelMode, float]:
    """
    Parse a set-level value token.

    - Suffix ``db`` (e.g. ``-6db``, ``-infdb``) → dB
    - ``-inf`` / ``-infinity`` alone → −∞ dB
    - Plain number (e.g. ``0``, ``0.75``) → linear gain
    """
    raw = token.strip()
    if not raw:
        raise ValueError("level value is required")

    lower = raw.lower()
    if lower in ("-inf", "-infinity"):
        return "db", float("-inf")

    if lower.endswith("db"):
        num_part = raw[:-2].strip()
        if not num_part:
            raise ValueError(f"invalid level token {token!r}")
        num_lower = num_part.lower()
        if num_lower in ("-inf", "-infinity", "inf", "infinity"):
            return "db", float("-inf")
        try:
            return "db", float(num_part)
        except ValueError as exc:
            raise ValueError(f"invalid dB value in {token!r}") from exc

    try:
        return "gain", float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid level token {token!r}") from exc


def level_token_to_gain_db(token: str) -> tuple[float | None, float | None]:
    """Convert a CLI level token to mutually exclusive gain/db kwargs."""
    mode, value = parse_level_token(token)
    if mode == "gain":
        return value, None
    return None, value


def fix_set_level_argv(argv: list[str]) -> list[str]:
    """
    Insert ``--`` before a negative level token so argparse keeps it positional.

    Handles one-shot CLI such as:
    ``--host H --serial S set-level KEY -6db``
    """
    try:
        cmd_idx = argv.index("set-level")
    except ValueError:
        return argv

    positional: list[tuple[int, str]] = []
    i = cmd_idx + 1
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            break
        if tok in ("--host", "--serial", "--timeout", "--port"):
            i += 2
            continue
        if tok.startswith("--"):
            i += 1
            continue
        positional.append((i, tok))
        i += 1

    if len(positional) < 2:
        return argv

    level_idx, level_tok = positional[-1]
    if level_tok.startswith("-") and argv[level_idx - 1] != "--":
        return argv[:level_idx] + ["--"] + argv[level_idx:]
    return argv


@dataclass(frozen=True, slots=True)
class LevelCommand:
    """Resolved level write for one entity key."""

    key: str
    kind: EntityKind
    prop_key: str
    index: int
    wire_value: float | int
    frame: bytes


def _require_exclusive_gain_db(
    gain: float | None,
    db: float | None,
) -> tuple[str, float]:
    if gain is not None and db is not None:
        raise ValueError("specify only one of --gain or --db")
    if gain is not None:
        return "gain", gain
    if db is not None:
        return "db", db
    raise ValueError("one of --gain or --db is required")


def trim_db_to_byte(db: float) -> int:
    """Convert koTrim / kMainTrim dB to wire byte (iosetup.js)."""
    if math.isinf(db) and db < 0:
        return 100
    if db <= TRIM_MIN_DB:
        return 100
    if db >= TRIM_MAX_DB:
        return 0
    return int(round(-db))


def _input_gain_max_db(index: int) -> float:
    for channel in INPUT_GAIN_CHANNELS:
        if channel.index == index:
            return channel.max_db
    raise ValueError(f"unknown input gain index {index}")


def _encode_fader_level(gain: float | None, db: float | None) -> float:
    mode, value = _require_exclusive_gain_db(gain, db)
    if mode == "gain":
        linear = value
    elif math.isinf(value) and value < 0:
        linear = 0.0
    else:
        linear = db_to_linear_gain(value)

    if linear < FADER_GAIN_MIN or linear > FADER_GAIN_MAX:
        raise ValueError(
            f"fader gain must be between {FADER_GAIN_MIN} and {FADER_GAIN_MAX}, "
            f"got {linear}"
        )
    return linear


def _encode_input_gain_level(gain: float | None, db: float | None, max_db: float) -> int:
    mode, value = _require_exclusive_gain_db(gain, db)
    # Plain numbers and explicit dB both mean positive dB on the wire.
    level_db = value
    if math.isinf(level_db):
        raise ValueError("input gain cannot be -inf")
    if level_db < 0:
        raise ValueError(f"input gain must be >= 0 dB, got {level_db}")
    if level_db > max_db:
        raise ValueError(f"input gain must be <= {max_db} dB, got {level_db}")
    return int(round(level_db))


def _encode_trim_level(gain: float | None, db: float | None) -> int:
    mode, value = _require_exclusive_gain_db(gain, db)
    if mode == "db":
        level_db = value
    else:
        if value <= 0:
            level_db = float("-inf")
        elif value > 1:
            raise ValueError("trim --gain must be between 0 and 1")
        else:
            level_db = mix_fader_gain_to_db(value) or float("-inf")
    return trim_db_to_byte(level_db)


def encode_level_value(
    ref: EntityRef,
    *,
    gain: float | None = None,
    db: float | None = None,
) -> float | int:
    """Map --gain / --db to the wire value for one entity kind."""
    if ref.kind in ("mix_fader", "bus_fader"):
        return _encode_fader_level(gain, db)
    if ref.kind == "input_gain":
        return _encode_input_gain_level(gain, db, _input_gain_max_db(ref.index))
    if ref.kind in ("main_trim", "output_trim"):
        return _encode_trim_level(gain, db)
    raise ValueError(
        f"{ref.kind!r} entities cannot be set with set-level; "
        "use MIXBUSFADER_*, INPUTGAIN_*, VOLUME_*, or OUTPUTTRIM_* keys"
    )


def build_level_frame(prop_key: str, index: int, wire_value: float | int) -> bytes:
    if prop_key == "mix_fader":
        return make_mix_fader_frame(index, float(wire_value))
    if prop_key == "bus_fader":
        return make_bus_fader_frame(index, float(wire_value))
    if prop_key == "input_gain":
        return make_input_gain_frame(index, int(wire_value))
    if prop_key == "main_trim":
        return make_main_trim_frame(index, int(wire_value))
    if prop_key == "output_trim":
        return make_output_trim_frame(index, int(wire_value))
    raise ValueError(f"unsupported level property {prop_key!r}")


def prepare_level_command(
    key: str,
    level: str,
) -> LevelCommand:
    """Resolve entity key and level token to a wire frame."""
    gain, db = level_token_to_gain_db(level)
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind not in SETTABLE_LEVEL_KINDS:
        raise ValueError(
            f"{normalized!r} cannot be set with set-level; "
            "use MIXBUSFADER_*, INPUTGAIN_*, VOLUME_*, or OUTPUTTRIM_* keys"
        )

    from ultralite_mk5_lib.entities import property_index

    prop_key, index = property_index(normalized)
    wire_value = encode_level_value(ref, gain=gain, db=db)
    frame = build_level_frame(prop_key, index, wire_value)
    return LevelCommand(
        key=normalized,
        kind=ref.kind,
        prop_key=prop_key,
        index=index,
        wire_value=wire_value,
        frame=frame,
    )


def format_level_db(kind: EntityKind, wire_value: float | int) -> str:
    """Human-readable dB for CLI confirmation."""
    if kind in ("mix_fader", "bus_fader"):
        label_db = mix_fader_gain_to_db(float(wire_value))
    elif kind == "input_gain":
        label_db = float(wire_value)
    else:
        label_db = trim_byte_to_db(int(wire_value))

    if label_db is None:
        return "n/a"
    if math.isinf(label_db) and label_db < 0:
        return "-inf"
    return f"{label_db:.1f}"


def format_level_summary(command: LevelCommand) -> str:
    db_text = format_level_db(command.kind, command.wire_value)
    if command.kind in ("mix_fader", "bus_fader"):
        return (
            f"Set {command.key} gain={command.wire_value} ({db_text} dB)"
        )
    if command.kind == "input_gain":
        return f"Set {command.key} to {db_text} dB"
    return f"Set {command.key} to {db_text} dB (byte {command.wire_value})"
