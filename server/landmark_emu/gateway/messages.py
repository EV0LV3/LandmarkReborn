"""Gateway (ExternalGatewayApi_3) messages and registry."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from ..shared.network.message import Readable, Writable
from ..shared.network.protocol import ProtocolVersion

log = logging.getLogger("GatewayMessageManager")


class GatewayMessageOpcode(IntEnum):
    LoginRequest = 0x01
    LoginReply = 0x02
    Logout = 0x03
    ForceDisconnect = 0x04
    TunnelPacketToExternalConnection = 0x05
    TunnelPacketFromExternalConnection = 0x06
    ChannelIsRoutable = 0x07
    ConnectionIsNotRoutable = 0x08


class Channel(IntEnum):
    Zone = 0
    World = 1
    PositionUpdate = 2
    Voxel = 3


class ClientProtocol(IntEnum):
    # ClientProtocol_630 = 630
    LandmarkClientProtocol_709 = 709
    ClientProtocol_ALL = 709  # Alias, as in the original.


GatewayHandler = Callable[[object, Readable], None]

_factories: dict[int, type[Readable]] = {}
_opcodes: dict[type, GatewayMessageOpcode] = {}
_handlers: dict[ProtocolVersion, dict[int, GatewayHandler]] = {ProtocolVersion.ExternalGatewayApi_3: {}}


def gateway_message(opcode: GatewayMessageOpcode, version: ProtocolVersion = ProtocolVersion.ExternalGatewayApi_3):
    def decorator(cls):
        if issubclass(cls, Readable):
            _factories[int(opcode)] = cls
        _opcodes[cls] = opcode
        return cls

    return decorator


def gateway_handler(opcode: GatewayMessageOpcode, version: ProtocolVersion = ProtocolVersion.ExternalGatewayApi_3):
    def decorator(fn: GatewayHandler) -> GatewayHandler:
        for v, table in _handlers.items():
            if (version & v) == v:
                table[int(opcode)] = fn
        return fn

    return decorator


def initialise() -> None:
    from . import session  # noqa: F401  (registers the login handler)

    log.info("Initialised %d Gateway message(s).", len(_opcodes))
    log.info("Initialised %d Gateway message handler(s).", sum(len(h) for h in _handlers.values()))


def get_opcode(message: Writable) -> GatewayMessageOpcode | None:
    return _opcodes.get(type(message))


def get_gateway_message(opcode: int, version: ProtocolVersion) -> Readable | None:
    factory = _factories.get(opcode)
    return factory() if factory else None


def get_handler(opcode: int, version: ProtocolVersion) -> GatewayHandler | None:
    table = _handlers.get(version)
    return table.get(opcode) if table else None


@gateway_message(GatewayMessageOpcode.LoginRequest)
@dataclass
class LoginRequest(Readable):
    character_id: int = 0
    server_ticket: str = ""
    client_protocol: str = ""
    client_build: str = ""

    def read(self, reader):
        self.character_id = reader.read_ulong()
        self.server_ticket = reader.read_string()
        self.client_protocol = reader.read_string()
        self.client_build = reader.read_string()


@gateway_message(GatewayMessageOpcode.LoginReply)
@dataclass
class LoginReply(Writable):
    logged_in: bool = False

    def write(self, writer):
        writer.write_bool(self.logged_in)


@gateway_message(GatewayMessageOpcode.ForceDisconnect)
@dataclass
class ForceDisconnect(Writable):
    reason: int = 0

    def write(self, writer):
        writer.write_uint(self.reason)


@gateway_message(GatewayMessageOpcode.TunnelPacketToExternalConnection)
@dataclass
class TunnelPacketToExternalConnection(Writable):
    channel: int = 0
    data: bytes = b""

    def write(self, writer):
        writer.write_bytes(self.data)
