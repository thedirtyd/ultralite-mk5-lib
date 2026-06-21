"""Interactive console session for ultralite_mk5_lib."""

from __future__ import annotations

import argparse
import shlex
import sys
import textwrap

from ultralite_mk5_lib.client import UltraLiteMk5
from ultralite_mk5_lib.entities import ALL_ENTITY_KEYS, resolve_entity
from ultralite_mk5_lib.exceptions import NotConnectedError, UltraLiteMk5Error
from ultralite_mk5_lib.levels import format_level_summary
from ultralite_mk5_lib.mix_buses import STEREO_CAPABLE_MAX_GAIN_ICH
from ultralite_mk5_lib.mutes import DEFAULT_MUTE_VALUE, format_mute_summary
from ultralite_mk5_lib.protocol import (
    normalize_optical_mode,
    optical_mode_choices_text,
    parse_sample_rate,
    sample_rate_choices_text,
)
from ultralite_mk5_lib.state import DeviceState
from ultralite_mk5_lib.display import print_state_snapshot, run_monitor_meters
from ultralite_mk5_lib.report import state_report_to_json

PROMPT = "ultralite-mk5> "

INTERACTIVE_COMMANDS = (
    "set-sample-rate",
    "set-optical-input-mode",
    "set-optical-output-mode",
    "set-level",
    "set-channel-mode",
    "set-mute",
    "list-entities",
    "solo-output-bus",
    "get-state",
    "monitor-meters",
    "help",
    "exit",
)

COMMAND_ALIASES: dict[str, str] = {
    "ls": "list-entities",
}


def _resolve_command_alias(name: str) -> str:
    return COMMAND_ALIASES.get(name.lower(), name)


class InteractiveSession:
    """Holds an open device connection for interactive commands."""

    def __init__(self) -> None:
        self.device: UltraLiteMk5 | None = None
        self._waiting_for_device = False

    def open(
        self,
        host: str,
        *,
        port: int | None,
        serial: str | None,
        timeout: float,
    ) -> UltraLiteMk5:
        self.close()
        self._waiting_for_device = False

        def on_connection_lost() -> None:
            print("\nWaiting for device...", file=sys.stderr, flush=True)
            self._waiting_for_device = True

        def on_connection_restored() -> None:
            if self._waiting_for_device:
                print("Device reconnected.", file=sys.stderr, flush=True)
                print(PROMPT, end="", file=sys.stderr, flush=True)
                self._waiting_for_device = False

        self.device = UltraLiteMk5(
            host,
            port=port,
            serial=serial,
            timeout=timeout,
            connect=True,
            on_connection_lost=on_connection_lost,
            on_connection_restored=on_connection_restored,
        )
        return self.device

    def close(self) -> None:
        if self.device is not None:
            self.device.close()
            self.device = None

    def require_device(self) -> UltraLiteMk5:
        if self.device is None:
            raise NotConnectedError("Not connected")
        if not self.device.connected:
            self.device.wait_until_connected()
        return self.device

    @property
    def state(self) -> DeviceState:
        return self.require_device().state


def run_set_sample_rate(device: UltraLiteMk5, rate: int) -> None:
    device.set_sample_rate(rate)
    print(f"Set sample rate to {rate} Hz")


def run_set_optical_input_mode(device: UltraLiteMk5, mode: str) -> None:
    device.set_optical_input_mode(mode)
    print(f"Set optical input mode to {mode}")


def run_set_optical_output_mode(device: UltraLiteMk5, mode: str) -> None:
    device.set_optical_output_mode(mode)
    print(f"Set optical output mode to {mode}")


def run_set_mute(device: UltraLiteMk5, key: str, value: str | None = None) -> None:
    command = device.set_mute(key, value)
    print(format_mute_summary(command))


def run_solo_output_bus(device: UltraLiteMk5, key: str) -> None:
    device.solo_output_bus(key)
    print(f"{key} solo (all other buses muted)")


def run_list_entities() -> None:
    for key in ALL_ENTITY_KEYS:
        print(key)


