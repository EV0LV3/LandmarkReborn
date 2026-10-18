"""Full login flow against real Auth + World servers, driven by a fake game client."""

from __future__ import annotations

import struct
import time
from pathlib import Path

import aiohttp
import pytest

from landmark_emu.auth import message_manager as auth_messages
from landmark_emu.auth.message_manager import AuthMessageOpcode
from landmark_emu.auth.messages import (
    CharacterCreateReply,
    CharacterLoginReply,
    CharacterSelectInfoReply,
    LoginReply,
    ServerListReply,
    TunnelPacketServerToClient,
)
from landmark_emu.auth.tunnel_data import ArtData, NameValidationResult, TunnelDataType
from landmark_emu.shared.network.packet_io import GamePacketReader, GamePacketWriter
from landmark_emu.shared.network.protocol import ProtocolVersion
from landmark_emu.world.messages import GameTimeSync
from landmark_emu.world.opcodes import ZoneMessageOpcode as Op
from landmark_emu.world.send_self import SendSelfToClient
from landmark_emu.world.session import get_opcode, get_opcode_bytes

from .fake_client import FakeClient

# --- client message builders ----------------------------------------------------------------


def auth_message(opcode: AuthMessageOpcode, build=None) -> bytes:
    writer = GamePacketWriter()
    writer.write_byte(opcode)
    if build:
        build(writer)
    return writer.to_bytes()


def login_request(session_key: str) -> bytes:
    def build(w):
        w.write_string(session_key)
        w.write_string("fingerprint")
        w.write_uint(1)
        w.write_uint(0)

    return auth_message(AuthMessageOpcode.LoginRequest, build)


def name_validation_request(name: str) -> bytes:
    body = GamePacketWriter()
    body.write_string(name)
    body.write_string("")

    def build(w):
        w.write_ulong(0)
        w.write_uint(len(body) + 1)
        w.write_byte(TunnelDataType.NameValidationRequest)
        w.write_bytes(body.to_bytes())

    return auth_message(AuthMessageOpcode.TunnelPacketClientToServer, build)


def character_create_request(name: str) -> bytes:
    def build(w):
        w.write_ulong(1)
        w.write_uint(0)
        w.write_byte(1)
        w.write_uint(46)  # profile
        w.write_uint(0)
        w.write_string(name)
        w.write_uint(2)
        for custom in ((9, 101, 3), (11, 202, 4)):
            for value in custom:
                w.write_uint(value)
        w.write_uint(5)  # skin tint
        w.write_uint(0)
        w.write_uint(1)  # race
        w.write_uint(2)  # gender
        w.write_uint(0)

    return auth_message(AuthMessageOpcode.CharacterCreateRequest, build)


def character_login_request(character_id: int, server_id: int) -> bytes:
    def build(w):
        w.write_ulong(character_id)
        w.write_ulong(server_id)
        w.write_uint(0)
        w.write_string("en_US")
        w.write_ulong(0)

    return auth_message(AuthMessageOpcode.CharacterLoginRequest, build)


def parse_auth(data: bytes):
    # Some readers (e.g. LoginReply) intentionally skip trailing placeholder fields, as in the original.
    message = auth_messages.get_auth_message(data[0], ProtocolVersion.LoginUdp_10)
    message.read(GamePacketReader(data[1:]))
    return message


async def receive_auth(client: FakeClient, message_type, timeout: float = 30):
    deadline = time.monotonic() + timeout
    while True:
        message = parse_auth(await client.receive_game(max(deadline - time.monotonic(), 0.01)))
        if isinstance(message, message_type):
            return message


def gateway_login_request(character_id: int, ticket: str) -> bytes:
    w = GamePacketWriter()
    w.write_byte(0x01)
    w.write_ulong(character_id)
    w.write_string(ticket)
    w.write_string("LandmarkClientProtocol_709")
    w.write_string("0.695.1.132647")
    return w.to_bytes()


def zone_to_server(opcode: Op, payload: bytes = b"") -> bytes:
    return bytes([0x06]) + get_opcode_bytes(opcode) + payload


