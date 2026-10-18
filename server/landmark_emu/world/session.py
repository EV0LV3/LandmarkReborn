"""World (zone) session: zone packets tunnelled through the gateway."""

from __future__ import annotations

import logging
from collections import deque

from ..gateway.session import GatewaySession
from ..shared.database.models import CharacterModel
from ..shared.game.entity import Gender
from ..shared.game.game_table import ProfileDefinitionEntry, game_table_manager
from ..shared.game.text import LandmarkText
from ..shared.logs import TRACE, hex_dump
from ..shared.network.data_stream import InvalidPacketValueException
from ..shared.network.message import CharacterModelInfo, Writable
from ..shared.network.packet_io import GamePacketReader, GamePacketWriter
from ..shared.network.protocol import opcode_name
from . import message_manager, packet_data
from .opcodes import DEFINED_OPCODES, ZoneMessageOpcode as Op
from .resources import packet_dump, terrain_manifest_dump
from .send_self import Profile, SendSelfToClient

log = logging.getLogger("NetworkSession")

ENCRYPTION_KEY = "F70IaxuU8C/w7FPXY1ibXw=="

# Position and rotation (quaternion) from the captured live-server SendSelf, in zone 406.
SPAWN_POSITION = (1693.0899658203125, 1581.800048828125, 808.75, 1.0)
SPAWN_ROTATION = (0.0, 0.9969556927680969, 0.0, -0.07797038555145264)


class ZonePacket:
    __slots__ = ("opcode", "data")

    def __init__(self, opcode: int, data: bytes):
        self.opcode = opcode
        self.data = data

    @classmethod
    def from_message(cls, opcode: Op, message: Writable, prepend_size: bool = False) -> ZonePacket:
        writer = GamePacketWriter()
        message.write(writer)
        data = writer.to_bytes()
        if prepend_size:
            size = GamePacketWriter()
            size.write_uint(len(data))
            data = size.to_bytes() + data
        return cls(int(opcode), data)


def get_opcode_bytes(opcode: int) -> bytes:
    """Big-endian opcode with leading zero bytes removed (e.g. 0x2E00 -> 2E 00)."""
    return int(opcode).to_bytes(4, "big").lstrip(b"\x00")


def get_opcode(data: bytes) -> tuple[int | None, int]:
    """Decode a zone opcode (2, 3 or 4 bytes, shortest match first) and the payload offset."""
    if data and data[0] in DEFINED_OPCODES:
        return data[0], 2

    if len(data) > 1:
        opcode = (data[0] << 8) + data[1]
        if opcode in DEFINED_OPCODES:
            return opcode, 2
        if len(data) > 2:
            opcode = (data[0] << 16) + (data[1] << 8) + data[2]
            if opcode in DEFINED_OPCODES:
                return opcode, 3
            if len(data) > 3:
                opcode = (data[0] << 24) + (data[1] << 16) + (data[2] << 8) + data[3]
                if opcode in DEFINED_OPCODES:
                    return opcode, 4

    return None, 0


def _model_for_gender(profile: ProfileDefinitionEntry, gender: int) -> int:
    if gender == Gender.Male:
        return profile.male_model_id
    if gender == Gender.Female:
        return profile.female_model_id
    return 252


