"""Rich terminal rendering for device state snapshots."""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.table import Table
from rich.text import Text

from ultralite_mk5_lib.mix_buses import build_mix_bus_fader_matrix, mix_fader_gain_to_db
from ultralite_mk5_lib.inputs import build_input_gains
from ultralite_mk5_lib.meters import iter_visible_meter_slots, resolve_meter_slot_name
from ultralite_mk5_lib.protocol import (
    optical_input_mode_from_snap,
    optical_input_mode_wire_from_snap,
    optical_output_mode_from_snap,
)
from ultralite_mk5_lib.outputs import (
    TRIM_MAX_DB,
    TRIM_MIN_DB,
    build_monitors_trim,
    build_output_trims,
)
from ultralite_mk5_lib.state import (
    FADER_BUS_MAX_DB,
    FADER_BUS_MIN_DB,
    K_MIN_METER_DB,
    METER_BAR_WIDTH,
    db_to_fader_position,
    format_db,
    format_fader_bar,
    format_meter_bar,
)

if TYPE_CHECKING:
    from ultralite_mk5_lib.client import UltraLiteMk5

_console = Console()

_MIX_BUS_FADER_BAR_MIN = 6
_ACTIVE_METERS_TITLE = "Meters"
# Table borders and column padding (characters).
_TABLE_CHROME = 4


def _format_mute(muted: bool | None) -> str:
    if muted is None:
        return "n/a"
    return "true" if muted else "false"


def _terminal_level_bar_width(reserved: int) -> int:
    """Bar width after fixed columns; at least METER_BAR_WIDTH."""
    width = _console.size.width
    if width is None or width < 40:
        width = 80
    # Slack for column separators and header/body width differences in Rich layout.
    return max(METER_BAR_WIDTH, width - _TABLE_CHROME - reserved - 6)


def _table_width() -> int:
    width = _console.size.width
    if width is None or width < 40:
        return 80
    return width


def _meter_table_reserved(rows: list[tuple[int, float | None]]) -> int:
    if not rows:
        return 40
    name_w = max(len(resolve_meter_slot_name(r[0])) for r in rows)
    return name_w + 7  # dB


def _extra_column_width(extra: bool | str | None) -> int:
    if extra is None:
        return 3
    if isinstance(extra, bool):
        return len(_format_mute(extra))
    return len(extra)


def _fader_table_reserved(
    rows: list[tuple[str, float | None, bool | str | None]],
    *,
    extra_header: str | None,
) -> int:
    if not rows:
        return 42 if extra_header else 30
    name_w = max(len(name) for name, _, _ in rows)
    reserve = name_w + 7  # dB
    if extra_header:
        extra_w = max(_extra_column_width(extra) for _, _, extra in rows)
        reserve += max(len(extra_header), extra_w) + 1
    return reserve


def _catalog_meter_rows(
    meters: list[float],
    *,
    meters_received: bool,
    sample_rate: int | None = None,
    optical_input_mode: int | None = None,
) -> list[tuple[int, float | None]]:
    """One row per visible catalog entry, in display_index order."""
    rows: list[tuple[int, float | None]] = []
    for entry in iter_visible_meter_slots(
        sample_rate=sample_rate,
        optical_input_mode=optical_input_mode,
    ):
        slot = entry.slot
        if not meters_received or slot < 0 or slot >= len(meters):
            db: float | None = None
        else:
            db = meters[slot]
            if db <= K_MIN_METER_DB:
                db = K_MIN_METER_DB
        rows.append((slot, db))
    return rows


def _build_meter_table(rows: list[tuple[int, float | None]]) -> Table:
    bar_width = _terminal_level_bar_width(_meter_table_reserved(rows))
    table = Table(
        show_header=True,
        header_style="bold",
        expand=True,
        width=_table_width(),
        padding=(0, 1),
    )
    table.add_column("name", no_wrap=True)
    table.add_column("dB", justify="right", no_wrap=True)
    table.add_column("level", no_wrap=True, min_width=bar_width, ratio=1)
    for slot, db in rows:
        table.add_row(
            resolve_meter_slot_name(slot),
            format_db(db),
            format_meter_bar(db, width=bar_width),
        )
    return table


def _build_active_meters_panel(snap: dict[str, Any]) -> RenderableType:
    """Build the meters section used by get-state and monitor-meters."""
    title = Text(_ACTIVE_METERS_TITLE, style="bold")
    rows = _catalog_meter_rows(
        snap.get("meters", []),
        meters_received=bool(snap.get("meters_received")),
        sample_rate=snap.get("sample_rate"),
        optical_input_mode=optical_input_mode_wire_from_snap(snap),
    )
    return Group(title, _build_meter_table(rows))


