"""Packet parser: decodes a pcap/pcapng capture of a Landmark session into ``PacketParse.txt``.

Usage: ``python -m landmark_emu.parser <capture.pcapng> [--game-data gameData] [--out PacketParse.txt]``

Auth traffic is recognised by port 20042; everything else is treated as gateway/zone traffic.
"""

from __future__ import annotations

import argparse
import base64
import logging
import socket
import sys
import time
from enum import Enum
from pathlib import Path

from ..auth import message_manager as auth_messages
from ..auth.message_manager import AuthMessageOpcode
from ..auth.messages import CharacterLoginReply
from ..gateway import messages as gateway_messages
from ..gateway.messages import Channel, GatewayMessageOpcode
from ..shared.game.text import text_manager
from ..shared.logs import TRACE, configure_logging, hex_dump
from ..shared.network.data_stream import DataStreamInput
from ..shared.network.message import to_json
from ..shared.network.packet_io import GamePacketReader, ProtocolPacketReader
from ..shared.network.protocol import (
    DataFragment,
    DataWhole,
    MultiPacket,
    OutOfOrder,
    PacketOptions,
    ProtocolMessageOpcode,
    ProtocolPacket,
    ProtocolVersion,
    SessionReply,
    SessionRequest,
    get_protocol_message,
    opcode_name,
)
from ..world import message_manager as zone_messages
from ..world.opcodes import ZoneMessageOpcode
from ..world.session import get_opcode
from .pcap import read_frames

log = logging.getLogger("Parser")

AUTH_PORT = 20042
CLIENT_HEADER = "[Client]"
SERVER_HEADER = "[Server]"


class GamePacketType(Enum):
    Auth = "Auth"
    Gateway = "Gateway"
    Zone = "Zone"


class ParserPacketOptions(PacketOptions):
    def __init__(self, is_client: bool, game_packet_type: GamePacketType, **kwargs):
        super().__init__(**kwargs)
        self.is_client = is_client
        self.game_packet_type = game_packet_type


