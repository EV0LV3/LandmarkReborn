"""Auth flows not covered by the main end-to-end test: LoginUdp_9, deletion, gateway rejection."""

from __future__ import annotations

import asyncio

import pytest

from landmark_emu.auth.message_manager import AuthMessageOpcode
from landmark_emu.auth.messages import CharacterCreateReply, CharacterSelectInfoReply
from landmark_emu.shared.database.manager import database_manager
from landmark_emu.shared.network.crypto import PasswordProvider
from landmark_emu.shared.network.packet_io import GamePacketReader, GamePacketWriter

from .fake_client import FakeClient
from .test_end_to_end import auth_message, gateway_login_request, login_request, parse_auth


def create_request9(name: str, gender: int) -> bytes:
    def build(w: GamePacketWriter):
        w.write_ulong(1)
        w.write_uint(0)
        w.write_byte(1)
        w.write_uint(46)
        w.write_uint(gender)
        w.write_string(name)
        w.write_uint(1)
        for value in (9, 101, 3):
            w.write_uint(value)
        w.write_uint(7)

    return auth_message(AuthMessageOpcode.CharacterCreateRequest, build)


def delete_request(character_id: int) -> bytes:
    return auth_message(AuthMessageOpcode.CharacterDeleteRequest, lambda w: w.write_ulong(character_id))


async def make_session_key(username: str) -> str:
    def create():
        salt, verifier = PasswordProvider.generate_salt_and_verifier("pw")
        database_manager.auth_database.create_account(username, salt, verifier)
        account = database_manager.auth_database.get_account_by_username(username)
        database_manager.auth_database.update_account_session_key(account, "AB" * 16)
        return account.session_key

    return await asyncio.to_thread(create)


async def test_login_udp_9_create_select_and_delete(servers):
    auth, _ = servers
    key = await make_session_key("nine")
    client = await FakeClient.connect("127.0.0.1", auth.network.local_port)
    await client.start_session("LoginUdp_9")

    client.send_game(login_request(key))
    data = await client.receive_game()
    # LoginReply_9: opcode, logged in, status, member, internal, "soe", empty payload.
    assert data[:7] == bytes([AuthMessageOpcode.LoginReply, 1, 1, 0, 0, 0, 0])

    client.send_game(create_request9("Nina", gender=2))
    created = parse_auth(await client.receive_game())
    assert isinstance(created, CharacterCreateReply) and created.result == 1
    character_id = created.character_id

    client.send_game(auth_message(AuthMessageOpcode.CharacterSelectInfoRequest))
    data = await client.receive_game()
    assert data[0] == AuthMessageOpcode.CharacterSelectInfoReply
    reader = GamePacketReader(data[1:])
    assert (reader.read_uint(), reader.read_bool(), reader.read_uint()) == (1, False, 1)
    assert reader.read_ulong() == character_id
    assert b"Char_Biped_HumanFemale_Entities_" in data  # v9 builds the model name from enum names
    character = await asyncio.to_thread(database_manager.character_database.get_character_by_id, character_id)
    assert (character.race, character.gender, character.skin_tint) == (1, 2, 7)

    client.send_game(delete_request(character_id))
    empty = parse_auth(await client.receive_game())
    assert isinstance(empty, CharacterSelectInfoReply) and empty.characters == []
    data = await client.receive_game()
    assert data[0] == AuthMessageOpcode.CharacterDeleteReply
    reader = GamePacketReader(data[1:])
    assert (reader.read_ulong(), reader.read_uint()) == (character_id, 1)

    deleted = await asyncio.to_thread(database_manager.character_database.get_character_by_id, character_id)
    assert deleted.name is None and deleted.original_name == "Nina" and deleted.delete_time is not None
    # The freed name can be validated again.
    assert not await asyncio.to_thread(database_manager.character_database.character_name_exists, "Nina")

    client.send_game(delete_request(999))
    data = await client.receive_game()
    reader = GamePacketReader(data[1:])
    assert data[0] == AuthMessageOpcode.CharacterDeleteReply and (reader.read_ulong(), reader.read_uint()) == (999, 0)
    client.close()


async def test_login_with_bad_session_key_is_rejected(servers):
    auth, _ = servers
    client = await FakeClient.connect("127.0.0.1", auth.network.local_port)
    await client.start_session("LoginUdp_10")
    client.send_game(login_request("not-a-key"))
    # ArtData is always sent first, then a failed LoginReply.
    while True:
        data = await client.receive_game(30)
        if data[0] == AuthMessageOpcode.LoginReply:
            break
    assert data[1:2] == b"\x00"
    client.close()


async def test_gateway_rejects_unknown_ticket(servers):
    _, world = servers
    zone = await FakeClient.connect("127.0.0.1", world.network.local_port)
    await zone.start_session("ExternalGatewayApi_3")
    zone.out_stream.set_encryption(False)
    zone.send_game(gateway_login_request(1, "0" * 32))
    zone.out_stream.set_encryption(True)
    assert await zone.receive_game() == b"\x02\x00"
    zone.close()


async def test_data_before_session_request_disconnects(servers):
    auth, _ = servers
    client = await FakeClient.connect("127.0.0.1", auth.network.local_port)
    client.compression = True
    client.send_game(b"\x01")
    await asyncio.wait_for(client.disconnected.wait(), 5)
    client.close()


@pytest.mark.parametrize("protocol", ["LandmarkClientProtocol_709", "709", "ClientProtocol_ALL"])
def test_client_protocol_parsing(protocol):
    from landmark_emu.gateway.session import parse_client_protocol

    assert parse_client_protocol(protocol) == 709


def test_client_protocol_rejects_garbage():
    from landmark_emu.gateway.session import parse_client_protocol

    assert parse_client_protocol("landmarkclientprotocol_709") is None
    assert parse_client_protocol("nope") is None
