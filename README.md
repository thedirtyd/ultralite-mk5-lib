# ultralite-mk5-lib

Python library and CLI for controlling MOTU UltraLite mk5 over a WebSocket connection. 

**Under active development.** Expect bugs, incomplete coverage of device features, and breaking changes.

Tested with UltraLite mk5 firmware 2.0.9+2572 only.

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

At the `ultralite-mk5>` prompt:

```
ultralite-mk5> get-state
ultralite-mk5> get-state --json
ultralite-mk5> monitor-meters
ultralite-mk5> set-sample-rate --rate 96
ultralite-mk5> set-optical-input-mode adat
ultralite-mk5> set-optical-output-mode toslink
ultralite-mk5> set-level MIXBUSFADER_MAIN0102_LINEIN03 0.75
ultralite-mk5> set-level VOLUME_MAIN -48db
ultralite-mk5> set-level VOLUME_MAIN -inf
ultralite-mk5> set-level INPUTGAIN_MICLINEIN01 12
ultralite-mk5> set-channel-mode MIXINPUT_OPTICAL01 stereo
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
| `set-channel-mode KEY MODE`   | Link/unlink input pair as `stereo` or `mono`              |
| `set-mute KEY [VALUE]`        | Mute/unmute by entity key (default VALUE: mute)           |
| `solo-output-bus KEY`         | Unmute one bus, mute all others (reverb unchanged)        |
| `help`                        | Command help                                              |
| `exit`                        | Disconnect                                                |


You can also run any command directly without entering interactive mode. Long-running commands such as `monitor-meters` exit on Ctrl+C:

```bash
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
from ultralite_mk5_lib import UltraLiteMk5, build_state_report

with UltraLiteMk5("127.0.0.1", serial="ULM5FFF0EE") as device:
    device.set_sample_rate(96000)
    device.set_optical_input_mode("adat")
    device.set_optical_output_mode("toslink")
    device.set_mute("MIXBUSFADER_MAIN0102_OUT")
    device.set_level("MIXBUSFADER_MAIN0102_LINEIN03", "0.75")
    device.set_level("VOLUME_MAIN", "-6db")
    device.solo_output_bus("MIXBUSFADER_PHONES_OUT")

    # Wait for state if you need it
    device.state.wait_until_ready(device.timeout)
    print(device.state.optical_input_mode)   # "adat" or "toslink"
    print(device.state.optical_output_mode)
    report = build_state_report(device.state.snapshot())
    print(report["device"]["optical_input_mode"])
    print(device.snapshot_json())
```

## Limitations

- Password-protected devices are not supported.

