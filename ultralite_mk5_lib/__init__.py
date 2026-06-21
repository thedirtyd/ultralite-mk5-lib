"""Control MOTU UltraLite mk5 / Gen5 devices over WebSocket."""

from ultralite_mk5_lib.client import UltraLiteMk5
from ultralite_mk5_lib.entities import (
    ALL_ENTITY_KEYS,
    DISPLAY_NAMES,
    SOLO_OUTPUT_BUS_KEYS,
    display_name,
    meter_slot,
    property_index,
    resolve_entity,
)
from ultralite_mk5_lib.report import build_state_report, state_report_to_json
from ultralite_mk5_lib.state import DeviceState, snapshot_to_json
from ultralite_mk5_lib.exceptions import (
    NotConnectedError,
    PasswordRequiredError,
    UltraLiteMk5Error,
)
from ultralite_mk5_lib.protocol import (
    VALID_SAMPLE_RATES,
    format_optical_mode,
    optical_input_mode_from_snap,
    optical_output_mode_from_snap,
    parse_optical_mode,
)

__all__ = [
    "ALL_ENTITY_KEYS",
    "DISPLAY_NAMES",
    "DeviceState",
    "SOLO_OUTPUT_BUS_KEYS",
    "NotConnectedError",
    "PasswordRequiredError",
    "UltraLiteMk5",
    "UltraLiteMk5Error",
    "VALID_SAMPLE_RATES",
    "build_state_report",
    "display_name",
    "format_optical_mode",
    "meter_slot",
    "optical_input_mode_from_snap",
    "optical_output_mode_from_snap",
    "parse_optical_mode",
    "property_index",
    "resolve_entity",
    "snapshot_to_json",
    "state_report_to_json",
]