class WorldSession(GatewaySession):
    def __init__(self):
        super().__init__(ENCRYPTION_KEY)
        self._outgoing_zone_packets: deque[ZonePacket] = deque()
        self.ready_sent = False
        self.character: CharacterModel | None = None

    @property
    def terrain_manifest(self) -> bytes:
        return terrain_manifest_dump()

    # -- session handlers -------------------------------------------------------------------

    def on_character_login(self, model: CharacterModel) -> None:
        self.character = model

        self.enqueue_raw(Op.SendZoneDetails, packet_data.ZONE_DETAILS)

        # Set up the player.
        self.enqueue_raw(Op.InitializationParameters, packet_data.INITIALIZATION_PARAMETERS)
        self.enqueue_raw(Op.ClientGameSettings, packet_data.CLIENT_GAME_SETTINGS)
        self.enqueue_raw(Op.ReferenceDataItemClassDefinitions, packet_data.REFERENCE_DATA_ITEM_CLASS_DEFINITIONS)
        self.enqueue_raw(
            Op.ReferenceDataItemCategoryDefinitions, packet_dump("39-ReferenceDataItemCategoryDefinitions")[4:]
        )
        self.enqueue_raw(Op.ReferenceDataProfileDefinitions, packet_dump("41-ReferenceDataProfileDefinitions")[4:])
        self.enqueue_raw(Op.SkillBase, packet_data.SKILL_BASE)
        self.enqueue_raw(Op.CommandBase, packet_dump("44-CommandBase")[2:])

        self.build_send_to_self_packet()

    def build_send_to_self_packet(self) -> None:
        # TODO (from the original): build this from a real player entity.
        character = self.character
        if character is None or character.name is None:
            # TODO (from the original): force disconnect instead of just dropping the session.
            self.on_disconnect()
            return

        profile_data = game_table_manager.profile_definitions.get_entry(character.profile_type_id)

        message = SendSelfToClient()
        message.client_0_589 = self.client_build.startswith("0.589.")
        message.guid = 1
        message.character_id = character.id
        message.account_name = self.account.username
        message.gender_maybe = character.gender
        message.unknown22 = character.race
        message.model_id = _model_for_gender(profile_data, character.gender)

        message.model = CharacterModelInfo(skin_id=character.skin_tint, race=character.race, gender=character.gender)
        for custom in character.customisation:
            message.model.customisations.append((custom.slot, custom.option, custom.tint))
        message.identity.first_name = character.name
        # The original left these at zero, which spawns the player at the world origin, buried
        # under the voxel terrain: the client then meshes solid ground forever and never drops
        # the loading screen. Use the spawn from the captured SendSelf (SendSelf.bin).
        message.unknown3 = SPAWN_POSITION
        message.unknown4 = SPAWN_ROTATION

        message.profiles.append(
            Profile(
                unknown0=profile_data.id,
                name_id=LandmarkText.from_id(profile_data.name_id),
                unknown3=profile_data.profile_type,
                unknown15=True,
                unknown19=profile_data.stand_camera_height,
                unknown20=profile_data.line_of_sight_height,
                unknown21=profile_data.capsule_radius,
                unknown22=1,
                unknown23=profile_data.crouch_camera_height,
                unknown24=profile_data.mass,
                unknown29=profile_data.char_size,
                unknown30=profile_data.armor,
                unknown31=profile_data.feet,
            )
        )
        message.current_profile = profile_data.id
        message.unknown24.append((profile_data.id, profile_data.id, 0))
        message.unknown30.append((profile_data.profile_type, profile_data.id))
        message.loadouts[0].unknown1.unknown1 = profile_data.id

        self.enqueue_message(message)

    # -- packet management ------------------------------------------------------------------

    def on_process_zone_packets(self) -> None:
        while self.can_process_packets and self._outgoing_zone_packets:
            self._send_zone_packet(self._outgoing_zone_packets.popleft())

    def _handle_zone_packet(self, packet: ZonePacket) -> None:
        name = opcode_name(Op, packet.opcode)
        message = message_manager.get_zone_message(packet.opcode, self.client_protocol)
        if message is None:
            log.warning("Received Zone packet that was unreadable %s(0x%X) : %s", name, packet.opcode, hex_dump(packet.data))
            return

        log.debug("Received Zone packet %s(0x%X)", name, packet.opcode)

        reader = GamePacketReader(packet.data)
        message.read(reader)
        if reader.bytes_remaining > 0:
            log.warning("Failed to read entire contents of Zone packet %s (%d bytes remaining)", name, reader.bytes_remaining)

        handler = message_manager.get_handler(packet.opcode, self.client_protocol)
        if handler is None:
            log.warning("Unhandled Zone packet %s(0x%X).", name, packet.opcode)
            return

        try:
            handler(self, message)
        except InvalidPacketValueException:
            log.exception("Invalid packet value")
            self.on_disconnect()
        except Exception:
            log.exception("Zone handler for %s failed", name)

    def enqueue_message(self, message: Writable) -> None:
        opcode = message_manager.get_opcode(message)
        if opcode is None:
            log.warning("Failed to send message with no attribute!")
            return
        self._outgoing_zone_packets.append(
            ZonePacket.from_message(opcode, message, message_manager.has_prepended_size(opcode))
        )

    def enqueue_raw(self, opcode: Op, data: bytes) -> None:
        """Queue a pre-built zone payload (captured from the live game)."""
        self._outgoing_zone_packets.append(ZonePacket(int(opcode), bytes(data)))

    def _send_zone_packet(self, packet: ZonePacket) -> None:
        writer = GamePacketWriter()
        writer.write_bytes(get_opcode_bytes(packet.opcode))
        writer.write_bytes(packet.data)

        log.debug("Sending packet %s(0x%X)", opcode_name(Op, packet.opcode), packet.opcode)
        if log.isEnabledFor(TRACE):
            log.log(TRACE, "%s", hex_dump(packet.data))

        self.pack_tunnel_packet(writer.to_bytes())

    def on_tunnel_data(self, channel: int, data: bytes) -> None:
        opcode, offset = get_opcode(data)
        payload = data[offset:]
        if opcode is None:
            log.warning("Unknown Zone Packet : %s", hex_dump(payload))
            return
        self._handle_zone_packet(ZonePacket(opcode, payload))