def _print_fader_table(
    rows: list[tuple[str, float | None, bool | str | None]],
    *,
    title: str,
    min_db: float,
    max_db: float,
    extra_header: str | None = None,
    row_limits: list[tuple[float, float]] | None = None,
) -> None:
    _console.print(f"[bold]{title}[/bold]")
    bar_width = _terminal_level_bar_width(
        _fader_table_reserved(rows, extra_header=extra_header),
    )
    table = Table(
        show_header=True,
        header_style="bold",
        expand=True,
        width=_table_width(),
        padding=(0, 1),
    )
    table.add_column("name", no_wrap=True)
    table.add_column("dB", justify="right", no_wrap=True)
    if extra_header:
        table.add_column(extra_header, no_wrap=True)
    table.add_column("position", no_wrap=True, min_width=bar_width, ratio=1)

    for i, (name, db, extra) in enumerate(rows):
        row_min, row_max = row_limits[i] if row_limits else (min_db, max_db)
        pos = db_to_fader_position(
            db,
            min_db=row_min,
            max_db=row_max,
            width=bar_width,
        )
        bar = format_fader_bar(pos, width=bar_width)
        if extra_header:
            extra_val = _format_mute(extra) if isinstance(extra, bool) else (
                extra if extra is not None else "n/a"
            )
            table.add_row(name, format_db(db), extra_val, bar)
        else:
            table.add_row(name, format_db(db), bar)

    _console.print(table)
    _console.print()


def _mix_bus_matrix_bar_width(column_count: int, name_width: int) -> int:
    """Fader bar width per matrix column given terminal width."""
    width = _console.size.width
    if width is None or width < 40:
        width = 80
    reserved = name_width + _TABLE_CHROME + 4
    per_col = (width - reserved) // max(column_count, 1)
    return max(_MIX_BUS_FADER_BAR_MIN, per_col)


def _mix_bus_fader_cell(
    cell: dict[str, Any],
    *,
    bar_width: int,
) -> tuple[str, str]:
    """Return (bar, detail) strings for one matrix cell."""
    gain = cell.get("gain")
    db = cell.get("db")
    if db is None and gain is not None:
        db = mix_fader_gain_to_db(gain)
    muted = cell.get("mute")
    pos = db_to_fader_position(
        db,
        min_db=FADER_BUS_MIN_DB,
        max_db=FADER_BUS_MAX_DB,
        width=bar_width,
    )
    bar = format_fader_bar(pos, width=bar_width)
    detail = _format_fader_detail_cell(db, muted, width=bar_width)
    return bar, detail


def _format_bus_column_header(bus_name: str) -> str:
    """Title-case bus name for column headers (e.g. main 1-2 → Main 1-2)."""
    if not bus_name:
        return bus_name
    return bus_name[0].upper() + bus_name[1:]


def _format_fader_detail_cell(
    db: float | None,
    muted: bool | None,
    *,
    width: int,
) -> str:
    """Second row: dB left-aligned; M in the rightmost column when muted."""
    db_str = format_db(db)
    if width <= 1:
        return "M" if muted else db_str[:1]
    if len(db_str) >= width:
        db_str = db_str[: width - 1]
    suffix = "M" if muted else " "
    return db_str.ljust(width - 1) + suffix


def _build_mix_bus_fader_matrix_table(snap: dict[str, Any]) -> Table:
    matrix = snap.get("mix_bus_fader_matrix")
    if not matrix:
        props = snap.get("props", {})
        matrix = build_mix_bus_fader_matrix(
            props,
            sample_rate=snap.get("sample_rate"),
            optical_input_mode=optical_input_mode_wire_from_snap(snap),
        )

    columns = matrix.get("columns", [])
    buses = matrix.get("buses", [])
    bus_labels = [_format_bus_column_header(b["name"]) for b in buses]
    channel_labels = [c["label"] for c in columns]
    if channel_labels:
        name_width = max(len("Channel"), *(len(label) for label in channel_labels))
    else:
        name_width = len("Channel")
    bar_width = _mix_bus_matrix_bar_width(len(bus_labels), name_width)

    table = Table(
        show_header=True,
        header_style="bold",
        expand=True,
        width=_table_width(),
        padding=(0, 0),
        pad_edge=False,
    )
    table.add_column("Channel", no_wrap=True, min_width=name_width)
    for label in bus_labels:
        table.add_column(
            label,
            no_wrap=True,
            min_width=bar_width,
            justify="left",
        )

    for col_idx, col in enumerate(columns):
        bar_cells: list[str] = []
        detail_cells: list[str] = []
        for bus in buses:
            faders = bus.get("faders", [])
            if col_idx >= len(faders):
                bar_cells.append(format_fader_bar(None, width=bar_width))
                detail_cells.append(
                    _format_fader_detail_cell(None, None, width=bar_width)
                )
                continue
            bar, detail = _mix_bus_fader_cell(faders[col_idx], bar_width=bar_width)
            bar_cells.append(bar)
            detail_cells.append(detail)
        table.add_row(col["label"], *bar_cells)
        table.add_row("", *detail_cells)
    return table


