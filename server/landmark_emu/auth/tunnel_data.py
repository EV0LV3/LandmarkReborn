"""Payloads carried inside Auth tunnel packets."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from ..shared.network.packet_io import GamePacketReader, GamePacketWriter


class TunnelDataType(IntEnum):
    NameValidationRequest = 0x01
    NameValidationReply = 0x02
    ServerQueue = 0x04
    LoginInit = 0x06
    Unknown7 = 0x07  # Presumed to be a login MOTD or an error string.
    ClaimData = 0x09
    ArtData = 0x0A


class NameValidationResult(IntEnum):
    Fail = 0
    Success = 1
    NameTaken = 2
    NameInvalid = 3
    NameNaughty = 4
    NameUnavailable = 5


def _str_size(value: str) -> int:
    return 4 + len(value.encode("utf-8"))


class TunnelData:
    TYPE: TunnelDataType

    def read(self, reader: GamePacketReader) -> None:
        raise NotImplementedError

    def write(self, writer: GamePacketWriter) -> None:
        raise NotImplementedError

    def get_size(self) -> int:
        raise NotImplementedError


_tunnel_data_types: dict[int, type[TunnelData]] = {}


def tunnel_data(data_type: TunnelDataType):
    def decorator(cls):
        cls.TYPE = data_type
        _tunnel_data_types[int(data_type)] = cls
        return cls

    return decorator


def new_tunnel_data(data_type: int) -> TunnelData | None:
    factory = _tunnel_data_types.get(data_type)
    return factory() if factory else None


@tunnel_data(TunnelDataType.NameValidationRequest)
@dataclass
class NameValidationRequest(TunnelData):
    first_name: str = ""
    last_name: str = ""

    def get_size(self):
        return _str_size(self.first_name) + _str_size(self.last_name)

    def read(self, reader):
        self.first_name = reader.read_string()
        self.last_name = reader.read_string()

    def write(self, writer):
        pass


@tunnel_data(TunnelDataType.NameValidationReply)
@dataclass
class NameValidationReply(TunnelData):
    result: NameValidationResult = NameValidationResult.Fail
    first_name: str = ""
    last_name: str = ""

    def get_size(self):
        return 4 + _str_size(self.first_name) + _str_size(self.last_name)

    def read(self, reader):
        pass

    def write(self, writer):
        writer.write_string(self.first_name)
        writer.write_string(self.last_name)
        writer.write_uint(self.result)


@tunnel_data(TunnelDataType.LoginInit)
@dataclass
class LoginInit(TunnelData):
    def get_size(self):
        return 0

    def read(self, reader):
        pass

    def write(self, writer):
        pass


@tunnel_data(TunnelDataType.Unknown7)
@dataclass
class Unknown7(TunnelData):
    string: str = ""

    def get_size(self):
        return _str_size(self.string)

    def read(self, reader):
        self.string = reader.read_string()

    def write(self, writer):
        writer.write_string(self.string)


@dataclass
class Claim:
    unknown0: int = 0  # Probably ServerId
    unknown1: int = 0  # Probably ClaimId
    unknown2: int = 0  # Probably paid time remaining
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: bool = False
    unknown7: str = ""
    unknown8: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # Probably position
    unknown9: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # Probably rotation
    unknown10: int = 0
    unknown11: int = 0

    def get_size(self):
        return 8 + 8 + 8 + 4 + 4 + 4 + 1 + _str_size(self.unknown7) + 3 * 8 + 3 * 8 + 4 + 4

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unknown1 = reader.read_ulong()
        self.unknown2 = reader.read_ulong()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_bool()
        self.unknown7 = reader.read_string()
        self.unknown8 = [reader.read_double() for _ in range(3)]
        self.unknown9 = [reader.read_double() for _ in range(3)]
        self.unknown10 = reader.read_uint()
        self.unknown11 = reader.read_uint()

    def write(self, writer):
        writer.write_ulong(self.unknown0)
        writer.write_ulong(self.unknown1)
        writer.write_ulong(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_bool(self.unknown6)
        writer.write_string(self.unknown7)
        for value in self.unknown8:
            writer.write_double(value)
        for value in self.unknown9:
            writer.write_double(value)
        writer.write_uint(self.unknown10)
        writer.write_uint(self.unknown11)


@tunnel_data(TunnelDataType.ClaimData)
@dataclass
class ClaimData(TunnelData):
    claims: list[Claim] = field(default_factory=list)

    def get_size(self):
        return 4 + sum(c.get_size() for c in self.claims)

    def read(self, reader):
        # The original only reads the count, creating empty claims.
        count = reader.read_uint()
        self.claims = [Claim() for _ in range(count)]

    def write(self, writer):
        writer.write_uint(len(self.claims))
        for claim in self.claims:
            claim.write(writer)


# --- ArtData -------------------------------------------------------------------------------


@dataclass
class _IntString:  # UnknownStruct_142C36820
    unknown0: int = 0
    unknown1: str = ""

    def get_size(self):
        return 4 + _str_size(self.unknown1)

    def read(self, reader):
        self.unknown0 = reader.read_int()
        self.unknown1 = reader.read_string()

    def write(self, writer):
        writer.write_int(self.unknown0)
        writer.write_string(self.unknown1)


@dataclass
class _IntPair:  # UnknownStruct_142C351D0 / ArtTintOverrideEntry
    unknown0: int = 0
    unknown1: int = 0

    def get_size(self):
        return 8

    def read(self, reader):
        self.unknown0 = reader.read_int()
        self.unknown1 = reader.read_int()

    def write(self, writer):
        writer.write_int(self.unknown0)
        writer.write_int(self.unknown1)


@dataclass
class ArtTintOverrideGroupEntry:
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: list[_IntPair] = field(default_factory=list)

    def get_size(self):
        return 4 + 4 + 4 + 4 + sum(e.get_size() for e in self.unknown3)

    def read(self, reader):
        # The original reads Unknown2 twice and never sets Unknown1; preserved.
        self.unknown0 = reader.read_int()
        self.unknown2 = reader.read_int()
        self.unknown2 = reader.read_int()
        count = reader.read_uint()
        for _ in range(count):
            entry = _IntPair()
            entry.read(reader)
            self.unknown3.append(entry)

    def write(self, writer):
        writer.write_int(self.unknown0)
        writer.write_int(self.unknown1)
        writer.write_int(self.unknown2)
        writer.write_uint(len(self.unknown3))
        for entry in self.unknown3:
            entry.write(writer)


@dataclass
class _LongFourInts:  # UnknownStruct_142C3FE00
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0

    def get_size(self):
        return 8 + 4 + 4 + 4 + 4

    def read(self, reader):
        self.unknown0 = reader.read_long()
        self.unknown1 = reader.read_int()
        self.unknown2 = reader.read_int()
        self.unknown3 = reader.read_int()
        self.unknown4 = reader.read_int()

    def write(self, writer):
        writer.write_long(self.unknown0)
        writer.write_int(self.unknown1)
        writer.write_int(self.unknown2)
        writer.write_int(self.unknown3)
        writer.write_int(self.unknown4)


@dataclass
class _String:  # UnknownStruct_142C3BAC0
    unknown0: str = ""

    def get_size(self):
        return _str_size(self.unknown0)

    def read(self, reader):
        self.unknown0 = reader.read_string()

    def write(self, writer):
        writer.write_string(self.unknown0)


@dataclass
class TintSemanticEntry:
    semantic_name: str = ""
    unknown1: int = 0  # Id?
    unknown2: int = 0  # TypeId
    unknown3: int = 0
    edit_type: str = ""
    unknown4: int = 0
    r: int = 0
    g: int = 0
    b: int = 0
    a: int = 0

    def get_size(self):
        return _str_size(self.semantic_name) + 12 + _str_size(self.edit_type) + 20

    def read(self, reader):
        self.semantic_name = reader.read_string()
        self.unknown1 = reader.read_int()
        self.unknown2 = reader.read_int()
        self.unknown3 = reader.read_int()
        self.edit_type = reader.read_string()
        self.unknown4 = reader.read_int()
        self.r = reader.read_int()
        self.g = reader.read_int()
        self.b = reader.read_int()
        self.a = reader.read_int()

    def write(self, writer):
        writer.write_string(self.semantic_name)
        writer.write_int(self.unknown1)
        writer.write_int(self.unknown2)
        writer.write_int(self.unknown3)
        writer.write_string(self.edit_type)
        writer.write_int(self.unknown4)
        writer.write_int(self.r)
        writer.write_int(self.g)
        writer.write_int(self.b)
        writer.write_int(self.a)


@dataclass
class TintSemanticGroupEntry:
    id: int = 0
    alias_name: str = ""
    semantic_group: str = ""
    art_tints: list[TintSemanticEntry] = field(default_factory=list)
    unknown3: int = 0
    unknown4: int = 0

    def get_size(self):
        return 4 + _str_size(self.alias_name) + _str_size(self.semantic_group) + 4 + 4 + 4 + sum(
            t.get_size() for t in self.art_tints
        )

    def read(self, reader):
        self.id = reader.read_int()
        self.alias_name = reader.read_string()
        self.semantic_group = reader.read_string()
        count = reader.read_uint()
        for _ in range(count):
            tint = TintSemanticEntry()
            tint.read(reader)
            self.art_tints.append(tint)
        self.unknown3 = reader.read_int()
        self.unknown4 = reader.read_int()

    def write(self, writer):
        writer.write_int(self.id)
        writer.write_string(self.alias_name)
        writer.write_string(self.semantic_group)
        writer.write_uint(len(self.art_tints))
        for tint in self.art_tints:
            tint.write(writer)
        writer.write_int(self.unknown3)
        writer.write_int(self.unknown4)


def _json_list(data: dict[str, Any], key: str) -> list:
    # Newtonsoft matches property names case-insensitively.
    for k, v in data.items():
        if k.lower() == key.lower():
            return v or []
    return []


def _json_get(data: dict[str, Any], key: str, default: Any = 0) -> Any:
    for k, v in data.items():
        if k.lower() == key.lower():
            return default if v is None else v
    return default


@tunnel_data(TunnelDataType.ArtData)
@dataclass
class ArtData(TunnelData):
    unknown0: list[_IntString] = field(default_factory=list)
    unknown1: list[_IntPair] = field(default_factory=list)
    art_tint_override_groups: list[ArtTintOverrideGroupEntry] = field(default_factory=list)
    unknown3: list[_LongFourInts] = field(default_factory=list)
    unknown4: list[_String] = field(default_factory=list)
    unknown5: list[_String] = field(default_factory=list)
    art_tint_groups: list[TintSemanticGroupEntry] = field(default_factory=list)
    unknown7: list[_IntPair] = field(default_factory=list)
    # The art data is static, so the encoded form is computed once and reused.
    _encoded: bytes | None = field(default=None, repr=False, compare=False)

    _SECTIONS = (
        ("unknown0", _IntString),
        ("unknown1", _IntPair),
        ("art_tint_override_groups", ArtTintOverrideGroupEntry),
        ("unknown3", _LongFourInts),
        ("unknown4", _String),
        ("unknown5", _String),
        ("art_tint_groups", TintSemanticGroupEntry),
        ("unknown7", _IntPair),
    )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ArtData:
        def pairs(items):
            return [_IntPair(_json_get(i, "Unknown0"), _json_get(i, "Unknown1")) for i in items]

        return cls(
            unknown0=[_IntString(_json_get(i, "Unknown0"), _json_get(i, "Unknown1", "")) for i in _json_list(data, "Unknown0")],
            unknown1=pairs(_json_list(data, "Unknown1")),
            art_tint_override_groups=[
                ArtTintOverrideGroupEntry(
                    _json_get(i, "Unknown0"),
                    _json_get(i, "Unknown1"),
                    _json_get(i, "Unknown2"),
                    pairs(_json_list(i, "Unknown3")),
                )
                for i in _json_list(data, "ArtTintOverrideGroups")
            ],
            unknown3=[
                _LongFourInts(*(_json_get(i, f"Unknown{n}") for n in range(5))) for i in _json_list(data, "Unknown3")
            ],
            unknown4=[_String(_json_get(i, "Unknown0", "")) for i in _json_list(data, "Unknown4")],
            unknown5=[_String(_json_get(i, "Unknown0", "")) for i in _json_list(data, "Unknown5")],
            art_tint_groups=[
                TintSemanticGroupEntry(
                    id=_json_get(g, "Id"),
                    alias_name=_json_get(g, "AliasName", ""),
                    semantic_group=_json_get(g, "SemanticGroup", ""),
                    art_tints=[
                        TintSemanticEntry(
                            semantic_name=_json_get(t, "SemanticName", ""),
                            unknown1=_json_get(t, "Unknown1"),
                            unknown2=_json_get(t, "Unknown2"),
                            unknown3=_json_get(t, "Unknown3"),
                            edit_type=_json_get(t, "EditType", ""),
                            unknown4=_json_get(t, "Unknown4"),
                            r=_json_get(t, "R"),
                            g=_json_get(t, "G"),
                            b=_json_get(t, "B"),
                            a=_json_get(t, "A"),
                        )
                        for t in _json_list(g, "ArtTints")
                    ],
                    unknown3=_json_get(g, "Unknown3"),
                    unknown4=_json_get(g, "Unknown4"),
                )
                for g in _json_list(data, "ArtTintGroups")
            ],
            unknown7=pairs(_json_list(data, "Unknown7")),
        )

    def _encode(self) -> bytes:
        if self._encoded is None:
            writer = GamePacketWriter()
            for name, _ in self._SECTIONS:
                items = getattr(self, name)
                writer.write_uint(len(items))
                for item in items:
                    item.write(writer)
            self._encoded = writer.to_bytes()
        return self._encoded

    def get_size(self):
        return len(self._encode())

    def read(self, reader):
        for name, item_type in self._SECTIONS:
            items = []
            for _ in range(reader.read_uint()):
                item = item_type()
                item.read(reader)
                items.append(item)
            setattr(self, name, items)
        self._encoded = None

    def write(self, writer):
        writer.write_bytes(self._encode())
