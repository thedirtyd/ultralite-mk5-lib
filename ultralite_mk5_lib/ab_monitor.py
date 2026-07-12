"""CueMix Outputs tab A/B monitoring (kABEnable / kAEnable / kBEnable)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from ultralite_mk5_lib.protocol import (
    make_a_enable_frame,
    make_ab_enable_frame,
    make_b_enable_frame,
)
from ultralite_mk5_lib.views.transport import send_binary, send_prop_local

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

ABMonitorPath = Literal["a", "b", "both", "none"]

AB_MONITOR_INDEX = 0

_TOGGLE_ON = frozenset({"on", "true", "1"})
_TOGGLE_OFF = frozenset({"off", "false", "0"})
DEFAULT_AB_MONITOR_VALUE = "on"


@dataclass(frozen=True, slots=True)
class ABMonitorWrite:
    """Resolved A/B monitor write (one or more wire frames)."""

    enabled: bool | None
    path: ABMonitorPath | None
    frames: bytes
    prop_updates: tuple[tuple[str, int, int], ...]


def _prop_byte(props: dict[str, dict[int, Any]], key: str) -> int | None:
    raw = props.get(key, {}).get(AB_MONITOR_INDEX)
    if raw is None:
        return None
    return int(raw)


def ab_monitor_enabled(props: dict[str, dict[int, Any]]) -> bool | None:
    """Read kABEnable master switch."""
    raw = _prop_byte(props, "ab_enable")
    if raw is None:
        return None
    return bool(raw)


def ab_monitor_path(props: dict[str, dict[int, Any]]) -> ABMonitorPath | None:
    """Derive active path from kAEnable / kBEnable (iosetup.js whichChanged)."""
    a_raw = _prop_byte(props, "a_enable")
    b_raw = _prop_byte(props, "b_enable")
    if a_raw is None and b_raw is None:
        return None
    a_state = bool(a_raw)
    b_state = bool(b_raw)
    if a_state and b_state:
        return "both"
    if a_state:
        return "a"
    if b_state:
        return "b"
    return "none"


def build_ab_monitor_state(props: dict[str, dict[int, Any]]) -> dict[str, Any]:
    """JSON-friendly A/B monitor state."""
    return {
        "enabled": ab_monitor_enabled(props),
        "path": ab_monitor_path(props),
    }


def parse_ab_monitor_enabled(token: str) -> bool:
    """Parse on/true/1 or off/false/0."""
    normalized = token.strip().lower()
    if normalized in _TOGGLE_ON:
        return True
    if normalized in _TOGGLE_OFF:
        return False
    raise ValueError(
        f"A/B monitor value must be on/true/1 or off/false/0, got {token!r}"
    )


def parse_ab_monitor_path(token: str) -> Literal["a", "b", "both"]:
    """Parse a/b/both path selector."""
    normalized = token.strip().lower()
    if normalized in ("a", "b", "both"):
        return normalized
    raise ValueError(f"A/B path must be a, b, or both, got {token!r}")


def _wire_values_for_enable(enabled: bool) -> tuple[int, int, int]:
    """CueMix AB ON / AB OFF button semantics."""
    if enabled:
        return 1, 1, 0
    return 0, 0, 0


def _wire_values_for_path(path: Literal["a", "b", "both"]) -> tuple[int, int, int]:
    """CueMix A / B / BOTH button semantics."""
    if path == "a":
        return 1, 1, 0
    if path == "b":
        return 1, 0, 1
    return 1, 1, 1


def build_ab_monitor_write(
    *,
    enabled: bool | None = None,
    path: Literal["a", "b", "both"] | None = None,
) -> ABMonitorWrite:
    """Build outbound frames and local prop updates for one A/B monitor change."""
    if enabled is None and path is None:
        raise ValueError("enabled or path is required")

    if enabled is not None and path is not None:
        raise ValueError("set enabled or path, not both in one write")

    if enabled is not None:
        ab_val, a_val, b_val = _wire_values_for_enable(enabled)
        resolved_path: ABMonitorPath | None = "a" if enabled else "none"
    else:
        assert path is not None
        ab_val, a_val, b_val = _wire_values_for_path(path)
        resolved_path = path

    frames = (
        make_ab_enable_frame(ab_val)
        + make_a_enable_frame(a_val)
        + make_b_enable_frame(b_val)
    )
    prop_updates = (
        ("ab_enable", AB_MONITOR_INDEX, ab_val),
        ("a_enable", AB_MONITOR_INDEX, a_val),
        ("b_enable", AB_MONITOR_INDEX, b_val),
    )
    return ABMonitorWrite(
        enabled=enabled,
        path=resolved_path,
        frames=frames,
        prop_updates=prop_updates,
    )


def apply_ab_monitor_write(device: UltraLiteMk5, write: ABMonitorWrite) -> None:
    """Send frames to device and mirror into local state."""
    send_binary(device, write.frames)
    for prop_key, index, value in write.prop_updates:
        send_prop_local(device, prop_key, index, value)


def set_ab_monitor_enabled(device: UltraLiteMk5, enabled: bool) -> ABMonitorWrite:
    """Enable or disable A/B monitoring (CueMix AB ON button)."""
    write = build_ab_monitor_write(enabled=enabled)
    apply_ab_monitor_write(device, write)
    return write


def set_ab_monitor_path(
    device: UltraLiteMk5,
    path: Literal["a", "b", "both"],
) -> ABMonitorWrite:
    """Select A, B, or both monitor paths."""
    write = build_ab_monitor_write(path=path)
    apply_ab_monitor_write(device, write)
    return write


def format_ab_monitor_summary(write: ABMonitorWrite) -> str:
    if write.enabled is not None:
        state = "on" if write.enabled else "off"
        return f"Set A/B monitor {state}"
    assert write.path is not None
    return f"Set A/B path to {write.path}"


def format_ab_path_summary(path: ABMonitorPath | None) -> str:
    if path is None:
        return "n/a"
    return path
