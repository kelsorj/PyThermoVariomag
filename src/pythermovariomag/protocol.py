from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import serial


DIRECTION_VALUES = {
    "NWSE": 0x01,
    "NESW": 0x02,
    "EW": 0x10,
    "NS": 0x20,
    "NE,SW": 0x08,
    "NW,SE": 0x04,
}

COMMAND_START = 0x30
COMMAND_STOP = 0x31
COMMAND_SET_SPEED = 0x33
COMMAND_SET_DIRECTION = 0x34
COMMAND_APPLY_SETTINGS = 0x3C
CONTROL_BYTE = 0x61


@dataclass(frozen=True)
class Transaction:
    label: str
    tx: bytes
    rx: Optional[bytes]


def format_hex(data: Optional[bytes]) -> str:
    if not data:
        return "timeout"
    return " ".join(f"{byte:02X}" for byte in data)


def build_packet(command: int, data: list[int]) -> bytes:
    payload = [CONTROL_BYTE, command & 0xFF] + [byte & 0xFF for byte in data[:3]]
    while len(payload) < 5:
        payload.append(0)
    payload.append(sum(payload[:5]) % 256)
    return bytes(payload)


def speed_to_cycle_time_bytes(rpm: int) -> tuple[int, int, int]:
    cycle_time_us = int(60_000_000 / rpm)
    return (
        (cycle_time_us >> 16) & 0xFF,
        (cycle_time_us >> 8) & 0xFF,
        cycle_time_us & 0xFF,
    )


class TeleshakeController:
    def __init__(self, port: str = "COM4", timeout: float = 0.1) -> None:
        self.port = port
        self.timeout = timeout
        self.serial_port: Optional[serial.Serial] = None

    @property
    def is_connected(self) -> bool:
        return bool(self.serial_port and self.serial_port.is_open)

    def connect(self) -> None:
        self.serial_port = serial.Serial(
            port=self.port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=False,
            dsrdtr=False,
            timeout=self.timeout,
        )
        self.serial_port.setRTS(True)
        self.serial_port.setDTR(True)
        self.serial_port.reset_input_buffer()
        self.serial_port.reset_output_buffer()

    def disconnect(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None

    def start(self, rpm: int, direction: str) -> list[Transaction]:
        if not 100 <= rpm <= 2000:
            raise ValueError("RPM must be from 100 to 2000.")
        if direction not in DIRECTION_VALUES:
            raise ValueError(f"Unsupported direction: {direction}")

        speed_bytes = speed_to_cycle_time_bytes(rpm)
        packets = [
            ("speed", build_packet(COMMAND_SET_SPEED, list(speed_bytes))),
            ("direction", build_packet(COMMAND_SET_DIRECTION, [0x00, 0x00, DIRECTION_VALUES[direction]])),
            ("apply", build_packet(COMMAND_APPLY_SETTINGS, [0x00, 0xFF, 0xFF])),
            ("start", build_packet(COMMAND_START, [0x00, 0x00, 0x00])),
        ]
        return [self.transact(label, packet) for label, packet in packets]

    def stop(self) -> Transaction:
        return self.transact("stop", build_packet(COMMAND_STOP, [0x00, 0x00, 0x00]))

    def transact(self, label: str, packet: bytes) -> Transaction:
        if not self.serial_port or not self.serial_port.is_open:
            raise RuntimeError("Serial port is not connected.")

        try:
            self.serial_port.reset_input_buffer()
        except Exception:
            pass

        self.serial_port.write(packet)
        self.serial_port.flush()
        return Transaction(label=label, tx=packet, rx=self._read_exact(6, timeout_s=0.6))

    def _read_exact(self, size: int, timeout_s: float) -> Optional[bytes]:
        if not self.serial_port or not self.serial_port.is_open:
            return None

        deadline = time.time() + timeout_s
        response = bytearray()
        while len(response) < size and time.time() < deadline:
            chunk = self.serial_port.read(size - len(response))
            if chunk:
                response.extend(chunk)
            else:
                time.sleep(0.01)
        return bytes(response) if response else None
