from __future__ import annotations

import logging
from collections import deque

from ..shared.database.models import AccountModel, CharacterModel
from ..shared.logs import hex_dump
from ..shared.network.data_stream import InvalidPacketValueException
from ..shared.network.message import Writable
from ..shared.network.packet_io import GamePacketReader, GamePacketWriter
from ..shared.network.protocol import opcode_name
from ..shared.network.session import GameSession
from . import message_manager
from .message_manager import AuthMessageOpcode

log = logging.getLogger("NetworkSession")

ENCRYPTION_KEY = "F70IaxuU8C/w7FPXY1ibXw=="


class AuthPacket:
    __slots__ = ("opcode", "data")

    def __init__(self, opcode: int, data: bytes):
        self.opcode = opcode
        self.data = data

    @classmethod
    def from_bytes(cls, data: bytes) -> AuthPacket:
        reader = GamePacketReader(data)
        opcode = reader.read_byte()
        return cls(opcode, reader.read_bytes(reader.bytes_remaining))

    @classmethod
    def from_message(cls, opcode: AuthMessageOpcode, message: Writable) -> AuthPacket:
        writer = GamePacketWriter()
        message.write(writer)
        return cls(int(opcode), writer.to_bytes())

    def encode(self) -> bytes:
        """Opcode byte followed by the payload (before RC4/stream packing)."""
        return bytes([self.opcode]) + self.data


class AuthSession(GameSession):
    def __init__(self):
        super().__init__(ENCRYPTION_KEY)
        self.account: AccountModel | None = None
        self.characters: list[CharacterModel] = []
        self._outgoing_packets: deque[AuthPacket] = deque()

    def initialise(self, model: AccountModel | None) -> None:
        """Bind the authenticated account to this session."""
        if self.account is not None:
            raise RuntimeError("Session already has an account.")
        self.account = model

    def on_game_packet(self, data: bytes) -> None:
        self._handle_auth_packet(AuthPacket.from_bytes(data))

    def on_process_packets(self) -> None:
        while self.can_process_packets and self._outgoing_packets:
            self._send_packet(self._outgoing_packets.popleft())

    def _handle_auth_packet(self, packet: AuthPacket) -> None:
        name = opcode_name(AuthMessageOpcode, packet.opcode)
        message = message_manager.get_auth_message(packet.opcode, self.protocol_version)
        if message is None:
            log.warning("Received unknown Auth packet %X : %s", packet.opcode, hex_dump(packet.data))
            return

        handler = message_manager.get_handler(packet.opcode, self.protocol_version)
        if handler is None:
            log.warning("Received unhandled Auth packet %s(0x%X).", name, packet.opcode)
            return

        log.debug("Received packet %s(0x%X)", name, packet.opcode)

        reader = GamePacketReader(packet.data)
        message.read(reader)
        if reader.bytes_remaining > 0:
            log.warning("Failed to read entire contents of Auth packet %s (%d bytes remaining)", name, reader.bytes_remaining)

        try:
            handler(self, message)
        except InvalidPacketValueException:
            log.exception("Invalid packet value")
            self.on_disconnect()
        except Exception:
            log.exception("Auth handler for %s failed", name)

    def _send_packet(self, packet: AuthPacket) -> None:
        log.debug("Sending packet %s(0x%X)", opcode_name(AuthMessageOpcode, packet.opcode), packet.opcode)
        self.pack_and_send(packet.encode())

    def enqueue_message(self, message: Writable) -> None:
        opcode = message_manager.get_opcode(message)
        if opcode is None:
            log.warning("Failed to send message with no attribute!")
            return
        self._outgoing_packets.append(AuthPacket.from_message(opcode, message))
