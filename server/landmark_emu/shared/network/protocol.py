"""SOE reliable-UDP protocol layer: opcodes, options, messages and the protocol packet."""

from __future__ import annotations

import logging
import zlib
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag

from ..logs import TRACE, hex_dump
from .packet_io import ProtocolPacketReader, ProtocolPacketWriter

log = logging.getLogger("MultiPacket")


class ProtocolMessageOpcode(IntEnum):
    SessionRequest = 0x01
    SessionReply = 0x02
    MultiPacket = 0x03
    Disconnect = 0x05
    Ping = 0x06
    NetStatusRequest = 0x07
    NetStatusReply = 0x08
    Data = 0x09
    DataFragment = 0x0D
    OutOfOrder = 0x11
    Ack = 0x15
    FatalError = 0x1D
    FatalErrorReply = 0x1E


class ProtocolVersion(IntFlag):
    NONE = 0
    LoginUdp_9 = 0x01
    LoginUdp_10 = 0x02
    LOGIN_ALL = LoginUdp_9 | LoginUdp_10
    ExternalGatewayApi_3 = 0x04


@dataclass
class PacketOptions:
    compression: bool = False
    is_subpacket: bool = False
    was_out_of_order: bool = False
    sequence: int = 0
    is_priority: bool = False


def opcode_name(enum_type: type[IntEnum], value: int) -> str:
    """Name of an enum member, or the raw number for values the enum does not define."""
    try:
        return enum_type(value).name
    except ValueError:
        return str(value)


class ProtocolMessage:
    """Base for protocol-layer messages (IProtocol)."""

    OPCODE: ProtocolMessageOpcode
    USE_ENCRYPTION: bool  # When set, a CRC is appended on send.

    def read(self, reader: ProtocolPacketReader, options: PacketOptions) -> None:
        raise NotImplementedError

    def write(self, writer: ProtocolPacketWriter, options: PacketOptions) -> None:
        raise NotImplementedError


_protocol_factories: dict[int, type[ProtocolMessage]] = {}


def protocol_message(opcode: ProtocolMessageOpcode, use_encryption: bool):
    def decorator(cls: type[ProtocolMessage]) -> type[ProtocolMessage]:
        cls.OPCODE = opcode
        cls.USE_ENCRYPTION = use_encryption
        _protocol_factories[int(opcode)] = cls
        return cls

    return decorator


def get_protocol_message(opcode: int) -> ProtocolMessage | None:
    factory = _protocol_factories.get(opcode)
    return factory() if factory else None


def protocol_message_count() -> int:
    return len(_protocol_factories)


@protocol_message(ProtocolMessageOpcode.Ack, use_encryption=True)
@dataclass
class Ack(ProtocolMessage):
    compression_flag: int = 0
    sequence: int = 0

    def read(self, reader, options):
        if not options.is_subpacket:
            self.compression_flag = reader.read_byte()
        self.sequence = reader.read_ushort()

    def write(self, writer, options):
        if not options.is_subpacket:
            writer.write_byte(self.compression_flag)
        writer.write_ushort(self.sequence)


@protocol_message(ProtocolMessageOpcode.OutOfOrder, use_encryption=True)
@dataclass
class OutOfOrder(ProtocolMessage):
    compression_flag: int = 0
    sequence: int = 0

    def read(self, reader, options):
        if not options.is_subpacket:
            self.compression_flag = reader.read_byte()
        self.sequence = reader.read_ushort()

    def write(self, writer, options):
        if not options.is_subpacket:
            writer.write_byte(self.compression_flag)
        writer.write_ushort(self.sequence)


@dataclass
class _DataBase(ProtocolMessage):
    sequence: int = 0
    data: bytes = b""
    crc: int = 0
    packet_options: PacketOptions | None = None

    def read(self, reader, options):
        data_end = 0 if options.is_subpacket else 2
        if options.compression and not options.is_subpacket:
            reader.read_byte()
        self.sequence = reader.read_ushort()
        self.data = reader.read_bytes(reader.bytes_remaining - data_end)
        if not options.is_subpacket:
            self.crc = reader.read_ushort()
        self.packet_options = options

    def write(self, writer, options):
        if options.compression and not options.is_subpacket:
            writer.write_byte(0)
        writer.write_ushort(self.sequence)
        writer.write_bytes(self.data)


@protocol_message(ProtocolMessageOpcode.Data, use_encryption=True)
@dataclass
class DataWhole(_DataBase):
    pass


@protocol_message(ProtocolMessageOpcode.DataFragment, use_encryption=True)
@dataclass
class DataFragment(_DataBase):
    pass


@protocol_message(ProtocolMessageOpcode.Disconnect, use_encryption=True)
@dataclass
class Disconnect(ProtocolMessage):
    def read(self, reader, options):
        pass

    def write(self, writer, options):
        pass


