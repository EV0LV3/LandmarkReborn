"""Gateway session: authenticates the zone connection and carries tunnelled zone packets."""

from __future__ import annotations

import logging
from collections import deque

from ..shared.database.manager import database_manager
from ..shared.database.models import AccountModel, CharacterModel
from ..shared.events import TaskGenericEvent
from ..shared.logs import TRACE, hex_dump
from ..shared.network.data_stream import InvalidPacketValueException
from ..shared.network.message import Writable
from ..shared.network.packet_io import GamePacketReader, GamePacketWriter
from ..shared.network.protocol import ProtocolVersion, opcode_name
from ..shared.network.session import Address, GameSession
from . import messages as gateway_messages
from .messages import (
    Channel,
    ClientProtocol,
    GatewayMessageOpcode,
    LoginReply,
    LoginRequest,
    TunnelPacketToExternalConnection,
    gateway_handler,
)

log = logging.getLogger("NetworkSession")


class GatewayPacket:
    __slots__ = ("opcode", "channel", "data")

    def __init__(self, opcode: int, data: bytes, channel: int = 0):
        self.opcode = opcode
        self.channel = channel
        self.data = data

    @classmethod
    def from_bytes(cls, data: bytes) -> GatewayPacket:
        reader = GamePacketReader(data)
        first = reader.read_byte()
        return cls(first & 0x1F, reader.read_bytes(reader.bytes_remaining), channel=first >> 5)

    @classmethod
    def from_message(cls, opcode: GatewayMessageOpcode, message: Writable) -> GatewayPacket:
        writer = GamePacketWriter()
        message.write(writer)
        return cls(int(opcode), writer.to_bytes())


def parse_client_protocol(value: str) -> int | None:
    """``Enum.TryParse``: accepts a member name (case-sensitive) or any integer."""
    if value in ClientProtocol.__members__:
        return int(ClientProtocol[value])
    try:
        return int(value.strip())
    except ValueError:
        return None