def run_set_level(device: UltraLiteMk5, key: str, level: str) -> None:
    normalized = key.strip().upper()
    ref = resolve_entity(normalized)
    if ref.kind == "mix_fader" and ref.gain_ich is not None:
        ich = ref.gain_ich
        if ich % 2 == 1 and ich <= STEREO_CAPABLE_MAX_GAIN_ICH:
            mix_stereo = device.state.props.get("mix_stereo", {})
            if mix_stereo.get(ich & 0xFE, 0):
                print(
                    "Warning: channel pair is in stereo mode; "
                    "R channel level change will have no effect on audio.",
                    file=sys.stderr,
                )
    command = device.set_level(normalized, level)
    print(format_level_summary(command))


def run_set_channel_mode(device: UltraLiteMk5, key: str, mode: str) -> None:
    normalized = key.strip().upper()
    device.set_channel_stereo_mode(normalized, mode)
    print(f"Set {normalized} channel pair to {mode.strip().lower()}")


def run_get_state(device: UltraLiteMk5, *, json: bool = False) -> None:
    if not device.state.is_ready():
        print("Waiting for device state...", file=sys.stderr)
        device.state.wait_until_ready(device.timeout)
    snap = device.state.snapshot()
    if json:
        print(state_report_to_json(snap))
    else:
        print_state_snapshot(snap)


def run_monitor_meters_cmd(device: UltraLiteMk5, refresh_hz: float) -> None:
    run_monitor_meters(device, refresh_hz=refresh_hz)


def _add_set_sample_rate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rate",
        type=parse_sample_rate,
        required=True,
        help=f"Sample rate ({sample_rate_choices_text()})",
    )


def _add_set_optical_mode_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "mode",
        type=normalize_optical_mode,
        help=f"Optical mode ({optical_mode_choices_text()})",
    )


def _add_set_level_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "key",
        help="Entity key (MIXBUSFADER_*, INPUTGAIN_*, VOLUME_*, OUTPUTTRIM_*)",
    )
    parser.add_argument(
        "level",
        help="Level: plain gain (0.75), dB (-6db), or -inf / -infdb",
    )


def _add_set_channel_mode_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "key",
        help="MIXINPUT_* (preferred) or MIXBUSFADER_* crosspoint key for L or R of the pair",
    )
    parser.add_argument(
        "mode",
        choices=("stereo", "mono"),
        help="Link pair as stereo or split to mono",
    )


def _add_set_mute_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "key",
        help="Entity key (MIXBUSFADER_* crosspoint or *_OUT bus mute)",
    )
    parser.add_argument(
        "value",
        nargs="?",
        default=DEFAULT_MUTE_VALUE,
        help="mute/on/true/1 or unmute/off/false/0 (default: mute)",
    )


def _add_monitor_meters_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rate",
        type=float,
        default=12.0,
        help="Refresh rate in Hz (default: 12)",
    )


def _add_solo_output_bus_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "key",
        help="Output-bus mute entity key (MIXBUSFADER_*_OUT, not REVERB)",
    )


def _command_help_lines() -> dict[str, list[str]]:
    return {
        "set-sample-rate": [
            "set-sample-rate --rate RATE",
            f"  RATE: {sample_rate_choices_text()}",
            "  Examples: set-sample-rate --rate 96",
            "            set-sample-rate --rate 96000",
        ],
        "set-optical-input-mode": [
            "set-optical-input-mode MODE",
            f"  MODE: {optical_mode_choices_text()}",
            "  Examples: set-optical-input-mode adat",
            "            set-optical-input-mode toslink",
        ],
        "set-optical-output-mode": [
            "set-optical-output-mode MODE",
            f"  MODE: {optical_mode_choices_text()}",
            "  Examples: set-optical-output-mode adat",
            "            set-optical-output-mode toslink",
        ],
        "set-level": [
            "set-level KEY LEVEL",
            "  LEVEL: plain number = linear gain (e.g. 0, 0.75); suffix db = dB",
            "  Examples: set-level MIXBUSFADER_MAIN0102_LINEIN03 0.75",
            "            set-level MIXBUSFADER_MAIN0102_OUT -6db",
            "            set-level VOLUME_MAIN -inf",
            "            set-level INPUTGAIN_MICLINEIN01 12",
        ],
        "set-channel-mode": [
            "set-channel-mode KEY stereo|mono",
            "  KEY: MIXINPUT_* (preferred) or MIXBUSFADER_* crosspoint for L or R of pair",
            "  Stereo link applies globally across all mix buses.",
            "  Examples: set-channel-mode MIXINPUT_OPTICAL01 stereo",
            "            set-channel-mode MIXINPUT_LINEIN04 mono",
            "            set-channel-mode MIXINPUT_HOST0102 stereo",
            "            set-channel-mode MIXINPUT_HOST0304 mono",
            "            set-channel-mode MIXBUSFADER_MAIN0102_OPTICAL01 stereo",
        ],
        "list-entities": [
            "list-entities  (alias: ls)",
            "  Print all entity keys, one per line (no device connection).",
        ],
        "set-mute": [
            "set-mute KEY [VALUE]",
            "  VALUE: mute/on/true/1 or unmute/off/false/0 (default: mute)",
            "  Examples: set-mute MIXBUSFADER_MAIN0102_LINEIN03",
            "            set-mute MIXBUSFADER_MAIN0102_OUT unmute",
        ],
        "solo-output-bus": [
            "solo-output-bus KEY",
            "  KEY: MIXBUSFADER_*_OUT entity key (see list-entities)",
            "  Example: solo-output-bus MIXBUSFADER_MAIN0102_OUT",
            "  Reverb is not a valid target; its mute state is unchanged.",
        ],
        "get-state": [
            "get-state [--json]",
            "  Print device state as Rich tables (trims, faders, meters).",
            "  --json  Emit the state snapshot as JSON instead.",
        ],
        "monitor-meters": [
            "monitor-meters [--rate HZ]",
            "  Live-refresh active meter levels (default 12 Hz). Ctrl+C to stop.",
        ],
        "help": [
            "help [command]",
            "  Show this summary or help for one command.",
        ],
        "exit": [
            "exit",
            "  Disconnect and leave interactive mode.",
        ],
    }


