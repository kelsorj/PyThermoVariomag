# PyThermoVariomag

Small Python control app for a Thermo / Variomag Teleshake orbital shaking station over RS-232 serial.

The simple GUI mirrors the vendor diagnostics dialog: choose a COM port, RPM, stir direction, then start or stop the shaker.

## Features

- Windows-friendly Tkinter GUI.
- Uses `COM4` by default.
- Uses the captured vendor serial settings: `9600 8N1`.
- Supports RPM values from `100` to `2000`.
- Supports the six stir directions.
- Sends the confirmed 6-byte binary telegram protocol.

## Install

```powershell
python -m pip install -e .
```

## Run

```powershell
pythermovariomag
```

Or run directly from source:

```powershell
python -m pythermovariomag
```

## Confirmed Protocol

Each command is a 6-byte packet:

```text
[0x61, command, data1, data2, data3, checksum]
checksum = sum(first five bytes) % 256
```

Confirmed commands:

```text
0x30 = start
0x31 = stop
0x33 = set speed as 24-bit cycle time
0x34 = set stir direction
0x3C = apply settings
```

Speed is encoded as cycle time in microseconds:

```text
cycle_time_us = 60,000,000 / rpm
```

Confirmed direction values:

```text
NWSE  = 0x01
NESW  = 0x02
EW    = 0x10
NS    = 0x20
NE,SW = 0x08
NW,SE = 0x04
```

Start sequence:

```text
set speed -> set direction -> apply settings -> start
```

Stop sequence:

```text
stop
```

## Safety

This controls real lab hardware. Verify the plate/deck area is clear.
