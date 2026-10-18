"""Byte-for-byte comparisons against output captured from the original C# implementation."""

import base64
import hashlib
import json

import pytest

from landmark_emu.auth.assets import ART_TINTS_PATH
from landmark_emu.auth.message_manager import AuthMessageOpcode
from landmark_emu.auth.messages import (
    CharacterAttachment,
    CharacterAttachment9,
    CharacterCreateReply,
    CharacterDeleteReply,
    CharacterLoginReply,
    CharacterPayload,
    CharacterPayload9,
    CharacterSelectInfoReply,
    CharacterSelectInfoReply9,
    ForceDisconnect,
    LoginReply,
    LoginReply9,
    SelectCharacter,
    SelectCharacter9,
    ServerInfo,
    ServerListReply,
    TunnelPacketServerToClient,
)
from landmark_emu.auth.session import AuthPacket
from landmark_emu.auth.tunnel_data import (
    ArtData,
    ClaimData,
    NameValidationReply,
    NameValidationResult,
    TunnelDataType,
    Unknown7,
)
from landmark_emu.auth.zone import ZoneServer
from landmark_emu.shared.database.models import ZoneServerModel
from landmark_emu.shared.game.text import LandmarkText, TextManager, jenkins_lookup2, text_manager
from landmark_emu.shared.network.crypto import Arc4Provider, PasswordProvider, append_crc, crc32
from landmark_emu.shared.network.data_stream import DataStreamInput, DataStreamOutput
from landmark_emu.shared.network.message import CharacterModelInfo, serialize
from landmark_emu.shared.network.packet_io import GamePacketReader, GamePacketWriter, ProtocolPacketReader
from landmark_emu.shared.network.protocol import (
    Ack,
    DataFragment,
    DataWhole,
    Disconnect,
    MultiPacket,
    OutOfOrder,
    PacketOptions,
    Ping,
    ProtocolPacket,
    SessionReply,
)
from landmark_emu.shared.network.session import encode_protocol_packet
from landmark_emu.world.messages import (
    ClientUpdateDoneSendingPreloadCharacters,
    ClientUpdateZonePopulation,
    GameTimeSync,
    InitializationParameters,
    Synchronization,
)
from landmark_emu.world.opcodes import ZoneMessageOpcode
from landmark_emu.world.resources import send_self_dump
from landmark_emu.world.send_self import Profile, SendSelfToClient
from landmark_emu.world.session import ZonePacket, get_opcode, get_opcode_bytes

KEY = base64.b64decode("F70IaxuU8C/w7FPXY1ibXw==")


def seq(n: int, mul: int, add: int) -> bytes:
    return bytes((i * mul + add) & 0xFF for i in range(n))


def h(data: bytes) -> str:
    return data.hex().upper()


# --- crypto --------------------------------------------------------------------------------


def test_arc4(golden):
    arc = Arc4Provider(KEY)
    first = bytearray(b"hello world")
    arc.encrypt(first)
    second = bytearray(range(256)) * 3 + bytearray(range(232))
    arc.encrypt(second)
    assert h(first) == golden["arc4"]["first"]
    assert h(second) == golden["arc4"]["second"]

    other = bytearray(bytes.fromhex(golden["arc4"]["other_plain"]))
    Arc4Provider(bytes.fromhex(golden["arc4"]["other_key"])).encrypt(other)
    assert h(other) == golden["arc4"]["other"]


def test_crc(golden):
    data = bytes.fromhex(golden["crc"]["data"])
    for seed, expected in golden["crc"]["seeds"].items():
        assert crc32(data, int(seed)) == expected, seed
    assert h(append_crc(data[:10], 0)) == golden["crc"]["append"]


def test_jenkins_and_text_hash(golden):
    for value, expected in golden["jenkins"].items():
        assert jenkins_lookup2(value) == expected, value
    assert TextManager.get_hash(62147) == golden["text_hash"]["62147"]
    assert TextManager.get_hash("Global.Text.5") == golden["text_hash"]["Global.Text.5"]
    assert TextManager.get_hash("Foo") == golden["text_hash"]["Foo"]


def test_password_verifier_compatible(golden):
    expected = golden["password"]
    salt, verifier = PasswordProvider.generate_salt_and_verifier(expected["password"], seq(16, 1, 1))
    assert (salt, verifier) == (expected["salt"], expected["verifier"])
    assert PasswordProvider.verify_password(salt, verifier, "hunter2")
    assert not PasswordProvider.verify_password(salt, verifier, "hunter3")