def print_interactive_help(command: str | None = None) -> None:
    lines = _command_help_lines()
    if command is None:
        print("Interactive commands:")
        print()
        for name in INTERACTIVE_COMMANDS:
            print(f"  {lines[name][0]}")
        print()
        print("Type 'help <command>' for details.")
        return

    key = _resolve_command_alias(command.strip().lower())
    if key not in lines:
        known = ", ".join(INTERACTIVE_COMMANDS)
        print(f"Unknown command {command!r}. Known commands: {known}", file=sys.stderr)
        return

    print(textwrap.dedent("\n".join(lines[key])))


def build_interactive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="",
        description="Interactive commands (connection already open).",
        exit_on_error=False,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_command(name: str, **kwargs: object) -> argparse.ArgumentParser:
        return subparsers.add_parser(name, exit_on_error=False, **kwargs)

    set_rate = add_command("set-sample-rate", help="Set sample rate")
    _add_set_sample_rate_args(set_rate)
    set_rate.set_defaults(func=_interactive_set_sample_rate)

    set_optical_input = add_command(
        "set-optical-input-mode",
        help="Set optical input mode (ADAT or TOSlink)",
    )
    _add_set_optical_mode_args(set_optical_input)
    set_optical_input.set_defaults(func=_interactive_set_optical_input_mode)

    set_optical_output = add_command(
        "set-optical-output-mode",
        help="Set optical output mode (ADAT or TOSlink)",
    )
    _add_set_optical_mode_args(set_optical_output)
    set_optical_output.set_defaults(func=_interactive_set_optical_output_mode)

    set_level = add_command("set-level", help="Set level by entity key")
    _add_set_level_args(set_level)
    set_level.set_defaults(func=_interactive_set_level)

    set_channel_mode = add_command(
        "set-channel-mode",
        help="Link or unlink an input pair as stereo/mono",
    )
    _add_set_channel_mode_args(set_channel_mode)
    set_channel_mode.set_defaults(func=_interactive_set_channel_mode)

    set_mute = add_command("set-mute", help="Set mute by entity key")
    _add_set_mute_args(set_mute)
    set_mute.set_defaults(func=_interactive_set_mute)

    list_entities = add_command(
        "list-entities",
        help="List all entity keys (one per line)",
    )
    list_entities.set_defaults(func=_interactive_list_entities)

    solo_bus = add_command(
        "solo-output-bus",
        help="Solo one output bus (unmute it, mute all others; reverb unchanged)",
    )
    _add_solo_output_bus_args(solo_bus)
    solo_bus.set_defaults(func=_interactive_solo_output_bus)

    get_state = add_command(
        "get-state",
        help="Print current device state from received frames",
    )
    get_state.add_argument(
        "--json",
        action="store_true",
        help="Output state snapshot as JSON",
    )
    get_state.set_defaults(func=_interactive_get_state)

    monitor_meters = add_command(
        "monitor-meters",
        help="Live active meter levels (Ctrl+C to stop)",
    )
    _add_monitor_meters_args(monitor_meters)
    monitor_meters.set_defaults(func=_interactive_monitor_meters)

    help_parser = add_command("help", help="Show command help")
    help_parser.add_argument(
        "topic",
        nargs="?",
        help="Command name (omit for summary)",
    )
    help_parser.set_defaults(func=_interactive_help)

    add_command("exit", help="Disconnect and leave interactive mode")

    return parser


