"""Load optional connection defaults from config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.yaml")
_CONFIG_KEYS = frozenset({"host", "serial", "port", "timeout"})
_DEFAULT_TIMEOUT = 3.0


@dataclass(frozen=True)
class ConnectionConfig:
    host: str | None = None
    serial: str | None = None
    port: int | None = None
    timeout: float | None = None


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_connection_config(path: Path | None = None) -> ConnectionConfig:
    """Read connection defaults from a flat YAML file (missing file → empty config)."""
    path = path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return ConnectionConfig()

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, raw_value = stripped.partition(":")
        key = key.strip().lower()
        if key not in _CONFIG_KEYS:
            continue
        value = _parse_scalar(raw_value)
        if value:
            values[key] = value

    port: int | None = None
    if "port" in values:
        try:
            port = int(values["port"])
        except ValueError as exc:
            raise ValueError(f"invalid port in config.yaml: {values['port']!r}") from exc

    timeout: float | None = None
    if "timeout" in values:
        try:
            timeout = float(values["timeout"])
        except ValueError as exc:
            raise ValueError(
                f"invalid timeout in config.yaml: {values['timeout']!r}"
            ) from exc

    return ConnectionConfig(
        host=values.get("host"),
        serial=values.get("serial"),
        port=port,
        timeout=timeout,
    )


def apply_connection_config(args: object, config: ConnectionConfig) -> None:
    """Fill unset CLI connection args from config."""
    if getattr(args, "host", None) is None and config.host is not None:
        args.host = config.host  # type: ignore[attr-defined]
    if getattr(args, "serial", None) is None and config.serial is not None:
        args.serial = config.serial  # type: ignore[attr-defined]
    if getattr(args, "port", None) is None and config.port is not None:
        args.port = config.port  # type: ignore[attr-defined]
    if getattr(args, "timeout", None) is None and config.timeout is not None:
        args.timeout = config.timeout  # type: ignore[attr-defined]


def default_timeout() -> float:
    return _DEFAULT_TIMEOUT
