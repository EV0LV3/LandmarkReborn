"""Network sessions: the per-client protocol state machine."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable

from ..events import Event
from ..logs import TRACE, hex_dump
from .crypto import append_crc
from .data_stream import (
    DataPacket,
    DataStreamInput,
    DataStreamOutput,
    InvalidOperationError,
    InvalidPacketValueException,
)
from .packet_io import ProtocolPacketReader, ProtocolPacketWriter
from .protocol import (
    Ack,
    DataFragment,
    DataWhole,
    Disconnect,
    MultiPacket,
    OutOfOrder,
    PacketOptions,
    Ping,
    ProtocolMessage,
    ProtocolMessageOpcode,
    ProtocolPacket,
    ProtocolVersion,
    SessionReply,
    SessionRequest,
    get_protocol_message,
    opcode_name,
)

log = logging.getLogger("NetworkSession")

Address = tuple


def encode_protocol_packet(packet: ProtocolPacket) -> bytes:
    """Datagram bytes for a protocol packet: big-endian opcode, payload and (optionally) CRC."""
    writer = ProtocolPacketWriter()
    writer.write_ushort(packet.opcode)
    writer.write_bytes(packet.data)
    data = writer.to_bytes()
    if packet.use_encryption:
        data = append_crc(data, 0)
    return data


class SocketHeartbeat:
    TIMEOUT_SECONDS = 180.0

    def __init__(self):
        self._time_to_flatline = self.TIMEOUT_SECONDS

    @property
    def flatline(self) -> bool:
        return self._time_to_flatline <= 0.0

    def on_heartbeat(self) -> None:
        self._time_to_flatline = self.TIMEOUT_SECONDS

    def update(self, last_tick: float) -> None:
        self._time_to_flatline -= last_tick


class NetworkSession:
    def __init__(self):
        self._can_process_packets = False
        self.was_connected = False
        self.disconnected = False
        self.heartbeat = SocketHeartbeat()
        self.endpoint: Address | None = None
        self._endpoint_ref = ""
        self.events: deque[Event] = deque()
        self.on_send: Callable[[Address, bytes], None] | None = None

    @property
    def can_process_packets(self) -> bool:
        """Whether queued packets may currently be sent."""
        return self._can_process_packets and self.was_connected and not self.disconnected

    def on_accept(self, endpoint: Address) -> None:
        self.endpoint = endpoint
        self._endpoint_ref = f"{endpoint[0]}:{endpoint[1]}"
        log.debug("Client connected: %s", self._endpoint_ref)

    def update(self, last_tick: float) -> None:
        self.heartbeat.update(last_tick)
        if self.heartbeat.flatline:
            self.on_disconnect()

        # Events complete in order; a pending event holds back the ones queued after it.
        while self.events:
            event = self.events[0]
            if not event.can_execute():
                break
            self.events.popleft()
            try:
                event.execute()
            except Exception:
                log.exception("Session event failed")

    def send_raw(self, data: bytes) -> None:
        try:
            self.on_send(self.endpoint, data)
        except Exception:
            log.exception("Failed to send data")
            self.on_disconnect()

    def on_data(self, data: bytes) -> None:
        pass

    def on_disconnect(self) -> None:
        self.disconnected = True
        log.debug("Client disconnected: %s", self._endpoint_ref)

    def toggle_packet_processing(self, allowed: bool) -> None:
        if not self.was_connected and allowed:
            self.was_connected = True
        self._can_process_packets = allowed


class GameSession(NetworkSession):
    """Implements the reliable UDP protocol; subclasses handle the decrypted game packets."""

    # Packets sent per burst before the sender pauses; the client is overwhelmed otherwise.
    SEND_BURST = 50
    SEND_BURST_PAUSE = 0.05
    IDLE_SLEEP = 0.01

    _PROTOCOL_HANDLERS: dict[int, str] = {
        ProtocolMessageOpcode.SessionRequest: "handle_session_request",
        ProtocolMessageOpcode.DataFragment: "handle_data_fragment",
        ProtocolMessageOpcode.Data: "handle_data_whole",
        ProtocolMessageOpcode.MultiPacket: "handle_multi_packet",
        ProtocolMessageOpcode.Ping: "handle_ping",
        ProtocolMessageOpcode.Disconnect: "handle_disconnect",
        ProtocolMessageOpcode.Ack: "handle_ack",
        ProtocolMessageOpcode.OutOfOrder: "handle_out_of_order",
    }

    def __init__(self, crypto_key: str, sub_packet_acks: bool = False):
        super().__init__()
        self.protocol_version = ProtocolVersion.NONE
        self.encryption_key = crypto_key
        self.session_id = 0

        self._client_crc_length = 0
        self._server_crc_length = 2
        self._client_udp_length = 0
        self._server_udp_length = 512
        self._server_compression = 0x100

        self._has_authed = False
        self._disconnecting = False
        self._packet_pause_count = 0
        self._sub_packet_acks = sub_packet_acks

        self._outgoing_priority: deque[ProtocolPacket] = deque()
        self._outgoing_data: deque[ProtocolPacket] = deque()
        self._out_of_order: deque[ProtocolPacket] = deque()
        self._sender_task: asyncio.Task | None = None

        self._input_stream = DataStreamInput(
            crypto_key,
            on_data=self.on_game_packet,
            on_out_of_order=self._on_input_out_of_order,
            on_ack=self._on_input_ack,
        )
        self._output_stream = DataStreamOutput(crypto_key, on_data=self._on_output_data)

    # -- stream callbacks -------------------------------------------------------------------

    def _on_input_ack(self, sequence: int) -> None:
        self.enqueue_protocol_message(Ack(sequence=sequence), PacketOptions(is_subpacket=self._sub_packet_acks))

    def _on_input_out_of_order(self, sequence: int) -> None:
        self.enqueue_protocol_message(
            OutOfOrder(sequence=sequence), PacketOptions(compression=self._server_compression != 0)
        )

    def _on_output_data(self, sequence: int, packet: DataPacket, was_out_of_order: bool) -> None:
        message: ProtocolMessage
        if not packet.is_fragment:
            message = DataWhole(sequence=sequence, data=packet.data)
        else:
            message = DataFragment(sequence=sequence, data=packet.data)
        self.enqueue_protocol_message(
            message,
            PacketOptions(
                is_subpacket=False,
                compression=self._server_compression != 0,
                was_out_of_order=was_out_of_order,
                sequence=sequence,
            ),
        )

    # -- hooks for subclasses ---------------------------------------------------------------

    def on_game_packet(self, data: bytes) -> None:
        """A decrypted game packet arrived (Auth, Gateway, ...)."""

    def on_process_packets(self) -> None:
        """Called every tick so subclasses can flush their own outgoing queues."""

    # -- incoming ---------------------------------------------------------------------------

    def on_data(self, data: bytes) -> None:
        if self._sender_task is None:
            self._sender_task = asyncio.get_running_loop().create_task(self._process_out_packets())

        self.heartbeat.on_heartbeat()

        packet = ProtocolPacket.from_bytes(
            data, PacketOptions(is_subpacket=False, compression=self._server_compression != 0)
        )
        self._handle_protocol_packet(packet)

        super().on_data(data)

    def update(self, last_tick: float) -> None:
        self.on_process_packets()
        super().update(last_tick)

    def _handle_protocol_packet(self, packet: ProtocolPacket) -> None:
        name = opcode_name(ProtocolMessageOpcode, packet.opcode)
        message = get_protocol_message(packet.opcode)
        if message is None:
            log.warning("Received unknown protocol packet %X : %s", packet.opcode, hex_dump(packet.data))
            return

        if not self._has_authed and not isinstance(message, SessionRequest):
            log.debug("Client sent data without session or session requests. Disconnecting.")
            self.on_disconnect()
            return

        handler_name = self._PROTOCOL_HANDLERS.get(packet.opcode)
        if handler_name is None:
            log.warning("Received unhandled protocol packet %s(0x%X).", name, packet.opcode)
            return

        if log.isEnabledFor(TRACE):
            log.log(TRACE, "Received packet %s(0x%X) : %s", name, packet.opcode, hex_dump(packet.data))

        reader = ProtocolPacketReader(packet.data)
        message.read(reader, packet.packet_options)
        if reader.bytes_remaining > 2:
            log.warning("Failed to read entire contents of packet %s (%d bytes remaining)", name, reader.bytes_remaining)

        try:
            getattr(self, handler_name)(message)
        except InvalidPacketValueException:
            log.exception("Invalid packet value")
            self.on_disconnect()
        except Exception:
            log.exception("Protocol handler %s failed", handler_name)

    # -- outgoing ---------------------------------------------------------------------------

    def enqueue_protocol_message(self, message: ProtocolMessage, options: PacketOptions) -> None:
        packet = ProtocolPacket.from_message(message, options)

        if options.is_priority:
            self._outgoing_priority.append(packet)
            return

        opcode = message.OPCODE
        if opcode == ProtocolMessageOpcode.Ack:
            # Only the latest ack matters.
            for queued in self._outgoing_priority:
                if queued.opcode == ProtocolMessageOpcode.Ack:
                    queued.ignore = True
            self._outgoing_priority.append(packet)
        elif opcode == ProtocolMessageOpcode.MultiPacket:
            self._outgoing_priority.append(packet)
        elif options.was_out_of_order:
            self._out_of_order.append(packet)
        else:
            self._outgoing_data.append(packet)

    async def _process_out_packets(self) -> None:
        """Paced sender: priority packets first, then resends, then regular data."""
        while not self.disconnected:
            if not self._outgoing_priority and not self._out_of_order and not self._outgoing_data:
                await asyncio.sleep(self.IDLE_SLEEP)

            self._packet_pause_count += 1

            if self.can_process_packets and self._outgoing_priority:
                priority_packet = self._outgoing_priority.popleft()
                if not priority_packet.ignore:
                    self.send_packet(priority_packet)
                    if priority_packet.opcode == ProtocolMessageOpcode.Disconnect:
                        self.on_disconnect()
                        return

            if self.can_process_packets and self._out_of_order:
                self.send_packet(self._out_of_order.popleft())

            if not self._out_of_order and not self._outgoing_priority:
                if self.can_process_packets and self._outgoing_data:
                    self.send_packet(self._outgoing_data.popleft())

            if self._packet_pause_count >= self.SEND_BURST:
                self._packet_pause_count = 0
                await asyncio.sleep(self.SEND_BURST_PAUSE)

            await asyncio.sleep(0)

    def send_packet(self, packet: ProtocolPacket) -> None:
        data = encode_protocol_packet(packet)
        if not data:
            return

        if log.isEnabledFor(TRACE):
            log.log(
                TRACE,
                "Sending packet %s(0x%X) : %s",
                opcode_name(ProtocolMessageOpcode, packet.opcode),
                packet.opcode,
                hex_dump(packet.data),
            )

        self.send_raw(data)

    def pack_and_send(self, data: bytes) -> None:
        """Hand game data to the output stream, which queues the resulting Data packets."""
        self._output_stream.pack_data(data)

    def toggle_encryption(self, using_encryption: bool) -> None:
        self._input_stream.set_encryption(using_encryption)
        self._output_stream.set_encryption(using_encryption)

    # -- protocol handlers ------------------------------------------------------------------

    def handle_session_request(self, request: SessionRequest) -> None:
        log.info("%d, %d, %d, %s", request.session_id, request.crc_length, request.udp_length, request.protocol)

        self._has_authed = True

        self.session_id = request.session_id
        self._client_crc_length = request.crc_length
        self._client_udp_length = request.udp_length

        if self._client_udp_length != 512:
            raise InvalidOperationError(f"Unsupported UDP length {self._client_udp_length}.")

        if request.protocol == "LoginUdp_10":
            self.protocol_version = ProtocolVersion.LoginUdp_10
        if request.protocol == "LoginUdp_9":
            self.protocol_version = ProtocolVersion.LoginUdp_9
        if request.protocol == "ExternalGatewayApi_3":
            self.protocol_version = ProtocolVersion.ExternalGatewayApi_3
            self._server_compression = 0x0

        # Leave room for opcode, compression byte and CRC.
        self._output_stream.set_fragment_size(self._client_udp_length - 7)
        self.enqueue_protocol_message(
            SessionReply(
                session_id=self.session_id,
                crc_seed=0,
                crc_length=self._server_crc_length,
                compression=self._server_compression,
                udp_length=self._server_udp_length,
            ),
            PacketOptions(is_subpacket=False, compression=self._server_compression != 0),
        )

    def handle_data_fragment(self, data_fragment: DataFragment) -> None:
        self._input_stream.process_data_fragment(data_fragment)

    def handle_data_whole(self, data_whole: DataWhole) -> None:
        self._input_stream.process_data_whole(data_whole)

    def handle_multi_packet(self, multi_packet: MultiPacket) -> None:
        # Handle immediately; re-queueing them causes ordering problems.
        for packet in multi_packet.packets:
            self._handle_protocol_packet(packet)

    def handle_ping(self, ping: Ping) -> None:
        self.enqueue_protocol_message(Ping(), PacketOptions())
        if self._output_stream.missing_acks:
            self._output_stream.resend_data_on_ping()

    def handle_disconnect(self, disconnect: Disconnect) -> None:
        self.on_disconnect()

    def on_disconnect(self) -> None:
        # A failed send calls back into on_disconnect; don't recurse.
        if self._disconnecting:
            return
        self._disconnecting = True
        try:
            if self.was_connected:
                self.send_packet(ProtocolPacket.from_message(Disconnect(), PacketOptions(is_priority=True)))
            super().on_disconnect()
        finally:
            self._disconnecting = False

    def handle_ack(self, ack: Ack) -> None:
        self._output_stream.handle_ack(ack.sequence)

    def handle_out_of_order(self, out_of_order: OutOfOrder) -> None:
        if self._out_of_order:
            return
        self._output_stream.resend_data(out_of_order.sequence)
