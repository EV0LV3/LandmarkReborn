"""Minimal pcap / pcapng reader yielding raw link-layer frames."""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

_PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1": "<",  # microsecond, little-endian
    b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<",  # nanosecond
    b"\xa1\xb2\x3c\x4d": ">",
}
_PCAPNG_SHB = 0x0A0D0D0A


class CaptureFormatError(Exception):
    pass


def read_frames(path: str | Path) -> Iterator[bytes]:
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) < 4:
        raise CaptureFormatError("File is too small to be a capture.")
    if data[:4] in _PCAP_MAGICS:
        yield from _read_pcap(data, _PCAP_MAGICS[data[:4]])
    elif struct.unpack("<I", data[:4])[0] == _PCAPNG_SHB:
        yield from _read_pcapng(data)
    else:
        raise CaptureFormatError("Unrecognised capture format (expected pcap or pcapng).")


def _read_pcap(data: bytes, endian: str) -> Iterator[bytes]:
    offset = 24
    record = struct.Struct(endian + "IIII")
    while offset + record.size <= len(data):
        _, _, incl_len, _ = record.unpack_from(data, offset)
        offset += record.size
        yield data[offset:offset + incl_len]
        offset += incl_len


def _read_pcapng(data: bytes) -> Iterator[bytes]:
    offset = 0
    endian = "<"
    while offset + 12 <= len(data):
        block_type = struct.unpack_from(endian + "I", data, offset)[0]
        if block_type == _PCAPNG_SHB:
            # The byte-order magic decides the endianness of this section.
            endian = "<" if data[offset + 8:offset + 12] == b"\x4d\x3c\x2b\x1a" else ">"
        block_length = struct.unpack_from(endian + "I", data, offset + 4)[0]
        if block_length < 12:
            raise CaptureFormatError(f"Invalid pcapng block length {block_length} at offset {offset}.")
        body = data[offset + 8:offset + block_length - 4]

        if block_type == 0x00000006:  # Enhanced Packet Block
            captured = struct.unpack_from(endian + "I", body, 12)[0]
            yield body[20:20 + captured]
        elif block_type == 0x00000003:  # Simple Packet Block
            original = struct.unpack_from(endian + "I", body, 0)[0]
            yield body[4:4 + min(original, len(body) - 4)]
        elif block_type == 0x00000002:  # Obsolete Packet Block
            captured = struct.unpack_from(endian + "I", body, 12)[0]
            yield body[20:20 + captured]

        offset += block_length
