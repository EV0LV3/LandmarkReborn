"""Binary readers/writers for the two packet layers.

``GamePacket*`` handle the little-endian game/application layer (Auth, Gateway, Zone
messages). ``ProtocolPacket*`` handle the big-endian SOE reliable-UDP protocol layer.
"""

from __future__ import annotations

import struct

_U8 = struct.Struct("B")


class PacketReadError(Exception):
    """Raised when a read runs past the end of a packet."""


def _to_unsigned(value: int, bits: int) -> int:
    return value & ((1 << bits) - 1)


def _to_signed(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


class _PacketReader:
    _endian = "<"

    def __init__(self, data: bytes | bytearray | memoryview):
        self._data = bytes(data)
        self._pos = 0
        e = self._endian
        self._u16 = struct.Struct(e + "H")
        self._i16 = struct.Struct(e + "h")
        self._u32 = struct.Struct(e + "I")
        self._i32 = struct.Struct(e + "i")
        self._f32 = struct.Struct(e + "f")
        self._u64 = struct.Struct(e + "Q")
        self._i64 = struct.Struct(e + "q")
        self._f64 = struct.Struct(e + "d")

    @property
    def total_bytes(self) -> int:
        return len(self._data)

    @property
    def bytes_remaining(self) -> int:
        return max(len(self._data) - self._pos, 0)

    @property
    def position(self) -> int:
        return self._pos

    def _take(self, count: int) -> bytes:
        end = self._pos + count
        if count < 0 or end > len(self._data):
            raise PacketReadError(
                f"Attempted to read {count} byte(s) at offset {self._pos} of a {len(self._data)} byte packet."
            )
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk

    def _unpack(self, fmt: struct.Struct):
        return fmt.unpack(self._take(fmt.size))[0]

    def reverse_byte_position(self, count: int) -> None:
        self._pos -= count

    def read_bool(self) -> bool:
        return self._take(1)[0] != 0

    def read_byte(self) -> int:
        return self._take(1)[0]

    def read_ushort(self) -> int:
        return self._unpack(self._u16)

    def read_short(self) -> int:
        return self._unpack(self._i16)

    def read_uint(self) -> int:
        return self._unpack(self._u32)

    def read_int(self) -> int:
        return self._unpack(self._i32)

    def read_single(self) -> float:
        return self._unpack(self._f32)

    def read_ulong(self) -> int:
        return self._unpack(self._u64)

    def read_long(self) -> int:
        return self._unpack(self._i64)

    def read_double(self) -> float:
        return self._unpack(self._f64)

    def read_bytes(self, length: int) -> bytes:
        return self._take(length)

    def read_string(self) -> str:
        """uint32 length prefixed UTF-8 string."""
        length = self.read_uint()
        return self._take(length).decode("utf-8", errors="replace")

    def read_null_terminated_string(self) -> str:
        end = self._data.find(b"\x00", self._pos)
        if end == -1:
            end = len(self._data)
        value = self._data[self._pos:end].decode("utf-8", errors="replace")
        # Position moves past the terminator (clamped when the terminator is missing).
        self._pos = min(end + 1, len(self._data))
        return value

    def get_remaining_data(self) -> bytes:
        return self._data[self._pos:]


class GamePacketReader(_PacketReader):
    """Little-endian reader used by Auth, Gateway and Zone messages."""

    _endian = "<"

    def read_short_length_string(self) -> str:
        length = self.read_ushort()
        value = self._take(length)
        return value.decode("utf-8", errors="replace") if length > 0 else ""

    def read_uint_2bit_length(self) -> int:
        # Mirrors the original implementation, which does not fold the first byte into the value.
        length = self._take(1)[0] & 3
        value = 0
        for i in range(length):
            value += self._take(1)[0] << ((i + 1) * 8)
        return (value >> 2) & 0xFFFFFFFF


class ProtocolPacketReader(_PacketReader):
    """Big-endian reader used by the reliable UDP protocol layer."""

    _endian = ">"


class _PacketWriter:
    _endian = "<"

    def __init__(self, output: bytearray | None = None):
        self._buf = output if output is not None else bytearray()
        e = self._endian
        self._u16 = struct.Struct(e + "H")
        self._i16 = struct.Struct(e + "h")
        self._u32 = struct.Struct(e + "I")
        self._i32 = struct.Struct(e + "i")
        self._f32 = struct.Struct(e + "f")
        self._u64 = struct.Struct(e + "Q")
        self._i64 = struct.Struct(e + "q")
        self._f64 = struct.Struct(e + "d")

    @property
    def buffer(self) -> bytearray:
        return self._buf

    def to_bytes(self) -> bytes:
        return bytes(self._buf)

    def __len__(self) -> int:
        return len(self._buf)

    def write_byte(self, value: int) -> None:
        self._buf.append(value & 0xFF)

    def write_bool(self, value: bool) -> None:
        self._buf.append(1 if value else 0)

    def write_uint(self, value: int) -> None:
        self._buf += self._u32.pack(_to_unsigned(int(value), 32))

    def write_int(self, value: int) -> None:
        self._buf += self._i32.pack(_to_signed(int(value), 32))

    def write_float(self, value: float) -> None:
        self._buf += self._f32.pack(float(value))

    def write_ulong(self, value: int) -> None:
        self._buf += self._u64.pack(_to_unsigned(int(value), 64))

    def write_long(self, value: int) -> None:
        self._buf += self._i64.pack(_to_signed(int(value), 64))

    def write_double(self, value: float) -> None:
        self._buf += self._f64.pack(float(value))

    def write_string(self, value: str) -> None:
        """uint32 length prefixed UTF-8 string."""
        encoded = value.encode("utf-8")
        self.write_uint(len(encoded))
        self._buf += encoded

    def write_null_terminated_string(self, value: str) -> None:
        self._buf += value.encode("utf-8")
        self._buf.append(0)

    def write_bytes(self, data: bytes | bytearray, length: int = 0) -> None:
        if length != 0 and length != len(data):
            raise ValueError("Length does not match data length.")
        self._buf += data


class GamePacketWriter(_PacketWriter):
    """Little-endian writer used by Auth, Gateway and Zone messages."""

    _endian = "<"

    def write_ushort(self, value: int) -> None:
        self._buf += self._u16.pack(_to_unsigned(int(value), 16))

    def write_vector4(self, value: tuple[float, float, float, float]) -> None:
        for component in value:
            self.write_float(component)

    def write_long_string(self, value: str) -> None:
        encoded = value.encode("utf-8")
        self.write_ulong(len(encoded))
        self._buf += encoded

    def write_uint_with_2bit_length(self, value: int) -> None:
        value = _to_signed(int(value) << 2, 32)
        if value > 0xFFFFFF:
            n = 3
        elif value > 0xFFFF:
            n = 2
        elif value > 0xFF:
            n = 1
        else:
            n = 0
        value |= n
        self._buf += self._i32.pack(_to_signed(value, 32))[: n + 1]


class ProtocolPacketWriter(_PacketWriter):
    """Big-endian writer used by the reliable UDP protocol layer."""

    _endian = ">"

    def write_ushort(self, value: int) -> None:
        self._buf += self._u16.pack(_to_unsigned(int(value), 16))

    def write_short(self, value: int) -> None:
        self._buf += self._i16.pack(_to_signed(int(value), 16))

    def write_short_length_string(self, value: str) -> None:
        # The original writes the character count as a float; kept for wire compatibility.
        self.write_float(float(len(value) & 0xFFFF))
        self._buf += value.encode("utf-8")