class Parser:
    def __init__(self, dump_dir: Path):
        self.lines: list[str] = []
        self.current_packet = 0
        self.packet_max = 0
        self._dump_dir = dump_dir

        def stream(name: str, packet_type: GamePacketType, is_client: bool) -> DataStreamInput:
            return DataStreamInput(
                None,
                on_data=lambda data: self.on_game_packet(data, packet_type, is_client),
                lenient_fragments=True,
                name=name,
            )

        self.auth_server_stream = stream("authServerStream", GamePacketType.Auth, False)
        self.auth_client_stream = stream("authClientStream", GamePacketType.Auth, True)
        self.zone_server_stream = stream("zoneServerStream", GamePacketType.Gateway, False)
        self.zone_client_stream = stream("zoneClientStream", GamePacketType.Gateway, True)
        # The gateway LoginRequest arrives unencrypted.
        self.zone_server_stream.set_encryption(False)
        self.zone_client_stream.set_encryption(False)

    # -- game layer -------------------------------------------------------------------------

    def on_game_packet(self, data: bytes, packet_type: GamePacketType, is_client: bool) -> None:
        header = CLIENT_HEADER if is_client else SERVER_HEADER

        if packet_type is GamePacketType.Auth:
            self._handle_auth_message(data, is_client)
        elif packet_type is GamePacketType.Gateway:
            for zone_stream in (self.zone_client_stream, self.zone_server_stream):
                if not zone_stream.using_encryption:
                    zone_stream.set_encryption(True)
            self._handle_gateway_packet(data, is_client)
        else:
            opcode, offset = get_opcode(data)
            if opcode is None:
                if len(data) > 5000:
                    self._dump(f"{self.current_packet}-unknown", data)
                self.lines.append(f"{header} [Zone] Unknown packet | {len(data)} bytes")
                log.warning("Unknown Zone Packet : %s", hex_dump(data))
                return

            name = opcode_name(ZoneMessageOpcode, opcode)
            payload = data[offset:]
            self.lines.append(f"{header} [Zone] {name} (0x{opcode:08X}) | {len(payload)} bytes")
            if log.isEnabledFor(TRACE):
                log.log(TRACE, "%s Parsed Zone packet %s (0x%08X) | %d bytes | %s", header, name, opcode, len(payload), hex_dump(payload))

            if len(payload) > 5000:
                self._dump(f"{self.current_packet}-{name}", data)

            if opcode == ZoneMessageOpcode.SendSelfToClient:
                Path("SendSelf.bin").write_bytes(data)
            elif opcode == ZoneMessageOpcode.TerrainCellModifiedCellManifest:
                Path("TerrainCellManifest.bin").write_bytes(data)

            message = zone_messages.get_zone_message(opcode)
            if message is None:
                return
            message.read(GamePacketReader(payload))
            self.lines.append(to_json(message))

        self.current_packet += 1

    def _dump(self, name: str, data: bytes) -> None:
        self._dump_dir.mkdir(parents=True, exist_ok=True)
        (self._dump_dir / name).write_bytes(data)

    def _handle_gateway_packet(self, data: bytes, is_client: bool) -> None:
        header = CLIENT_HEADER if is_client else SERVER_HEADER
        opcode = data[0] & 0x1F
        data = data[1:]
        channel = data[0] >> 5 if data else 0
        name = opcode_name(GatewayMessageOpcode, opcode)
        if log.isEnabledFor(TRACE):
            log.log(
                TRACE,
                "%s Parsed Gateway packet %s (0x%08X) | %d bytes | Channel: %s | %s",
                header, name, opcode, len(data), opcode_name(Channel, channel), hex_dump(data),
            )

        if opcode in (
            GatewayMessageOpcode.TunnelPacketFromExternalConnection,
            GatewayMessageOpcode.TunnelPacketToExternalConnection,
        ):
            self.on_game_packet(data, GamePacketType.Zone, is_client)
            return

        message = gateway_messages.get_gateway_message(opcode, ProtocolVersion.ExternalGatewayApi_3)
        if message is None:
            log.warning("Received unknown Gateway packet %X : %s", opcode, hex_dump(data))
            return
        message.read(GamePacketReader(data))
        self.lines.append(to_json(message))

    def _handle_auth_message(self, data: bytes, is_client: bool) -> None:
        header = CLIENT_HEADER if is_client else SERVER_HEADER
        opcode = data[0]
        name = opcode_name(AuthMessageOpcode, opcode)
        if log.isEnabledFor(TRACE):
            log.log(TRACE, "%s Parsed Auth packet %s (0x%08X) | %d bytes | %s", header, name, opcode, len(data), hex_dump(data))
        self.lines.append(f"{header} [Auth] {name} (0x{opcode:08X})")

        message = auth_messages.get_auth_message(opcode, ProtocolVersion.LOGIN_ALL)
        if message is None:
            log.warning("%s Received unknown auth packet %X : %s", header, opcode, hex_dump(data))
            return

        message.read(GamePacketReader(data[1:]))

        if isinstance(message, CharacterLoginReply):
            key = base64.b64encode(message.server.encryption_key).decode("ascii")
            self.zone_client_stream.set_encryption_key(key)
            self.zone_server_stream.set_encryption_key(key)

        self.lines.append(to_json(message))

    # -- protocol layer ---------------------------------------------------------------------

    def handle_frame(self, frame: bytes) -> None:
        if len(frame) < 34:
            return
        ip = frame[14:]
        protocol = ip[9]
        if protocol != 17:  # UDP
            src = socket.inet_ntoa(ip[12:16])
            dst = socket.inet_ntoa(ip[16:20])
            protocol_name = {6: "TCP"}.get(protocol, "Unknown")
            self.lines.append(f"Unreadable packet | {src} -> {dst} | {protocol_name} | {len(frame)} bytes")
            return

        source_port = int.from_bytes(frame[34:36], "big")
        destination_port = int.from_bytes(frame[36:38], "big")
        packet_type = GamePacketType.Auth if AUTH_PORT in (source_port, destination_port) else GamePacketType.Gateway
        is_client = source_port > 40000

        packet = ProtocolPacket.from_bytes(
            frame[42:],
            ParserPacketOptions(is_client, packet_type, is_subpacket=False, compression=True),
        )
        try:
            self._handle_protocol_packet(packet)
        except Exception:
            log.exception("Failed to parse protocol packet")

    def _handle_protocol_packet(self, packet: ProtocolPacket) -> None:
        options: ParserPacketOptions = packet.packet_options
        header = CLIENT_HEADER if options.is_client else SERVER_HEADER

        message = get_protocol_message(packet.opcode)
        if message is None:
            self.current_packet += 1
            log.warning("%s Received unknown protocol packet %X : %s", header, packet.opcode, hex_dump(packet.data))
            return

        if isinstance(message, OutOfOrder):
            return

        if options.game_packet_type is GamePacketType.Gateway:
            options.compression = False

        message.read(ProtocolPacketReader(packet.data), options)
        name = opcode_name(ProtocolMessageOpcode, packet.opcode)

        if isinstance(message, (SessionRequest, SessionReply)):
            self.lines.append(f"{header} [Protocol] {name} (0x{packet.opcode:08X})")
            self.lines.append(to_json(message))
            self.current_packet += 1

        if isinstance(message, MultiPacket):
            for sub_packet in message.packets:
                self.packet_max += 1
                sub_packet.packet_options = ParserPacketOptions(
                    options.is_client,
                    options.game_packet_type,
                    is_subpacket=True,
                    compression=options.game_packet_type is not GamePacketType.Gateway,
                )
                self._handle_protocol_packet(sub_packet)

        if isinstance(message, (DataWhole, DataFragment)):
            stream = self._stream_for(options)
            if stream is None:
                return
            if isinstance(message, DataWhole):
                stream.process_data_whole(message)
            else:
                stream.process_data_fragment(message)

    def _stream_for(self, options: ParserPacketOptions) -> DataStreamInput | None:
        if options.game_packet_type is GamePacketType.Auth:
            return self.auth_client_stream if options.is_client else self.auth_server_stream
        if options.game_packet_type is GamePacketType.Gateway:
            return self.zone_client_stream if options.is_client else self.zone_server_stream
        return None