def _print_mix_bus_fader_matrix(snap: dict[str, Any]) -> None:
    _console.print("[bold]Mix Bus Faders[/bold]")
    _console.print(_build_mix_bus_fader_matrix_table(snap))
    _console.print()


def _print_input_gain_table(snap: dict[str, Any]) -> None:
    props = snap.get("props", {})
    gain_rows = build_input_gains(props)
    fader_rows = [(name, db, None) for name, db, _min, _max in gain_rows]
    limits = [(min_db, max_db) for _name, _db, min_db, max_db in gain_rows]
    _print_fader_table(
        fader_rows,
        title="Input Gain",
        min_db=0.0,
        max_db=74.0,
        row_limits=limits,
    )


def _print_output_trim_table(snap: dict[str, Any]) -> None:
    props = snap.get("props", {})
    trim_rows = [(name, db, None) for name, db in build_output_trims(props)]
    _print_fader_table(
        trim_rows,
        title="Output Trim",
        min_db=TRIM_MIN_DB,
        max_db=TRIM_MAX_DB,
    )


def _print_monitors_trim_table(snap: dict[str, Any]) -> None:
    props = snap.get("props", {})
    _print_fader_table(
        [(name, db, mute) for name, _key, db, mute in build_monitors_trim(props)],
        title="Monitor Trim",
        min_db=TRIM_MIN_DB,
        max_db=TRIM_MAX_DB,
        extra_header="mute",
    )


def print_state_snapshot(snap: dict[str, Any]) -> None:
    """Print a human-readable state summary using Rich tables."""
    device_name = snap.get("device_name") or "n/a"
    sample_rate = snap.get("sample_rate")
    api_version = snap.get("api_version")

    _console.print(f"Device:       {device_name}")
    if api_version is not None:
        _console.print(f"API version:  {api_version}")
    if sample_rate is not None:
        _console.print(f"Sample rate:  {sample_rate} Hz")
    else:
        _console.print("Sample rate:  n/a")

    optical_input = snap.get("optical_input_mode", optical_input_mode_from_snap(snap))
    optical_output = snap.get("optical_output_mode", optical_output_mode_from_snap(snap))
    _console.print(
        f"Optical in:   {optical_input if optical_input is not None else 'n/a'}"
    )
    _console.print(
        f"Optical out:  {optical_output if optical_output is not None else 'n/a'}"
    )

    _console.print()
    _print_monitors_trim_table(snap)
    _print_input_gain_table(snap)
    _print_output_trim_table(snap)
    _print_mix_bus_fader_matrix(snap)

    _console.print(_build_active_meters_panel(snap))
    _console.print()
    _console.print(f"Frames received: {snap.get('frame_count', 0)}")


def run_monitor_meters(device: UltraLiteMk5, *, refresh_hz: float = 12.0) -> None:
    """Live-refresh the active meters table until Ctrl+C."""
    if refresh_hz <= 0:
        raise ValueError(f"refresh_hz must be positive, got {refresh_hz}")

    def wait_for_meters() -> None:
        if device.state.meters_received:
            return
        print("Waiting for meters...", file=sys.stderr)
        device.state.wait_for(lambda state: state.meters_received, device.timeout)

    wait_for_meters()

    interval = 1.0 / refresh_hz
    try:
        with Live(_build_active_meters_panel(device.state.snapshot()), console=_console, screen=False) as live:
            while True:
                if not device.connected:
                    device.wait_until_connected()
                    wait_for_meters()
                live.update(_build_active_meters_panel(device.state.snapshot()))
                time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
