"""A minimal Landmark client speaking the reliable UDP protocol, for end-to-end tests."""

from __future__ import annotations

import asyncio
import random

from landmark_emu.shared.network.data_stream import DataStreamInput, DataStreamOutput
from landmark_emu.shared.network.packet_io import ProtocolPacketReader
from landmark_emu.shared.network.protocol import (
    DataFragment,
    DataWhole,
    PacketOptions,
    ProtocolMessageOpcode,
    ProtocolPacket,
    SessionReply,
    SessionRequest,
)
from landmark_emu.shared.network.session import encode_protocol_packet


class FakeClient(asyncio.DatagramProtocol):
    def __init__(self, capture: list | None = None):
        self.transport: asyncio.DatagramTransport | None = None
        self.server: tuple | None = None
        self.compression = False
        self.inbox: asyncio.Queue[bytes] = asyncio.Queue()
        self.session_reply: asyncio.Future = asyncio.get_running_loop().create_future()
        self.disconnected = asyncio.Event()
        self.in_stream = DataStreamInput(None, on_data=self.inbox.put_nowait)
        self.out_stream = DataStreamOutput(None, self._send_data_packet)
        self.out_stream.set_fragment_size(505)
        self.capture = capture  # (direction, datagram) tuples, for building pcaps.

    @classmethod
    async def connect(cls, host: str, port: int, capture: list | None = None) -> FakeClient:
        loop = asyncio.get_running_loop()
        client = cls(capture)
        await loop.create_datagram_endpoint(lambda: client, remote_addr=(host, port))
        client.server = (host, port)
        return client

    def connection_made(self, transport):
        self.transport = transport

    def _send(self, data: bytes) -> None:
        if self.capture is not None:
            self.capture.append(("out", data))
        self.transport.sendto(data)

    def datagram_received(self, data, addr):
        if self.capture is not None:
            self.capture.append(("in", data))
        packet = ProtocolPacket.from_bytes(data)
        if packet.opcode == ProtocolMessageOpcode.SessionReply:
            reply = SessionReply()
            reply.read(ProtocolPacketReader(packet.data), PacketOptions())
            self.compression = reply.compression != 0
            if not self.session_reply.done():
                self.session_reply.set_result(reply)
        elif packet.opcode in (ProtocolMessageOpcode.Data, ProtocolMessageOpcode.DataFragment):
            message = DataWhole() if packet.opcode == ProtocolMessageOpcode.Data else DataFragment()
            message.read(ProtocolPacketReader(packet.data), PacketOptions(compression=self.compression))
            if isinstance(message, DataWhole):
                self.in_stream.process_data_whole(message)
            else:
                self.in_stream.process_data_fragment(message)
        elif packet.opcode == ProtocolMessageOpcode.Disconnect:
            self.disconnected.set()

    def _send_data_packet(self, sequence, packet, out_of_order):
        message = DataFragment(sequence=sequence, data=packet.data) if packet.is_fragment else DataWhole(sequence=sequence, data=packet.data)
        options = PacketOptions(compression=self.compression)
        self._send(encode_protocol_packet(ProtocolPacket.from_message(message, options)))

    async def start_session(self, protocol: str) -> SessionReply:
        request = SessionRequest(crc_length=3, session_id=random.getrandbits(32), udp_length=512, protocol=protocol)
        self._send(encode_protocol_packet(ProtocolPacket.from_message(request, PacketOptions())))
        return await asyncio.wait_for(self.session_reply, 5)

    def send_game(self, data: bytes) -> None:
        self.out_stream.pack_data(data)

    async def receive_game(self, timeout: float = 10) -> bytes:
        return await asyncio.wait_for(self.inbox.get(), timeout)

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
