# ultralite-mk5-lib

Python library and CLI for controlling MOTU UltraLite mk5 over a WebSocket connection. 

**Under active development.** Expect bugs, incomplete coverage of device features, and breaking changes.

This project has only been tested with:
- UltraLite mk5 connected via USB to Windows host.
- UltraLite mk5 firmware 2.0.9+2572

This project is not affiliated with or endorsed by MOTU. As there is no official public API, this integration is likely to break with firmware updates.

## Requirements

- Python 3.10+
- CueMix or the MOTU driver running on the host machine
- Device password protection **disabled** (password auth is not implemented)

## Installation

```bash
git clone https://github.com/thedirtyd/ultralite-mk5-lib.git
cd ultralite-mk5-lib
pip install -e .
```

## Configuration

Copy `config.yaml.example` to `config.yaml` in your working directory and set your device defaults:

```yaml
host: 127.0.0.1
serial: ULM5FFF0EE
port: 1281      # optional
timeout: 3.0    # optional
```

Find your device serial in CueMix 5 under the **Discovery** tab. `port` and `timeout` are optional; omit them to use the defaults shown above.

The CLI reads this file automatically. Command-line flags (`--host`, `--serial`, `--port`, `--timeout`) override config values when provided.

## Command line

With `config.yaml` in place, run commands directly. Start an interactive session with `connect` (recommended):

```bash
python -m ultralite_mk5_lib connect
```

At the `ultralite-mk5>` prompt, Tab completes commands and entity keys; press Tab again to list all matches.

```
ultralite-mk5> get-state
ultralite-mk5> get-state --json
ultralite-mk5> monitor-meters
ultralite-mk5> set-sample-rate --rate 96
ultralite-mk5> set-optical-input-mode adat
ultralite-mk5> set-optical-output-mode toslink
ultralite-mk5> set-level MIXBUSFADER_PHONES_MICLINEIN01 -12db
ultralite-mk5> set-level MIXBUSFADER_MAIN0102_LINEIN03 0.75
ultralite-mk5> set-level VOLUME_MAIN -48db
ultralite-mk5> set-level VOLUME_MAIN -inf
ultralite-mk5> set-level INPUTGAIN_MICLINEIN01 12
ultralite-mk5> set-channel-mode MIXINPUT_OPTICAL01 stereo
ultralite-mk5> set-channel-mode MIXINPUT_HOST0102 stereo
ultralite-mk5> set-mute MIXBUSFADER_MAIN0102_OUT
ultralite-mk5> set-mute MIXBUSFADER_PHONES_LINEIN03 unmute
ultralite-mk5> solo-output-bus MIXBUSFADER_MAIN0102_OUT
ultralite-mk5> list-entities
ultralite-mk5> help
ultralite-mk5> exit
```


| Command                       | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| `get-state`                   | Rich tables: trims, input gain, mix bus matrix, meters    |
| `get-state --json`            | Same data as JSON                                         |
| `list-entities`               | All entity keys, one per line (no device state required)  |
| `monitor-meters`              | Live meter levels (Ctrl+C to stop)                        |
| `set-sample-rate --rate RATE` | 44.1, 48, 88.2, 96, 176.4, 192 kHz (or Hz equivalents)    |
| `set-optical-input-mode MODE` | Optical input: `adat` or `toslink`                            |
| `set-optical-output-mode MODE`| Optical output: `adat` or `toslink`                           |
| `set-level KEY LEVEL`         | Set level by entity key (`0.75`, `-6db`, `-inf`, `12`, …) |
| `set-channel-mode KEY MODE`   | Link/unlink input pair as `stereo` or `mono` (physical inputs and host returns) |
| `set-mute KEY [VALUE]`        | Mute/unmute by entity key (default VALUE: mute)           |
| `solo-output-bus KEY`         | Unmute one bus, mute all others (reverb unchanged)        |
| `help`                        | Command help                                              |
| `exit`                        | Disconnect                                                |


You can also run any command directly without entering interactive mode. Long-running commands such as `monitor-meters` exit on Ctrl+C:

```bash
python -m ultralite_mk5_lib get-state
python -m ultralite_mk5_lib get-state --json
python -m ultralite_mk5_lib monitor-meters
python -m ultralite_mk5_lib set-sample-rate --rate 96
python -m ultralite_mk5_lib set-optical-input-mode adat
python -m ultralite_mk5_lib set-optical-output-mode toslink
```

Override config for a single invocation:

```bash
python -m ultralite_mk5_lib --serial ULM5OTHER0 set-sample-rate --rate 48
```

`list-entities` does not require a device connection or `config.yaml`.

If `ultralite-mk5` is on your PATH after install, you can use that instead of `python -m ultralite_mk5_lib`.

## Python API

```python
from ultralite_mk5_lib import (
    Buses,
    InputMeters,
    InputPairs,
    Inputs,
    LineOutputs,
    Monitors,
    UltraLiteMk5,
    build_state_report,
)

with UltraLiteMk5("127.0.0.1", serial="ULM5FFF0EE") as device:
    device.wait_ready()

    device.settings.sample_rate = 96000
    device.settings.optical_input_mode = "adat"
    device.settings.optical_output_mode = "toslink"

    device.inputs[Inputs.MicLineIn01].gain_db = 12
    device.inputs[Inputs.MicLineIn01].phantom = True

    # Mix crosspoint fader (stereo-linked pairs mirror to R automatically)
    device.mix[Buses.Phones].channel[Inputs.MicLineIn01].fader.db = -12.0
    # Or address the pair explicitly (always writes L and R)
    device.mix[Buses.Phones].channel[InputPairs.MicLineIn0102].fader.db = -12.0
    # Entity keys (same strings as CLI / list-entities) also work
    device.mix.fader_by_key("MIXBUSFADER_PHONES_MICLINEIN01").db = -12.0

    device.mix[Buses.Main0102].out.db = -6.0
    device.mix[Buses.Phones].muted = False
    device.mix[Buses.Phones].solo()

    device.mix.stereo[Inputs.MicLineIn01].linked = True

    device.outputs.monitor[Monitors.Main].trim_db = -6.0
    device.outputs.line[LineOutputs.MainOut01].trim_db = -10.0

    print(device.meters.input[InputMeters.MicLineIn01].db)
    print(device.layout.visible_fader_keys())

    report = build_state_report(device.state.snapshot())
    print(report["device"]["optical_input_mode"])
    print(device.snapshot_json())
```

Entity key strings (`MIXBUSFADER_*`, `INPUTGAIN_*`, etc.) remain the stable identifiers used by the CLI and integrations. The typed enums (`Inputs`, `Buses`, …) map to the same wire indices underneath.

## Limitations

- Password-protected devices are not supported.