def _subparser_for_command(
    parser: argparse.ArgumentParser, command: str
) -> argparse.ArgumentParser | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(command)
    return None


def _print_command_syntax_help(
    parser: argparse.ArgumentParser,
    command: str | None,
) -> None:
    """Print full argparse usage for a command, or the top-level summary."""
    if command is not None:
        subparser = _subparser_for_command(parser, command)
        if subparser is not None:
            subparser.print_help(file=sys.stderr)
            return
        if command in _command_help_lines():
            print(file=sys.stderr)
            print_interactive_help(command)
            return
    parser.print_help(file=sys.stderr)


def _interactive_set_sample_rate(session: InteractiveSession, args: argparse.Namespace) -> None:
    run_set_sample_rate(session.require_device(), args.rate)


def _interactive_set_optical_input_mode(
    session: InteractiveSession, args: argparse.Namespace
) -> None:
    run_set_optical_input_mode(session.require_device(), args.mode)


def _interactive_set_optical_output_mode(
    session: InteractiveSession, args: argparse.Namespace
) -> None:
    run_set_optical_output_mode(session.require_device(), args.mode)


def _interactive_set_level(session: InteractiveSession, args: argparse.Namespace) -> None:
    run_set_level(session.require_device(), args.key, args.level)


def _interactive_set_channel_mode(
    session: InteractiveSession, args: argparse.Namespace
) -> None:
    run_set_channel_mode(session.require_device(), args.key, args.mode)


def _interactive_list_entities(
    session: InteractiveSession, args: argparse.Namespace
) -> None:
    run_list_entities()


def _interactive_set_mute(session: InteractiveSession, args: argparse.Namespace) -> None:
    run_set_mute(session.require_device(), args.key, args.value)


def _interactive_solo_output_bus(
    session: InteractiveSession, args: argparse.Namespace
) -> None:
    run_solo_output_bus(session.require_device(), args.key)


def _interactive_get_state(session: InteractiveSession, args: argparse.Namespace) -> None:
    run_get_state(session.require_device(), json=args.json)


def _interactive_monitor_meters(session: InteractiveSession, args: argparse.Namespace) -> None:
    run_monitor_meters_cmd(session.require_device(), args.rate)


def _interactive_help(session: InteractiveSession, args: argparse.Namespace) -> None:
    print_interactive_help(args.topic)


def run_interactive_loop(session: InteractiveSession) -> int:
    parser = build_interactive_parser()
    device = session.require_device()
    print(
        f"Connected to {device.url}. Type 'help' or 'exit'.",
        file=sys.stderr,
    )

    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            break

        line = line.strip()
        if not line:
            continue
        if line == "exit":
            break

        try:
            argv = shlex.split(line, posix=True)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            _print_command_syntax_help(parser, None)
            continue

        if argv:
            argv[0] = _resolve_command_alias(argv[0])

        if argv and _resolve_command_alias(argv[0]) == "set-level":
            parts = shlex.split(line, posix=True)
            if len(parts) < 3:
                print(
                    "Error: set-level requires KEY and LEVEL",
                    file=sys.stderr,
                )
                _print_command_syntax_help(parser, "set-level")
                continue
            argv = ["set-level", parts[1], parts[2]]

        try:
            args = parser.parse_args(argv)
        except argparse.ArgumentError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            _print_command_syntax_help(parser, argv[0] if argv else None)
            continue

        if args.command == "exit":
            break

        try:
            args.func(session, args)
        except (UltraLiteMk5Error, ValueError, KeyError) as exc:
            print(f"Error: {exc}", file=sys.stderr)

    session.close()
    print("Disconnected.", file=sys.stderr)
    return 0
