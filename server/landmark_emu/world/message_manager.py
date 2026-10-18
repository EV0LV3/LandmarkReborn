"""Zone message/handler registry, keyed by client protocol."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..gateway.messages import ClientProtocol
from ..shared.network.message import Readable, Writable
from .opcodes import ZoneMessageOpcode

log = logging.getLogger("ZoneMessageManager")

ZoneHandler = Callable[[object, Readable], None]

_SUPPORTED_PROTOCOLS = (int(ClientProtocol.LandmarkClientProtocol_709),)

# opcode -> (factory, prepend size)
_factories: dict[int, tuple[type[Readable], bool]] = {}
_opcodes: dict[type, ZoneMessageOpcode] = {}
_handlers: dict[int, dict[int, ZoneHandler]] = {p: {} for p in _SUPPORTED_PROTOCOLS}


def zone_message(
    opcode: ZoneMessageOpcode,
    version: ClientProtocol = ClientProtocol.ClientProtocol_ALL,
    prepend_size: bool = False,
):
    """Register a zone message. ``prepend_size`` prefixes the encoded body with its uint32 length."""

    def decorator(cls):
        if issubclass(cls, Readable):
            _factories[int(opcode)] = (cls, prepend_size)
        _opcodes[cls] = opcode
        return cls

    return decorator


def zone_handler(opcode: ZoneMessageOpcode, version: ClientProtocol = ClientProtocol.ClientProtocol_ALL):
    def decorator(fn: ZoneHandler) -> ZoneHandler:
        for protocol, table in _handlers.items():
            if (int(version) & protocol) == protocol:
                table[int(opcode)] = fn
        return fn

    return decorator


def initialise() -> None:
    from . import handlers, messages, send_self  # noqa: F401

    log.info("Initialised %d Zone message(s).", len(_opcodes))
    log.info("Initialised %d Zone message handler(s).", sum(len(h) for h in _handlers.values()))


def get_opcode(message: Writable) -> ZoneMessageOpcode | None:
    return _opcodes.get(type(message))


def get_zone_message(opcode: int, version: int = 0) -> Readable | None:
    entry = _factories.get(opcode)
    return entry[0]() if entry else None


def get_handler(opcode: int, version: int) -> ZoneHandler | None:
    table = _handlers.get(version)
    return table.get(opcode) if table else None


def has_prepended_size(opcode: int) -> bool:
    # Only readable messages are in the factory table; matches the original lookup.
    entry = _factories.get(opcode)
    return entry[1] if entry else False