async def receive_zone(client: FakeClient, opcode: Op, timeout: float = 30) -> bytes:
    deadline = time.monotonic() + timeout
    while True:
        data = await client.receive_game(max(deadline - time.monotonic(), 0.01))
        if data[0] & 0x1F != 0x05:
            continue
        zone_opcode, offset = get_opcode(data[1:])
        if zone_opcode == opcode:
            return data[1 + offset:]


# --- pcap ----------------------------------------------------------------------------------


def write_pcap(path: Path, flows: list[tuple[int, int, list]]) -> None:
    """flows: (server port, client port, [(direction, datagram)])."""
    out = bytearray(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
    for server_port, client_port, datagrams in flows:
        for direction, payload in datagrams:
            src, dst = (client_port, server_port) if direction == "out" else (server_port, client_port)
            udp = struct.pack(">HHHH", src, dst, 8 + len(payload), 0) + payload
            ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0, bytes([127, 0, 0, 1]), bytes([127, 0, 0, 1])) + udp
            frame = b"\x00" * 12 + b"\x08\x00" + ip
            out += struct.pack("<IIII", 0, 0, len(frame), len(frame)) + frame
    path.write_bytes(out)


# --- the test ------------------------------------------------------------------------------


async def test_full_login_flow(servers, tmp_path, monkeypatch):
    auth, world = servers
    api = f"http://127.0.0.1:{auth.web_api.port}"

    # --- web API: account + session key ---
    async with aiohttp.ClientSession() as http:
        async with http.post(f"{api}/create", params={"username": "player", "password": "s3cret!"}) as response:
            assert response.status == 200
            assert await response.json() == {"username": "player", "message": "Success."}
        async with http.post(f"{api}/create", params={"username": "player", "password": "x"}) as response:
            assert response.status == 409
        async with http.post(f"{api}/authenticate", params={"username": "player", "password": "wrong"}) as response:
            assert response.status == 403
        async with http.post(f"{api}/authenticate", params={"username": "player", "password": "s3cret!"}) as response:
            assert response.status == 200
            body = await response.json()
    session_key = body["sessionKey"]
    assert len(session_key) == 32 and body["message"] == "Success."

    # --- auth server ---
    auth_capture: list = []
    client = await FakeClient.connect("127.0.0.1", auth.network.local_port, auth_capture)
    reply = await client.start_session("LoginUdp_10")
    assert (reply.crc_length, reply.compression, reply.udp_length) == (2, 0x100, 512)

    client.send_game(login_request(session_key))
    art = await receive_auth(client, TunnelPacketServerToClient)
    assert isinstance(art.data, ArtData) and len(art.data.art_tint_groups) > 1000
    login = await receive_auth(client, LoginReply)
    assert login.logged_in and login.status == 1

    client.send_game(auth_message(AuthMessageOpcode.ServerListRequest))
    server_list = await receive_auth(client, ServerListReply)
    assert [(s.server_id, s.name) for s in server_list.servers] == [(1, "Emulated Server (Emulated Server)")]
    assert server_list.servers[0].server_info == '<ServerInfo IsRecommended="1"></ServerInfo>'

    client.send_game(auth_message(AuthMessageOpcode.CharacterSelectInfoRequest))
    assert (await receive_auth(client, CharacterSelectInfoReply)).characters == []

    for name, expected in (("mybadwordname", NameValidationResult.NameNaughty), ("Tester", NameValidationResult.Success)):
        client.send_game(name_validation_request(name))
        # NameValidationReply is write-only on the server, so decode the raw tunnel packet here.
        data = await client.receive_game(10)
        assert data[0] == AuthMessageOpcode.TunnelPacketServerToClient
        reader = GamePacketReader(data[1:])
        reader.read_ulong()  # server id
        size = reader.read_uint()
        assert reader.read_byte() == TunnelDataType.NameValidationReply
        assert size == reader.bytes_remaining + 1
        assert (reader.read_string(), reader.read_string(), reader.read_uint()) == (name, "", expected)

    client.send_game(character_create_request("Tester"))
    created = await receive_auth(client, CharacterCreateReply)
    assert (created.result, created.character_id) == (1, 1)

    client.send_game(auth_message(AuthMessageOpcode.CharacterSelectInfoRequest))
    select = await receive_auth(client, CharacterSelectInfoReply)
    assert len(select.characters) == 1
    character = select.characters[0]
    assert (character.character_id, character.character_data.name, character.character_data.model_id) == (1, "Tester", 392)
    assert character.character_data.model.customisations == [(9, 101, 3), (11, 202, 4)]

    client.send_game(character_login_request(1, 1))
    login_reply = await receive_auth(client, CharacterLoginReply)
    assert login_reply.result == 1
    assert login_reply.server.server_address == "127.0.0.1:19000"
    assert login_reply.server.character_name == "Tester"
    ticket = login_reply.server.server_ticket
    assert len(ticket) == 32
    client.close()

    # --- world server (gateway) ---
    world_capture: list = []
    zone = await FakeClient.connect("127.0.0.1", world.network.local_port, world_capture)
    reply = await zone.start_session("ExternalGatewayApi_3")
    assert reply.compression == 0

    # The gateway LoginRequest is sent unencrypted; everything after is RC4 encrypted.
    zone.out_stream.set_encryption(False)
    zone.send_game(gateway_login_request(1, ticket))
    zone.out_stream.set_encryption(True)

    gateway_reply = await zone.receive_game(10)
    assert gateway_reply == b"\x02\x01"  # LoginReply(logged_in=True)

    zone_details = await receive_zone(zone, Op.SendZoneDetails)
    assert b"OpenBetaGeometry_406" in zone_details

    send_self = await receive_zone(zone, Op.SendSelfToClient, timeout=60)
    assert struct.unpack_from("<I", send_self)[0] == len(send_self) - 4  # prepended size
    message = SendSelfToClient()
    message.read(GamePacketReader(send_self))
    assert (message.character_id, message.account_name, message.identity.first_name) == (1, "player", "Tester")
    assert message.model_id == 392 and message.current_profile == 46
    assert message.model.customisations == [(9, 101, 3), (11, 202, 4)]

    zone.send_game(zone_to_server(Op.GameTimeSync, struct.pack("<dfB", 1000.0, 1.0, 0)))
    sync = GameTimeSync()
    sync.read(GamePacketReader(await receive_zone(zone, Op.GameTimeSync)))
    assert sync.time == pytest.approx(999.997) and sync.cycle_speed == pytest.approx(9.1)

    zone.send_game(zone_to_server(Op.ClientIsReady))
    assert await receive_zone(zone, Op.QuickChatBase) == bytes.fromhex("010000000000")
    await receive_zone(zone, Op.ZoneDoneSendingInitialData, timeout=60)
    zone.close()

    # --- the packet parser decodes the captured traffic ---
    pcap = tmp_path / "capture.pcap"
    write_pcap(pcap, [(20042, 50001, auth_capture), (19000, 50002, world_capture)])
    monkeypatch.chdir(tmp_path)
    from landmark_emu.parser.__main__ import main as parser_main

    parser_main([str(pcap), "--game-data", str(tmp_path / "gameData"), "--out", "parse.txt", "--dump-dir", "dumps"])
    parsed = (tmp_path / "parse.txt").read_text(encoding="utf-8")
    for expected in (
        "[Client] [Protocol] SessionRequest",
        "[Server] [Auth] LoginReply",
        "[Client] [Auth] CharacterCreateRequest",
        "[Server] [Auth] CharacterLoginReply",
        "[Server] [Zone] SendZoneDetails",
        "[Server] [Zone] SendSelfToClient",
        "[Client] [Zone] ClientIsReady",
        '"first_name": "Tester"',
    ):
        assert expected in parsed, expected
    assert (tmp_path / "SendSelf.bin").read_bytes()[2:] == send_self