def _count_udp_frames(path: Path) -> int:
    count = 0
    for frame in read_frames(path):
        if len(frame) > 23 and frame[14 + 9] == 17:
            count += 1
    return count


def _progress(done: float, total: float) -> None:
    if total <= 0:
        return
    percent = min(done / total * 100.0, 100.0)
    filled = int(percent / 5)
    sys.stdout.write(f"\r[{'#' * filled}{'-' * (20 - filled)}] {percent:5.1f}%")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> None:
    arg_parser = argparse.ArgumentParser(description="Landmark RE:Build packet parser")
    arg_parser.add_argument("capture", type=Path, help="pcap or pcapng capture file")
    arg_parser.add_argument("--game-data", default="gameData", help="directory containing en_us_data.dat (optional)")
    arg_parser.add_argument("--out", type=Path, default=Path("PacketParse.txt"), help="output text file")
    arg_parser.add_argument("--dump-dir", type=Path, default=Path("packets"), help="where large packets are dumped")
    arg_parser.add_argument("--verbose", action="store_true", help="log at TRACE level")
    args = arg_parser.parse_args(argv)

    configure_logging(None, console_level=TRACE if args.verbose else logging.WARNING)
    started = time.perf_counter()
    print("[Landmark RE:Build Packet Parser] Starting Up!")

    if (Path(args.game_data) / "en_us_data.dat").is_file():
        text_manager.initialise(args.game_data)
    else:
        print(f"Text table not found in '{args.game_data}'; localised names will be blank.")

    auth_messages.initialise()
    gateway_messages.initialise()
    zone_messages.initialise()

    parser = Parser(args.dump_dir)
    parser.packet_max = _count_udp_frames(args.capture)
    print(f"[Landmark RE:Build Packet Parser] Beginning to parse {args.capture}")
    print(f"Estimated {parser.packet_max} packets parsing... ")

    last_report = 0.0
    for frame in read_frames(args.capture):
        parser.handle_frame(frame)
        now = time.perf_counter()
        if now - last_report > 0.1:
            _progress(parser.current_packet, parser.packet_max)
            last_report = now
    _progress(1, 1)
    print()

    args.out.write_text("\n".join(parser.lines) + "\n", encoding="utf-8")
    elapsed = time.strftime("%H:%M:%S", time.gmtime(time.perf_counter() - started))
    print(f"Finished! Completed {parser.packet_max} packets in {elapsed}")


if __name__ == "__main__":
    main()
