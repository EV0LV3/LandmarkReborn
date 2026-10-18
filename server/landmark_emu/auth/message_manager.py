"""Auth message/handler registry, keyed by login protocol version."""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import IntEnum

from ..shared.network.message import Readable, Writable
from ..shared.network.protocol import ProtocolVersion

log = logging.getLogger("AuthMessageManager")

_LOGIN_VERSIONS = (ProtocolVersion.LoginUdp_9, ProtocolVersion.LoginUdp_10)


class AuthMessageOpcode(IntEnum):
    LoginRequest = 0x01
    LoginReply = 0x02
    Logout = 0x03
    ForceDisconnect = 0x04
    CharacterCreateRequest = 0x05
    CharacterCreateReply = 0x06
    CharacterLoginRequest = 0x07
    CharacterLoginReply = 0x08
    CharacterDeleteRequest = 0x09
    CharacterDeleteReply = 0x0A
    CharacterSelectInfoRequest = 0x0B
    CharacterSelectInfoReply = 0x0C
    ServerListRequest = 0x0D
    ServerListReply = 0x0E
    ServerUpdate = 0x0F
    TunnelPacketClientToServer = 0x10
    TunnelPacketServerToClient = 0x11


AuthHandler = Callable[[object, Readable], None]

_factories: dict[ProtocolVersion, dict[int, type[Readable]]] = {v: {} for v in _LOGIN_VERSIONS}
_opcodes: dict[type, AuthMessageOpcode] = {}
_handlers: dict[ProtocolVersion, dict[int, AuthHandler]] = {v: {} for v in _LOGIN_VERSIONS}


def auth_message(opcode: AuthMessageOpcode, version: ProtocolVersion):
    """Register a message class for an opcode and login protocol version(s)."""

    def decorator(cls):
        if issubclass(cls, Readable):
            for v in _LOGIN_VERSIONS:
                if version & v:
                    if opcode in _factories[v]:
                        raise ValueError(f"Duplicate auth message for {opcode!r} / {v!r}")
                    _factories[v][int(opcode)] = cls
        _opcodes[cls] = opcode
        return cls

    return decorator


def auth_handler(opcode: AuthMessageOpcode, version: ProtocolVersion = ProtocolVersion.LOGIN_ALL):
    """Register a handler ``fn(session, message)`` for an opcode and login protocol version(s)."""

    def decorator(fn: AuthHandler) -> AuthHandler:
        for v in _LOGIN_VERSIONS:
            if (version & v) == v:
                if opcode in _handlers[v]:
                    raise ValueError(f"Duplicate auth handler for {opcode!r} / {v!r}")
                _handlers[v][int(opcode)] = fn
        return fn

    return decorator


def initialise() -> None:
    # Importing the modules registers their messages and handlers.
    from . import handlers, messages  # noqa: F401

    log.info("Initialised %d Auth message(s).", len(_opcodes))
    log.info("Initialised %d Auth message handler(s).", sum(len(h) for h in _handlers.values()))


def get_opcode(message: Writable) -> AuthMessageOpcode | None:
    return _opcodes.get(type(message))


def get_auth_message(opcode: int, version: ProtocolVersion) -> Readable | None:
    table = _factories[ProtocolVersion.LoginUdp_10] if version & ProtocolVersion.LoginUdp_10 else _factories[ProtocolVersion.LoginUdp_9]
    factory = table.get(opcode)
    return factory() if factory else None


def get_handler(opcode: int, version: ProtocolVersion) -> AuthHandler | None:
    table = _handlers.get(version)
    return table.get(opcode) if table else None
