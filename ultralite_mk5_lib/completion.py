"""Tab completion for the interactive CLI REPL."""

from __future__ import annotations

import shutil
import sys

from ultralite_mk5_lib.entities import (
    CLEAR_MIX_SOLO_KEYS,
    INPUT_48V_ENTITY_KEYS,
    INPUT_PAD_ENTITY_KEYS,
    SET_CHANNEL_MODE_ENTITY_KEYS,
    SET_LEVEL_ENTITY_KEYS,
    SET_MUTE_ENTITY_KEYS,
    SET_SOLO_ENTITY_KEYS,
    SET_PAN_ENTITY_KEYS,
    SOLO_OUTPUT_BUS_KEYS,
)
from ultralite_mk5_lib.eq import EQ_BAND_KEYS
from ultralite_mk5_lib.protocol import VALID_SAMPLE_RATES

try:
    import readline
except ImportError:  # pragma: no cover - Windows without pyreadline
    readline = None  # type: ignore[assignment]

_SOLO_VALUE_CHOICES: tuple[str, ...] = (
    "solo",
    "unsolo",
    "on",
    "off",
    "true",
    "false",
    "1",
    "0",
)

_PAN_VALUE_CHOICES: tuple[str, ...] = (
    "0",
    "0.0",
    "0.5",
    "1",
    "1.0",
    "center",
    "c",
    "l",
    "left",
    "r",
    "right",
)

_EQ_PARAM_CHOICES: tuple[str, ...] = ("enable", "freq", "gain", "q", "curve")

_EQ_ENABLE_CHOICES: tuple[str, ...] = ("on", "off", "true", "false", "1", "0")

_EQ_CURVE_CHOICES: tuple[str, ...] = ("peak", "lowshelf", "highshelf", "highpass")

_INPUT_MONITOR_VALUE_CHOICES: tuple[str, ...] = (
    "toggle",
    "on",
    "off",
    "true",
    "false",
    "1",
    "0",
)

_COMMAND_ENTITY_KEYS: dict[str, tuple[str, ...]] = {
    "set-level": SET_LEVEL_ENTITY_KEYS,
    "set-mute": SET_MUTE_ENTITY_KEYS,
    "set-solo": SET_SOLO_ENTITY_KEYS,
    "set-pan": SET_PAN_ENTITY_KEYS,
    "set-48v": INPUT_48V_ENTITY_KEYS,
    "set-pad": INPUT_PAD_ENTITY_KEYS,
    "set-eq": EQ_BAND_KEYS,
    "solo-output-bus": SOLO_OUTPUT_BUS_KEYS,
    "clear-mix-solo": CLEAR_MIX_SOLO_KEYS,
    "set-channel-mode": SET_CHANNEL_MODE_ENTITY_KEYS,
}

_MUTE_VALUE_CHOICES: tuple[str, ...] = (
    "mute",
    "unmute",
    "on",
    "off",
    "true",
    "false",
    "1",
    "0",
)

_TOGGLE_VALUE_CHOICES: tuple[str, ...] = (
    "on",
    "off",
    "true",
    "false",
    "1",
    "0",
)

_AB_PATH_CHOICES: tuple[str, ...] = ("a", "b", "both")

_OPTICAL_MODE_CHOICES: tuple[str, ...] = ("adat", "toslink")

_CHANNEL_MODE_CHOICES: tuple[str, ...] = ("stereo", "mono")

_SAMPLE_RATE_CHOICES: tuple[str, ...] = tuple(
    sorted(
        {
            *(f"{rate / 1000:g}" for rate in VALID_SAMPLE_RATES),
            *(str(rate) for rate in VALID_SAMPLE_RATES),
        }
    )
)


def _resolve_command_alias(name: str) -> str:
    from ultralite_mk5_lib.interactive import COMMAND_ALIASES

    return COMMAND_ALIASES.get(name.lower(), name)


def _command_names() -> tuple[str, ...]:
    from ultralite_mk5_lib.interactive import COMMAND_ALIASES, INTERACTIVE_COMMANDS

    return tuple(sorted({*INTERACTIVE_COMMANDS, *COMMAND_ALIASES}))


