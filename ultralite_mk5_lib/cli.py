#!/usr/bin/env python3
"""Command-line interface for ultralite_mk5_lib."""

from __future__ import annotations

import argparse
import sys

from ultralite_mk5_lib import UltraLiteMk5
from ultralite_mk5_lib.config import (
    apply_connection_config,
    default_timeout,
    load_connection_config,
)
from ultralite_mk5_lib.exceptions import UltraLiteMk5Error
from ultralite_mk5_lib.levels import fix_set_level_argv
from ultralite_mk5_lib.interactive import (
    InteractiveSession,
    _add_monitor_meters_args,
    _add_set_optical_mode_args,
    _add_solo_output_bus_args,
    _add_set_channel_mode_args,
    _add_set_level_args,
    _add_set_mute_args,
    _add_set_sample_rate_args,
    run_interactive_loop,
    run_list_entities,
    run_monitor_meters_cmd,
    run_set_channel_mode,
    run_set_level,
    run_set_mute,
    run_set_optical_input_mode,
    run_set_optical_output_mode,
    run_set_sample_rate,
    run_solo_output_bus,
)
from ultralite_mk5_lib.protocol import LOCALHOSTS


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("connection")
    group.add_argument(
        "--host",
        help="Device host (default: host from config.yaml)",
    )
    group.add_argument(
        "--port",
        type=int,
        default=None,
        help="WebSocket port (default: 1281 for localhost, 1280 for device IP)",
    )
    group.add_argument(
        "--serial",
        help="Device serial for local proxy (default: serial from config.yaml)",
    )
    group.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Connection/handshake timeout in seconds (default: 3, or timeout from config.yaml)",
    )


def _require_connection(args: argparse.Namespace) -> None:
    if not args.host:
        raise ValueError(
            "--host is required (set host in config.yaml or pass --host)"
        )
    if args.host.lower() in LOCALHOSTS and not args.serial:
        raise ValueError(
            "serial is required for the local CueMix proxy (host 127.0.0.1); "
            "set serial in config.yaml or pass --serial"
        )


def _device_from_args(args: argparse.Namespace) -> UltraLiteMk5:
    _require_connection(args)
    return UltraLiteMk5(
        args.host,
        port=args.port,
        serial=args.serial,
        timeout=args.timeout,
    )


def _cmd_connect(args: argparse.Namespace) -> int:
    _require_connection(args)
    session = InteractiveSession()
    try:
        session.open(
            args.host,
            port=args.port,
            serial=args.serial,
            timeout=args.timeout,
        )
        return run_interactive_loop(session)
    except UltraLiteMk5Error:
        session.close()
        raise


def _cmd_set_sample_rate(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_sample_rate(device, args.rate)
        print(f" on {device.url}", flush=True)
    return 0


def _cmd_set_optical_input_mode(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_optical_input_mode(device, args.mode)
        print(f" on {device.url}")
    return 0


def _cmd_set_optical_output_mode(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_optical_output_mode(device, args.mode)
        print(f" on {device.url}")
    return 0


def _cmd_monitor_meters(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_monitor_meters_cmd(device, args.rate)
    return 0


def _cmd_set_mute(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_mute(device, args.key, args.value)
        print(f" on {device.url}")
    return 0


def _cmd_list_entities(_args: argparse.Namespace) -> int:
    run_list_entities()
    return 0


def _cmd_set_level(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_level(device, args.key, args.level)
        print(f" on {device.url}")
    return 0


def _cmd_set_channel_mode(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_set_channel_mode(device, args.key, args.mode)
        print(f" on {device.url}")
    return 0


def _cmd_solo_output_bus(args: argparse.Namespace) -> int:
    with _device_from_args(args) as device:
        run_solo_output_bus(device, args.key)
        print(f" on {device.url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ultralite-mk5",
        description="Control MOTU UltraLite mk5 / Gen5 devices over WebSocket.",
    )
    _add_connection_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect = subparsers.add_parser(
        "connect",
        help="Open a connection and enter interactive command mode",
    )
    connect.set_defaults(func=_cmd_connect)

    set_rate = subparsers.add_parser(
        "set-sample-rate",
        help="Set the device sample rate",
    )
    _add_set_sample_rate_args(set_rate)
    set_rate.set_defaults(func=_cmd_set_sample_rate)

    set_optical_input = subparsers.add_parser(
        "set-optical-input-mode",
        help="Set optical input mode (ADAT or TOSlink)",
    )
    _add_set_optical_mode_args(set_optical_input)
    set_optical_input.set_defaults(func=_cmd_set_optical_input_mode)

    set_optical_output = subparsers.add_parser(
        "set-optical-output-mode",
        help="Set optical output mode (ADAT or TOSlink)",
    )
    _add_set_optical_mode_args(set_optical_output)
    set_optical_output.set_defaults(func=_cmd_set_optical_output_mode)

    set_level = subparsers.add_parser(
        "set-level",
        help="Set fader, input gain, or trim level by entity key",
    )
    _add_set_level_args(set_level)
    set_level.set_defaults(func=_cmd_set_level)

    set_channel_mode = subparsers.add_parser(
        "set-channel-mode",
        help="Link or unlink an input pair as stereo/mono",
    )
    _add_set_channel_mode_args(set_channel_mode)
    set_channel_mode.set_defaults(func=_cmd_set_channel_mode)

    set_mute = subparsers.add_parser(
        "set-mute",
        help="Set mute by entity key",
    )
    _add_set_mute_args(set_mute)
    set_mute.set_defaults(func=_cmd_set_mute)

    list_entities = subparsers.add_parser(
        "list-entities",
        help="Print all entity keys, one per line",
    )
    list_entities.set_defaults(func=_cmd_list_entities)

    ls = subparsers.add_parser(
        "ls",
        help="Alias for list-entities",
    )
    ls.set_defaults(func=_cmd_list_entities)

    monitor_meters = subparsers.add_parser(
        "monitor-meters",
        help="Live active meter levels (Ctrl+C to stop)",
    )
    _add_monitor_meters_args(monitor_meters)
    monitor_meters.set_defaults(func=_cmd_monitor_meters)

    solo_bus = subparsers.add_parser(
        "solo-output-bus",
        help="Solo one output bus (unmute it, mute all others; reverb unchanged)",
    )
    _add_solo_output_bus_args(solo_bus)
    solo_bus.set_defaults(func=_cmd_solo_output_bus)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = fix_set_level_argv(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_connection_config(args, load_connection_config())
    if args.timeout is None:
        args.timeout = default_timeout()
    try:
        return args.func(args)
    except (UltraLiteMk5Error, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
