"""Base types for game-layer messages and helpers shared by the servers."""

from __future__ import annotations

import base64
import dataclasses
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .packet_io import GamePacketReader, GamePacketWriter


class Readable:
    """A message the server can parse (client -> server)."""

    def read(self, reader: GamePacketReader) -> None:
        raise NotImplementedError


class Writable:
    """A message the server can send (server -> client)."""

    def write(self, writer: GamePacketWriter) -> None:
        raise NotImplementedError


def serialize(message: Writable) -> bytes:
    writer = GamePacketWriter()
    message.write(writer)
    return writer.to_bytes()


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in dataclasses.fields(value) if not f.name.startswith("_")}
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def to_json(message: Any) -> str:
    """Indented JSON of a message for logging (like ``JsonConvert.SerializeObject``)."""
    return json.dumps(_jsonable(message), indent=2, default=str)


@dataclass
class CharacterModelInfo(Readable, Writable):
    customisations: list[tuple[int, int, int]] = field(default_factory=list)
    skin_id: int = 0
    unknown1: str = ""
    race: int = 1
    gender: int = 1

    def get_size(self) -> int:
        return 4 + 12 * len(self.customisations) + 4 + 4 + len(self.unknown1.encode("utf-8")) + 4 + 4

    def read(self, reader):
        count = reader.read_uint()
        for _ in range(count):
            self.customisations.append((reader.read_uint(), reader.read_uint(), reader.read_uint()))
        self.skin_id = reader.read_uint()
        self.unknown1 = reader.read_string()
        self.race = reader.read_uint()
        self.gender = reader.read_uint()

    def write(self, writer):
        writer.write_uint(len(self.customisations))
        for slot, option, tint in self.customisations:
            writer.write_uint(slot)
            writer.write_uint(option)
            writer.write_uint(tint)
        writer.write_uint(self.skin_id)
        writer.write_string(self.unknown1)
        writer.write_uint(self.race)
        writer.write_uint(self.gender)