def test_uint_2bit_length(golden):
    for value, expected in golden["uint_2bit"].items():
        writer = GamePacketWriter()
        writer.write_uint_with_2bit_length(int(value))
        assert h(writer.to_bytes()) == expected, value
    for data, expected in golden["uint_2bit_read"].items():
        assert GamePacketReader(bytes.fromhex(data)).read_uint_2bit_length() == expected, data


# --- data streams --------------------------------------------------------------------------


def test_stream_output(golden):
    expected = golden["stream_out"]
    events = []
    stream = DataStreamOutput(None, lambda s, p, o: events.append({"seq": s, "frag": p.is_fragment, "ooo": o, "data": h(p.data)}))
    stream.set_fragment_size(expected["fragment_size"])
    inputs = [bytes.fromhex(x) for x in expected["inputs"]]
    for index, data in enumerate(inputs):
        if index == 4:
            stream.set_encryption(False)
        stream.pack_data(data)
        if index == 4:
            stream.set_encryption(True)
    stream.handle_ack(expected["ack"])
    assert stream.missing_acks == expected["missing_acks_after_ack"]
    stream.resend_data(5)
    assert events == expected["events"]


def test_stream_input(golden):
    expected = golden["stream_in"]
    outputs, acks = [], []
    stream = DataStreamInput(None, on_data=lambda d: outputs.append(h(d)))
    for item in expected["feed"]:
        data = bytes.fromhex(item["data"])
        if item["frag"]:
            stream.process_data_fragment(DataFragment(sequence=item["seq"], data=data))
        else:
            stream.process_data_whole(DataWhole(sequence=item["seq"], data=data))
        acks.append(stream.last_ack if stream.last_ack is not None else -1)
    assert outputs == expected["outputs"]
    assert acks == expected["last_acks"]


def test_output_stream_round_trips_through_input_stream():
    received = []
    inbound = DataStreamInput(None, on_data=received.append)
    outbound = DataStreamOutput(
        None,
        lambda s, p, o: (inbound.process_data_fragment if p.is_fragment else inbound.process_data_whole)(
            (DataFragment if p.is_fragment else DataWhole)(sequence=s, data=p.data)
        ),
    )
    outbound.set_fragment_size(505)
    payloads = [b"\x01hello", seq(3000, 7, 3), b"\x02" * 505, b"\x03" * 506]
    for payload in payloads:
        outbound.pack_data(payload)
    assert received == payloads


# --- protocol ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, message, options",
    [
        ("session_reply", SessionReply(session_id=0xDEADBEEF, crc_seed=0, crc_length=2, compression=0x100, udp_length=512), PacketOptions(compression=True)),
        ("ack", Ack(sequence=5), PacketOptions()),
        ("ack_sub", Ack(sequence=0x1234), PacketOptions(is_subpacket=True)),
        ("out_of_order", OutOfOrder(sequence=9), PacketOptions(compression=True)),
        ("data_compressed", DataWhole(sequence=3, data=seq(20, 1, 0)), PacketOptions(compression=True)),
        ("fragment_uncompressed", DataFragment(sequence=65535, data=seq(20, 1, 1)), PacketOptions(compression=False)),
        ("ping", Ping(), PacketOptions()),
        ("disconnect", Disconnect(), PacketOptions(is_priority=True)),
    ],
)
def test_protocol_messages(golden, name, message, options):
    assert h(encode_protocol_packet(ProtocolPacket.from_message(message, options))) == golden["protocol"][name]


@pytest.mark.parametrize("variant", ["plain", "compressed"])
def test_multi_packet(golden, variant):
    message = MultiPacket()
    message.read(ProtocolPacketReader(bytes.fromhex(golden["multi"][variant])), PacketOptions(compression=True))
    assert [{"opcode": p.opcode, "data": h(p.data)} for p in message.packets] == golden["multi"][f"{variant}_packets"]


# --- auth ----------------------------------------------------------------------------------


def auth_bytes(opcode, message) -> str:
    return h(AuthPacket.from_message(opcode, message).encode())