@protocol_message(ProtocolMessageOpcode.Ping, use_encryption=True)
@dataclass
class Ping(ProtocolMessage):
    def read(self, reader, options):
        pass

    def write(self, writer, options):
        pass


@protocol_message(ProtocolMessageOpcode.SessionReply, use_encryption=True)
@dataclass
class SessionReply(ProtocolMessage):
    session_id: int = 0
    crc_seed: int = 0
    crc_length: int = 0
    compression: int = 0
    udp_length: int = 0
    unknown0: int = 3

    def read(self, reader, options):
        self.session_id = reader.read_uint()
        self.crc_seed = reader.read_uint()
        self.crc_length = reader.read_byte()
        self.compression = reader.read_ushort()
        self.udp_length = reader.read_uint()
        self.unknown0 = reader.read_uint()

    def write(self, writer, options):
        writer.write_uint(self.session_id)
        writer.write_uint(self.crc_seed)
        writer.write_byte(self.crc_length)
        writer.write_ushort(self.compression)
        writer.write_uint(self.udp_length)
        writer.write_uint(self.unknown0)


@protocol_message(ProtocolMessageOpcode.SessionRequest, use_encryption=False)
@dataclass
class SessionRequest(ProtocolMessage):
    crc_length: int = 0
    session_id: int = 0
    udp_length: int = 0
    protocol: str = ""

    def read(self, reader, options):
        self.crc_length = reader.read_uint()
        self.session_id = reader.read_uint()
        self.udp_length = reader.read_uint()
        self.protocol = reader.read_null_terminated_string()

    def write(self, writer, options):
        # Only ever sent by the client; kept for tooling/tests.
        writer.write_uint(self.crc_length)
        writer.write_uint(self.session_id)
        writer.write_uint(self.udp_length)
        writer.write_null_terminated_string(self.protocol)


def read_variable_length(reader: ProtocolPacketReader) -> int:
    """Length prefix used by multi-packets and multi-channel data: 1, 3 or 7 bytes."""
    data = reader.get_remaining_data()
    length = reader.read_byte()
    if length == 0xFF:
        if data[1] == 0xFF and data[2] == 0xFF:
            reader.read_ushort()
            length = reader.read_uint()
        else:
            length = reader.read_ushort()
    return length


def read_length_prefixed_chunk(reader: ProtocolPacketReader) -> bytes:
    next_length = read_variable_length(reader)
    if next_length > reader.bytes_remaining:
        # The original truncates the remaining count to a byte here.
        next_length = reader.bytes_remaining & 0xFF
    return reader.read_bytes(next_length)


@protocol_message(ProtocolMessageOpcode.MultiPacket, use_encryption=True)
@dataclass
class MultiPacket(ProtocolMessage):
    packets: list[ProtocolPacket] = field(default_factory=list)

    def read(self, reader, options):
        data = reader.get_remaining_data()
        if options.compression:
            compression = reader.read_byte()
            if compression > 0 and len(data) > 2 and data[1] == 0x78 and data[2] == 0x9C:
                data = reader.read_bytes(len(data) - 3)
                reader = ProtocolPacketReader(zlib.decompress(data))
                if log.isEnabledFor(TRACE):
                    log.log(TRACE, "Decompressed: %s", hex_dump(reader.get_remaining_data()))

        while reader.bytes_remaining > 2:
            before = reader.position
            try:
                self._read_packet(reader, options)
            except Exception:
                log.error("%s : %s", hex_dump(data), hex_dump(reader.get_remaining_data()))
                if reader.position == before:
                    break  # A failed read that made no progress would otherwise spin forever.

    def _read_packet(self, reader: ProtocolPacketReader, options: PacketOptions) -> None:
        chunk = read_length_prefixed_chunk(reader)
        self.packets.append(
            ProtocolPacket.from_bytes(chunk, PacketOptions(is_subpacket=True, compression=options.compression))
        )

    def write(self, writer, options):
        raise NotImplementedError


class ProtocolPacket:
    """A raw protocol-layer packet: big-endian ushort opcode followed by the payload."""

    __slots__ = ("opcode", "data", "size", "use_encryption", "packet_options", "ignore")

    def __init__(self, opcode: int, data: bytes, use_encryption: bool = False, options: PacketOptions | None = None):
        self.opcode = opcode
        self.data = data
        self.size = len(data)
        self.use_encryption = use_encryption
        self.packet_options = options
        self.ignore = False

    @classmethod
    def from_bytes(cls, data: bytes, options: PacketOptions | None = None) -> ProtocolPacket:
        reader = ProtocolPacketReader(data)
        opcode = reader.read_ushort()
        return cls(opcode, reader.read_bytes(reader.bytes_remaining), options=options)

    @classmethod
    def from_message(cls, message: ProtocolMessage, options: PacketOptions) -> ProtocolPacket:
        writer = ProtocolPacketWriter()
        message.write(writer, options)
        return cls(int(message.OPCODE), writer.to_bytes(), use_encryption=message.USE_ENCRYPTION)