class GatewaySession(GameSession):
    def __init__(self, crypto_key: str):
        super().__init__(crypto_key, sub_packet_acks=True)
        self.account: AccountModel | None = None
        self.characters: list[CharacterModel] = []
        self.client_protocol: int = 0
        self.client_build: str = ""
        self._outgoing_packets: deque[GatewayPacket] = deque()

        # The first Data packet (carrying the LoginRequest) arrives unencrypted.
        self.toggle_encryption(False)

    def on_accept(self, endpoint: Address) -> None:
        super().on_accept(endpoint)
        log.debug("New session received on %s:%s", endpoint[0], endpoint[1])

    def on_game_packet(self, data: bytes) -> None:
        self._handle_packet(GatewayPacket.from_bytes(data))

    def on_process_zone_packets(self) -> None:
        """Lets subclasses move their packets into the gateway queue before it is flushed."""

    def on_process_packets(self) -> None:
        self.on_process_zone_packets()
        while self.can_process_packets and self._outgoing_packets:
            self._send_packet(self._outgoing_packets.popleft())

    def _handle_packet(self, packet: GatewayPacket) -> None:
        name = opcode_name(GatewayMessageOpcode, packet.opcode)

        # Tunnel packets are handed straight to the zone layer.
        if packet.opcode == GatewayMessageOpcode.TunnelPacketFromExternalConnection:
            if log.isEnabledFor(TRACE):
                log.log(
                    TRACE,
                    "Received Gateway packet %s(0x%X) | Channel: %s | %s",
                    name,
                    packet.opcode,
                    opcode_name(Channel, packet.channel),
                    hex_dump(packet.data),
                )
            self.on_tunnel_data(packet.channel, packet.data)
            return

        message = gateway_messages.get_gateway_message(packet.opcode, self.protocol_version)
        if message is None:
            log.warning("Received unknown Gateway packet %X : %s", packet.opcode, hex_dump(packet.data))
            return

        handler = gateway_messages.get_handler(packet.opcode, self.protocol_version)
        if handler is None:
            log.warning("Received unhandled Gateway packet %s(0x%X)  : %s.", name, packet.opcode, hex_dump(packet.data))
            return

        if log.isEnabledFor(TRACE):
            log.log(TRACE, "Received packet %s(0x%X) : %s", name, packet.opcode, hex_dump(packet.data))

        reader = GamePacketReader(packet.data)
        message.read(reader)
        if reader.bytes_remaining > 0:
            log.warning("Failed to read entire contents of Gateway packet %s (%d bytes remaining)", name, reader.bytes_remaining)

        try:
            handler(self, message)
        except InvalidPacketValueException:
            log.exception("Invalid packet value")
            self.on_disconnect()
        except Exception:
            log.exception("Gateway handler for %s failed", name)

    def _send_packet(self, packet: GatewayPacket) -> None:
        writer = GamePacketWriter()
        if packet.opcode == GatewayMessageOpcode.TunnelPacketToExternalConnection:
            writer.write_byte(packet.opcode | (packet.channel << 5))
        else:
            writer.write_byte(packet.opcode)
        writer.write_bytes(packet.data)

        if log.isEnabledFor(TRACE):
            log.log(
                TRACE,
                "Sending packet %s(0x%X) : %s",
                opcode_name(GatewayMessageOpcode, packet.opcode),
                packet.opcode,
                hex_dump(packet.data),
            )
        self.pack_and_send(writer.to_bytes())

    def _enqueue_gateway_message(self, message: Writable) -> None:
        opcode = gateway_messages.get_opcode(message)
        if opcode is None:
            log.warning("Failed to send message with no attribute!")
            return
        self._outgoing_packets.append(GatewayPacket.from_message(opcode, message))

    @gateway_handler(GatewayMessageOpcode.LoginRequest, ProtocolVersion.ExternalGatewayApi_3)
    def handle_login_request(self, request: LoginRequest) -> None:
        log.info("%d, %s, %s, %s", request.character_id, request.server_ticket, request.client_protocol, request.client_build)

        # The client expects the LoginReply and everything after it to be RC4 encrypted.
        self.toggle_encryption(True)

        self.client_build = request.client_build
        protocol = parse_client_protocol(request.client_protocol)
        if protocol is None:
            log.error("Unsupported Client Protocol: %s. Disconnecting.", request.client_protocol)
            self.on_disconnect()
            return
        self.client_protocol = protocol

        def on_characters(characters: list[CharacterModel]):
            self.characters = characters
            selected = [c for c in characters if c.id == request.character_id]
            if len(selected) > 1:
                raise LookupError("Sequence contains more than one matching element")
            if selected:
                self.on_character_login(selected[0])
            else:
                log.error(
                    "Account %d tried to login as Character %d. Potential hack attempt. Disconnecting.",
                    self.account.id,
                    request.character_id,
                )
                self.on_disconnect()

        def on_account(account: AccountModel | None):
            self._enqueue_gateway_message(LoginReply(logged_in=account is not None))
            self.account = account
            self.events.append(
                TaskGenericEvent(
                    database_manager.run(database_manager.character_database.get_characters, self.account.id),
                    on_characters,
                )
            )

        self.events.append(
            TaskGenericEvent(
                database_manager.run(
                    database_manager.auth_database.get_account_by_server_ticket, request.server_ticket
                ),
                on_account,
            )
        )

    def on_character_login(self, model: CharacterModel) -> None:
        """The login was authenticated and ``model`` is the character logging in."""

    def on_tunnel_data(self, channel: int, data: bytes) -> None:
        """A TunnelPacketFromExternalConnection arrived."""

    def pack_tunnel_packet(self, data: bytes) -> None:
        """Wrap ``data`` in a tunnel packet for the client."""
        self._enqueue_gateway_message(TunnelPacketToExternalConnection(data=data))
