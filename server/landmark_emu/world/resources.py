"""Captured packet dumps replayed to the client. Loaded once and shared by all sessions."""

from __future__ import annotations

import struct
import zlib
from functools import cache

from .. import RESOURCES_DIR

PACKET_DUMPS_DIR = RESOURCES_DIR / "world" / "PacketDumps"


@cache
def packet_dump(name: str) -> bytes:
    return (PACKET_DUMPS_DIR / name).read_bytes()


def send_self_dump() -> bytes:
    return packet_dump("SendSelf.bin")


def terrain_manifest_dump() -> bytes:
    return packet_dump("TerrainCellManifest.bin")


@cache
def empty_terrain_manifest() -> bytes:
    """TerrainCellModifiedCellManifest payload (opcode excluded) listing no modified cells.

    Layout, as in the captured dump: ushort 0, uint blob size, then the blob: magic A1 B2 C3 D4,
    big-endian uncompressed size and zlib data. The data is 2 x 4 lists, each a uint count of
    (ulong cell id, uint value, byte) entries (Landmark64.exe 0.589, 0x143EE8810).
    """
    data = bytes(4 * 8)
    blob = b"\xa1\xb2\xc3\xd4" + struct.pack(">I", len(data)) + zlib.compress(data, 9)
    return struct.pack("<HI", 0, len(blob)) + blob