def test_auth_messages(golden):
    expected = golden["auth"]
    text_manager.clear()  # The C# reference ran with no text table loaded.

    payload = CharacterPayload(name="Tester", race=1, gender=2, profile_id=46, model_id=392)
    payload.model.skin_id, payload.model.race, payload.model.gender = 5, 1, 2
    payload.model.customisations += [(1, 2, 3), (4, 5, 6)]
    payload.character_attachments.append(
        CharacterAttachment(model_name="Char_Biped_[RACE][GENDER]_Entities_Colony_000_Chest.adr", slot=8)
    )
    select10 = CharacterSelectInfoReply(status=1)
    select10.characters.append(SelectCharacter(status=1, character_id=7, last_login=-0.5, last_server_id=1, character_data=payload))

    payload9 = CharacterPayload9(name="Tester", gender=2, head_id=1, model_id=21, skin_tint=5)
    payload9.customizations.append((1, 2, 3))
    payload9.character_attachments.append(
        CharacterAttachment9(model_name="Char_Biped_HumanFemale_Entities_Colony_000_Chest.adr", slot=7)
    )
    select9 = CharacterSelectInfoReply9(status=1)
    select9.characters.append(SelectCharacter9(status=1, character_id=7, last_login=0.0, last_server_id=1, character_data=payload9))

    server_list = ServerListReply()
    server_list.servers.append(ZoneServer(ZoneServerModel(id=1, name_id=62147, host="127.0.0.1", port=19000, flags=1)).build())

    O = AuthMessageOpcode
    assert auth_bytes(O.LoginReply, LoginReply(logged_in=True, status=1)) == expected["login_reply"]
    assert auth_bytes(O.LoginReply, LoginReply9(logged_in=False, status=0)) == expected["login_reply_9"]
    assert auth_bytes(O.CharacterSelectInfoReply, select10) == expected["select_10"]
    assert auth_bytes(O.CharacterSelectInfoReply, select9) == expected["select_9"]
    assert auth_bytes(O.CharacterSelectInfoReply, CharacterSelectInfoReply(status=1)) == expected["select_empty"]
    assert auth_bytes(O.ServerListReply, server_list) == expected["server_list"]
    assert auth_bytes(O.CharacterCreateReply, CharacterCreateReply(result=1, character_id=42)) == expected["create_reply"]
    assert auth_bytes(O.CharacterDeleteReply, CharacterDeleteReply(character_id=42, status=1)) == expected["delete_reply"]
    assert auth_bytes(O.ForceDisconnect, ForceDisconnect(reason=3)) == expected["force_disconnect"]
    assert (
        auth_bytes(
            O.CharacterLoginReply,
            CharacterLoginReply(
                character_id=7,
                server_id=1,
                result=1,
                server=ServerInfo(
                    server_address="127.0.0.1:19000",
                    account_name="user",
                    encryption_key=KEY,
                    character_id=7,
                    character_name="Tester",
                    guid=1,
                    server_ticket="00112233445566778899AABBCCDDEEFF",
                ),
            ),
        )
        == expected["login_reply_character"]
    )
    assert (
        auth_bytes(O.CharacterLoginReply, CharacterLoginReply(character_id=7, server_id=9, result=3))
        == expected["login_reply_character_fail"]
    )
    assert (
        auth_bytes(
            O.TunnelPacketServerToClient,
            TunnelPacketServerToClient(
                type=TunnelDataType.NameValidationReply,
                data=NameValidationReply(result=NameValidationResult.NameTaken, first_name="Bob"),
            ),
        )
        == expected["tunnel_name_validation"]
    )
    assert (
        auth_bytes(
            O.TunnelPacketServerToClient,
            TunnelPacketServerToClient(
                type=TunnelDataType.Unknown7, data=Unknown7(string="Welcome to Landmark RE:Build! We're happy to have you!")
            ),
        )
        == expected["tunnel_unknown7"]
    )
    assert (
        auth_bytes(O.TunnelPacketServerToClient, TunnelPacketServerToClient(type=TunnelDataType.ClaimData, data=ClaimData()))
        == expected["tunnel_claims"]
    )


