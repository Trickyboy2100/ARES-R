"""Inspire/因时 gripper serial adapter."""

import os
import struct
from typing import Dict
from ..interfaces import Gripper
from ..models import DeviceState

try:
    import serial
except ImportError:  # reported clearly when this adapter is selected
    serial = None


class SerialGripper(Gripper):
    def __init__(self, name: str, config: Dict[str, object]) -> None:
        self.name = name
        self.port = str(config["port"])
        self.baudrate = int(config.get("baudrate", 115200))
        self.device_id = int(config.get("device_id", 1))
        self.min_position = int(config.get("min_position", 0))
        self.max_position = int(config.get("max_position", 1000))
        self._last_position = None

    @staticmethod
    def _checksum(data: bytes) -> int:
        return sum(data) & 0xFF

    def _frame(self, command: int, data: bytes = b"") -> bytes:
        body = bytes([self.device_id, len(data) + 1, command]) + data
        return bytes([0xEB, 0x90]) + body + bytes([self._checksum(body)])

    def _exchange(self, frame: bytes, response_length: int) -> bytes:
        if serial is None:
            raise RuntimeError("pyserial is required; activate the dope3.8 environment")
        try:
            with serial.Serial(self.port, self.baudrate, timeout=1.0) as stream:
                stream.reset_input_buffer()
                stream.write(frame)
                response = stream.read(response_length)
        except PermissionError as exc:
            raise RuntimeError("permission denied for %s; user must belong to dialout" % self.port) from exc
        if len(response) != response_length:
            raise RuntimeError("%s gripper response length %d, expected %d" % (self.name, len(response), response_length))
        return response

    def move_to(self, position: int) -> None:
        if position < self.min_position or position > self.max_position:
            raise ValueError("position must be between %d and %d" % (self.min_position, self.max_position))
        self._exchange(self._frame(0x54, struct.pack("<H", position)), 7)

    def position(self) -> int:
        response = self._exchange(self._frame(0xD9), 8)
        self._last_position = (response[-2] << 8) | response[-3]
        return self._last_position

    def open(self) -> None:
        self.move_to(self.max_position)

    def close(self) -> None:
        self.move_to(self.min_position)

    def has_object(self) -> bool:
        return self.position() > self.min_position

    def stop(self) -> None:
        self._exchange(self._frame(0x16), 6)

    def state(self) -> DeviceState:
        exists = os.path.exists(self.port)
        accessible = exists and os.access(self.port, os.R_OK | os.W_OK)
        detail = "%s; %s" % (self.name, self.port)
        if self._last_position is None:
            detail += "; position=not read"
        else:
            detail += "; position=%d" % self._last_position
        if exists and not accessible: detail += "; permission denied"
        return DeviceState(exists, accessible and serial is not None, detail)