def _split_line(line: str) -> tuple[list[str], bool]:
    """Split a partial line into tokens; trailing space starts a new empty token."""
    if not line:
        return [], False
    trailing_space = line[-1].isspace()
    tokens = line.split()
    return tokens, trailing_space


def _filter_prefix(candidates: tuple[str, ...] | list[str], prefix: str) -> list[str]:
    if not prefix:
        return list(candidates)
    upper = prefix.upper()
    return [c for c in candidates if c.upper().startswith(upper)]


def _entity_candidates(command: str, prefix: str) -> list[str]:
    keys = _COMMAND_ENTITY_KEYS.get(command)
    if keys is None:
        return []
    return _filter_prefix(keys, prefix)


def _filter_readline_candidates(text: str, candidates: list[str]) -> list[str]:
    if not text:
        return candidates
    upper = text.upper()
    return [c for c in candidates if c.upper().startswith(upper)]


def readline_matches(text: str, candidates: list[str], *, allow_lcp: bool = True) -> list[str]:
    """Shape candidates for GNU readline's case-sensitive prefix rules."""
    filtered = _filter_readline_candidates(text, candidates)
    if not filtered:
        return []
    if len(filtered) == 1:
        return filtered
    if (
        allow_lcp
        and text
        and all(match.startswith(text) for match in filtered)
    ):
        return filtered
    # Multiple matches without a safe shared prefix: return the typed text only
    # so readline does not apply a bogus longest-common-prefix extension.
    return [text]


def _completion_context(line: str, endidx: int) -> tuple[str, bool]:
    """Return (partial token text, allow_lcp) for readline at endidx."""
    partial_line = line[:endidx]
    tokens, trailing_space = _split_line(partial_line)
    if not tokens:
        return "", True

    command = _resolve_command_alias(tokens[0])

    if trailing_space:
        if command in _COMMAND_ENTITY_KEYS:
            return "", False
        return "", True

    text = tokens[-1]
    if len(tokens) == 1:
        return text, True

    if command in _COMMAND_ENTITY_KEYS and len(tokens) == 2:
        return text, False
    return text, True


def _print_completion_options(matches: list[str]) -> None:
    if len(matches) <= 1:
        return
    print()
    print(_format_columns(sorted(matches)))
    print(_prompt, end="")
    print(readline.get_line_buffer(), end="", flush=True)


def completion_candidates(line: str, endidx: int) -> list[str]:
    """Return completion strings for the partial line up to endidx."""
    text = line[:endidx]
    tokens, trailing_space = _split_line(text)

    if not tokens:
        return list(_command_names())

    command = _resolve_command_alias(tokens[0])
    token_index = len(tokens) - 1 if not trailing_space else len(tokens)
    prefix = "" if trailing_space else tokens[-1]

    if token_index == 0:
        return _filter_prefix(_command_names(), prefix)

    if command == "help":
        return _filter_prefix(_command_names(), prefix)

    if command in ("exit", "list-entities"):
        return []

    if command == "get-state":
        if token_index == 1 and (not prefix or prefix.startswith("-")):
            if prefix in ("", "-", "--", "--j", "--js", "--jso", "--json"):
                return ["--json"]
        return []

    if command in ("set-optical-input-mode", "set-optical-output-mode"):
        if token_index == 1:
            return _filter_prefix(_OPTICAL_MODE_CHOICES, prefix)
        return []

    if command == "set-ab-monitor":
        if token_index == 1:
            return _filter_prefix(_TOGGLE_VALUE_CHOICES, prefix)
        return []

    if command == "set-ab-path":
        if token_index == 1:
            return _filter_prefix(_AB_PATH_CHOICES, prefix)
        return []

    if command == "set-sample-rate":
        if token_index == 1:
            if prefix in ("", "-", "--", "--r", "--ra", "--rat", "--rate"):
                return ["--rate"]
            return []
        if token_index == 2 and tokens[1] == "--rate":
            return _filter_prefix(_SAMPLE_RATE_CHOICES, prefix)
        return []

    if command == "monitor-meters":
        if token_index == 1 and prefix.startswith("-"):
            if prefix in ("", "-", "--", "--r", "--ra", "--rat", "--rate"):
                return ["--rate"]
        return []

    if command == "set-channel-mode":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_CHANNEL_MODE_CHOICES, prefix)
        return []

    if command == "set-level":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        return []

    if command == "set-mute":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_MUTE_VALUE_CHOICES, prefix)
        return []

    if command == "set-solo":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_SOLO_VALUE_CHOICES, prefix)
        return []

    if command == "set-pan":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_PAN_VALUE_CHOICES, prefix)
        return []

    if command == "set-input-monitor":
        if token_index == 1:
            return _filter_prefix(("main", "phones"), prefix)
        if token_index == 2:
            return _filter_prefix(tuple(str(i) for i in range(8)), prefix)
        if token_index == 3:
            return _filter_prefix(_INPUT_MONITOR_VALUE_CHOICES, prefix)
        return []

    if command == "set-48v":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_TOGGLE_VALUE_CHOICES, prefix)
        return []

    if command == "set-pad":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_TOGGLE_VALUE_CHOICES, prefix)
        return []

    if command == "set-eq":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        if token_index == 2:
            return _filter_prefix(_EQ_PARAM_CHOICES, prefix)
        if token_index == 3:
            param = tokens[2].lower() if len(tokens) > 2 else ""
            if param == "enable":
                return _filter_prefix(_EQ_ENABLE_CHOICES, prefix)
            if param == "curve":
                return _filter_prefix(_EQ_CURVE_CHOICES, prefix)
        return []

    if command == "solo-output-bus":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        return []

    if command == "clear-mix-solo":
        if token_index == 1:
            return _entity_candidates(command, prefix)
        return []

    return []