def test_art_data_packet(golden):
    expected = golden["auth"]
    with ART_TINTS_PATH.open(encoding="utf-8-sig") as handle:
        art_data = ArtData.from_json(json.load(handle))
    packet = AuthPacket.from_message(
        AuthMessageOpcode.TunnelPacketServerToClient,
        TunnelPacketServerToClient(server_id=0, type=TunnelDataType.ArtData, data=art_data),
    ).encode()
    assert h(packet[:256]) == expected["art_data_head"]
    assert len(packet) == int(expected["art_data_length"])
    assert hashlib.sha256(packet).hexdigest().upper() == expected["art_data_sha256"]


# --- zone ----------------------------------------------------------------------------------


def test_zone_opcode_bytes(golden):
    for value, expected in golden["zone_opcode_bytes"].items():
        assert h(get_opcode_bytes(int(value))) == expected, value


def test_zone_opcode_parse(golden):
    for data, expected in golden["zone_opcode_parse"].items():
        opcode, offset = get_opcode(bytes.fromhex(data))
        assert (opcode if opcode is not None else -1, offset) == (expected["opcode"], expected["offset"]), data


def test_send_self_capture_round_trip(golden):
    expected = golden["zone"]
    message = SendSelfToClient()
    reader = GamePacketReader(send_self_dump()[2:])
    message.read(reader)
    assert reader.bytes_remaining == 0

    data = ZonePacket.from_message(ZoneMessageOpcode.SendSelfToClient, message, prepend_size=True).data
    assert h(data[:4096]) == expected["send_self_roundtrip_head"]
    assert len(data) == expected["send_self_roundtrip_length"]
    assert hashlib.sha256(data).hexdigest().upper() == expected["send_self_roundtrip_sha256"]


def test_send_self_built(golden):
    message = SendSelfToClient()
    message.guid = 1
    message.character_id = 7
    message.account_name = "user"
    message.gender_maybe = 2
    message.unknown22 = 1
    message.model_id = 392
    message.model = CharacterModelInfo(skin_id=5, race=1, gender=2, customisations=[(1, 2, 3)])
    message.identity.first_name = "Tester"
    message.profiles.append(
        Profile(
            unknown0=46, name_id=LandmarkText(571666), unknown3=3, unknown15=True,
            unknown19=2.8, unknown20=2.75, unknown21=0.4, unknown22=1, unknown23=1.4, unknown24=15.0,
            unknown29=3, unknown30=3, unknown31=3,
        )
    )
    message.current_profile = 46
    message.unknown24.append((46, 46, 0))
    message.unknown30.append((3, 46))
    message.loadouts[0].unknown1.unknown1 = 46
    data = ZonePacket.from_message(ZoneMessageOpcode.SendSelfToClient, message, prepend_size=True).data
    assert h(data) == golden["zone"]["send_self_built"]


def test_send_self_client_0_589(golden):
    # 0.589 clients share the 0.695 layout up to unknown68, then read a different 49 byte tail
    # (the 0.695 tail is 53 bytes: unknown69-74, is_admin_maybe, unknown76, unknown77, trailing).
    message = SendSelfToClient()
    message.read(GamePacketReader(send_self_dump()[2:]))
    data_695 = ZonePacket.from_message(ZoneMessageOpcode.SendSelfToClient, message, prepend_size=True).data
    message.client_0_589 = True
    data_589 = ZonePacket.from_message(ZoneMessageOpcode.SendSelfToClient, message, prepend_size=True).data

    assert len(data_589) == len(data_695) - 53 + 49
    # The prepended size differs; the body matches until the tail.
    head = len(data_695) - 53
    assert data_589[4:head] == data_695[4:head]
    assert data_589[head:] == bytes(49)

    reader = GamePacketReader(data_589)
    SendSelfToClient(client_0_589=True).read(reader)
    assert reader.bytes_remaining == 0


def test_small_zone_messages(golden):
    expected = golden["zone"]
    assert h(serialize(GameTimeSync(time=12345.678 - 0.003, cycle_speed=9.1))) == expected["game_time_sync"]
    assert (
        h(serialize(Synchronization(time1=1.5, time2=2.5, client_time=1000.25, server_time=500.125, server_time2=500.125, time3=1000.25)))
        == expected["synchronization"]
    )
    assert h(serialize(ClientUpdateZonePopulation())) == expected["zone_population"]
    assert h(serialize(ClientUpdateDoneSendingPreloadCharacters())) == expected["preload_done"]
    assert h(serialize(InitializationParameters(environment="live"))) == expected["init_params"]