def _format_columns(matches: list[str]) -> str:
    if not matches:
        return ""
    width = max(len(match) for match in matches) + 2
    try:
        cols = max(1, shutil.get_terminal_size().columns // width)
    except OSError:
        cols = 1
    lines: list[str] = []
    for start in range(0, len(matches), cols):
        row = matches[start : start + cols]
        lines.append("".join(match.ljust(width) for match in row))
    return "\n".join(lines)


class InteractiveCompleter:
    """Readline completer for the interactive REPL."""

    def __init__(self) -> None:
        self._matches: list[str] = []
        self.display_matches: list[str] = []
        self._printed_options = False

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            line = readline.get_line_buffer()
            endidx = readline.get_endidx()
            _, allow_lcp = _completion_context(line, endidx)
            candidates = completion_candidates(line, endidx)
            display_matches = _filter_readline_candidates(text, candidates)
            self.display_matches = display_matches
            self._printed_options = False
            if not allow_lcp and len(display_matches) > 1:
                _print_completion_options(display_matches)
                self._printed_options = True
            self._matches = readline_matches(
                text,
                candidates,
                allow_lcp=allow_lcp,
            )
        try:
            return self._matches[state]
        except IndexError:
            return None


_completer = InteractiveCompleter()
_readline_enabled = False
_prompt = "ultralite-mk5> "


def _display_matches(substitution: str, matches: list[str], longest_match_length: int) -> None:
    del substitution, longest_match_length
    if _completer._printed_options:
        return
    to_show = _completer.display_matches or matches
    if len(to_show) <= 1:
        return
    _print_completion_options(to_show)


def setup_interactive_completion(*, prompt: str = "ultralite-mk5> ") -> bool:
    """Configure readline tab completion. Returns True when readline is active."""
    global _readline_enabled, _prompt
    _prompt = prompt
    if readline is None or not sys.stdin.isatty():
        _readline_enabled = False
        return False

    readline.set_completer(_completer.complete)
    readline.set_completer_delims(" \t\n")
    readline.parse_and_bind("tab: complete")
    try:
        readline.parse_and_bind("set show-all-if-ambiguous on")
    except Exception:
        pass
    readline.set_completion_display_matches_hook(_display_matches)
    _readline_enabled = True
    return True


def readline_input(prompt: str = "ultralite-mk5> ") -> str:
    """Read a line with tab completion when readline and a TTY are available."""
    if readline is None or not _readline_enabled:
        return input(prompt)
    return input(prompt)
