"""Auth server messages (LoginUdp_9 / LoginUdp_10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from ..shared.game.text import text_manager
from ..shared.network.message import CharacterModelInfo, Readable, Writable
from ..shared.network.protocol import ProtocolVersion
from .message_manager import AuthMessageOpcode, auth_message
from .tunnel_data import TunnelData, new_tunnel_data

LOGIN_ALL = ProtocolVersion.LOGIN_ALL
LOGIN_9 = ProtocolVersion.LoginUdp_9
LOGIN_10 = ProtocolVersion.LoginUdp_10


def _str_size(value: str) -> int:
    return 4 + len(value.encode("utf-8"))


class CharacterCreateResult(IntEnum):
    Success = 1
    UnableToCreate = 2
    UnableToProcess = 3


class CharacterLoginResult(IntEnum):
    NoResult = 0
    Success = 1
    AccountInUse = 2
    ServerNotFound = 3
    ServerLocked = 4
    CharacterLocked = 5
    WrongAccount = 6
    Exception = 7
    CharacterQueued = 8
    NotAllowed = 9
    ServerFeatureLocked = 10


# --- Login ---------------------------------------------------------------------------------


@auth_message(AuthMessageOpcode.LoginRequest, LOGIN_ALL)
@dataclass
class LoginRequest(Readable):
    session_id: str = ""
    system_finger_print: str = ""
    locale: int = 0
    third_party_auth_ticket: int = 0

    def read(self, reader):
        self.session_id = reader.read_string()
        self.system_finger_print = reader.read_string()
        self.locale = reader.read_uint()
        self.third_party_auth_ticket = reader.read_uint()


@auth_message(AuthMessageOpcode.LoginReply, LOGIN_10)
@dataclass
class LoginReply(Readable, Writable):
    logged_in: bool = False
    status: int = 0
    result: int = 0
    is_member: bool = False
    is_internal: bool = False
    namespace: str = "soe"

    def read(self, reader):
        self.logged_in = reader.read_bool()
        self.status = reader.read_uint()
        self.result = reader.read_uint()
        self.is_member = reader.read_bool()
        self.is_internal = reader.read_bool()
        self.namespace = reader.read_string()

    def write(self, writer):
        writer.write_bool(self.logged_in)
        writer.write_uint(self.status)
        writer.write_uint(self.result)
        writer.write_bool(self.is_member)
        writer.write_bool(self.is_internal)
        writer.write_string(self.namespace)
        # TODO (from the original): AccountFeatures, Payload (XML) and ErrorDetails are
        # "bytes with length" structures; written as empty.
        writer.write_ulong(0)
        writer.write_ulong(0)
        writer.write_ulong(0)


@auth_message(AuthMessageOpcode.LoginReply, LOGIN_9)
@dataclass
class LoginReply9(Readable, Writable):
    logged_in: bool = False
    status: int = 0
    is_member: bool = False
    is_internal: bool = False
    namespace: str = "soe"

    def read(self, reader):
        self.logged_in = reader.read_bool()
        self.status = reader.read_uint()
        self.is_member = reader.read_bool()
        self.is_internal = reader.read_bool()
        self.namespace = reader.read_string()

    def write(self, writer):
        writer.write_bool(self.logged_in)
        writer.write_uint(self.status)
        writer.write_bool(self.is_member)
        writer.write_bool(self.is_internal)
        writer.write_string(self.namespace)
        writer.write_uint(0)  # TODO (from the original): Payload ("bytes with length").


@auth_message(AuthMessageOpcode.ForceDisconnect, LOGIN_ALL)
@dataclass
class ForceDisconnect(Writable):
    reason: int = 0

    def write(self, writer):
        writer.write_uint(self.reason)


# --- Server list ---------------------------------------------------------------------------


@dataclass
class Server(Readable, Writable):
    server_id: int = 0
    is_locked: bool = False
    name: str = ""
    name_id: int = 0
    description: str = ""
    description_id: int = 0
    req_feature_id: int = 0
    server_info: str = ""
    population_level: int = 0
    population_data: str = ""
    access_expression: str = ""
    allowed_access: bool = False

    def read(self, reader):
        self.server_id = reader.read_ulong()
        self.is_locked = reader.read_bool()
        self.name = reader.read_string()
        self.name_id = reader.read_uint()
        self.name = f"{self.name} ({text_manager.get_text_for_id(self.name_id)})"
        self.description = reader.read_string()
        self.description_id = reader.read_uint()
        self.description = f"{self.description} ({text_manager.get_text_for_id(self.description_id)})"
        self.req_feature_id = reader.read_uint()
        self.server_info = reader.read_string()
        self.population_level = reader.read_uint()
        self.population_data = reader.read_string()
        self.access_expression = reader.read_string()
        self.allowed_access = reader.read_bool()

    def write(self, writer):
        writer.write_ulong(self.server_id)
        writer.write_bool(self.is_locked)
        writer.write_string(self.name)
        writer.write_uint(self.name_id)
        writer.write_string(self.description)
        writer.write_uint(self.description_id)
        writer.write_uint(self.req_feature_id)
        writer.write_string(self.server_info)
        writer.write_uint(self.population_level)
        writer.write_string(self.population_data)
        writer.write_string(self.access_expression)
        writer.write_bool(self.allowed_access)


@auth_message(AuthMessageOpcode.ServerListRequest, LOGIN_ALL)
@dataclass
class ServerListRequest(Readable):
    def read(self, reader):
        pass


@auth_message(AuthMessageOpcode.ServerListReply, LOGIN_ALL)
@dataclass
class ServerListReply(Readable, Writable):
    servers: list[Server] = field(default_factory=list)

    def read(self, reader):
        for _ in range(reader.read_uint()):
            server = Server()
            server.read(reader)
            self.servers.append(server)

    def write(self, writer):
        writer.write_uint(len(self.servers))
        for server in self.servers:
            server.write(writer)


@auth_message(AuthMessageOpcode.ServerUpdate, LOGIN_ALL)
@dataclass
class ServerUpdate(Writable):
    server: Server = field(default_factory=Server)

    def write(self, writer):
        self.server.write(writer)


# --- Character select ----------------------------------------------------------------------


@dataclass
class CharacterAttachment(Readable, Writable):
    model_name: str = ""
    texture_alias: str = ""
    semantic_tint: str = ""  # TintAlias?
    unknown3: str = ""  # DecalAlias?
    unknown4: int = 0  # TintId?
    unknown5: int = 0  # CompositeId?
    slot: int = 0  # AttachmentSlot ("ActorUsage")
    unknown7: int = 0
    unknown8: bool = False

    def get_size(self):
        return (
            _str_size(self.model_name) + _str_size(self.texture_alias) + _str_size(self.semantic_tint)
            + _str_size(self.unknown3) + 4 + 4 + 4 + 4 + 1
        )

    def read(self, reader):
        self.model_name = reader.read_string()
        self.texture_alias = reader.read_string()
        self.semantic_tint = reader.read_string()
        self.unknown3 = reader.read_string()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.slot = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_bool()

    def write(self, writer):
        writer.write_string(self.model_name)
        writer.write_string(self.texture_alias)
        writer.write_string(self.semantic_tint)
        writer.write_string(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.slot)
        writer.write_uint(self.unknown7)
        writer.write_bool(self.unknown8)


@dataclass
class CharacterPayload(Readable, Writable):
    name: str = "Player"
    unknown0: int = 0
    unknown1: int = 1
    head_id: int = 0
    model_id: int = 0
    gender: int = 0
    race: int = 0
    profile_id: int = 0
    unknown7: int = 0
    unknown8: int = 0
    array_142c34c30: list[int] = field(default_factory=list)
    model: CharacterModelInfo = field(default_factory=CharacterModelInfo)
    character_attachments: list[CharacterAttachment] = field(default_factory=list)
    friends: list = field(default_factory=list)  # Friend structure not implemented in the original.
    unknown_q: int = 0

    def get_size(self):
        total = 4 + 4 * len(self.array_142c34c30)
        total += self.model.get_size()
        total += 4 + sum(a.get_size() for a in self.character_attachments)
        total += 4 + sum(f.get_size() for f in self.friends)
        return total + _str_size(self.name) + 1 + 4 * 7 + 8 + 8

    def read(self, reader):
        reader.read_uint()  # Size
        self.name = reader.read_string()
        self.unknown0 = reader.read_byte()
        self.unknown1 = reader.read_uint()
        self.head_id = reader.read_uint()
        self.model_id = reader.read_uint()
        self.gender = reader.read_uint()
        self.race = reader.read_uint()
        self.profile_id = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_ulong()
        self.array_142c34c30 = [reader.read_uint() for _ in range(reader.read_uint())]
        self.model.read(reader)
        for _ in range(reader.read_uint()):
            attachment = CharacterAttachment()
            attachment.read(reader)
            self.character_attachments.append(attachment)

    def write(self, writer):
        writer.write_uint(self.get_size())
        writer.write_string(self.name)
        writer.write_byte(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.head_id)
        writer.write_uint(self.model_id)
        writer.write_uint(self.gender)
        writer.write_uint(self.race)
        writer.write_uint(self.profile_id)
        writer.write_uint(self.unknown7)
        writer.write_ulong(self.unknown8)
        writer.write_uint(len(self.array_142c34c30))
        for value in self.array_142c34c30:
            writer.write_uint(value)
        self.model.write(writer)
        writer.write_uint(len(self.character_attachments))
        for attachment in self.character_attachments:
            attachment.write(writer)
        writer.write_uint(len(self.friends))
        for friend in self.friends:
            friend.write(writer)
        writer.write_ulong(self.unknown_q)


@dataclass
class SelectCharacter(Readable, Writable):
    character_id: int = 0
    last_server_id: int = 0
    last_login: float = 0.0
    status: int = 0
    character_data: CharacterPayload = field(default_factory=CharacterPayload)

    def read(self, reader):
        self.character_id = reader.read_ulong()
        self.last_server_id = reader.read_ulong()
        self.last_login = reader.read_double()
        self.status = reader.read_uint()
        self.character_data.read(reader)

    def write(self, writer):
        writer.write_ulong(self.character_id)
        writer.write_ulong(self.last_server_id)
        writer.write_double(self.last_login)
        writer.write_uint(self.status)
        self.character_data.write(writer)


@auth_message(AuthMessageOpcode.CharacterSelectInfoReply, LOGIN_10)
@dataclass
class CharacterSelectInfoReply(Readable, Writable):
    status: int = 0
    can_bypass_server_lock: bool = False
    characters: list[SelectCharacter] = field(default_factory=list)

    def read(self, reader):
        self.status = reader.read_uint()
        self.can_bypass_server_lock = reader.read_bool()
        for _ in range(reader.read_uint()):
            character = SelectCharacter()
            character.read(reader)
            self.characters.append(character)

    def write(self, writer):
        writer.write_uint(self.status)
        writer.write_bool(self.can_bypass_server_lock)
        writer.write_uint(len(self.characters))
        for character in self.characters:
            character.write(writer)


@dataclass
class CharacterAttachment9(Writable):
    model_name: str = ""
    texture_alias: str = ""
    semantic_tint: str = ""
    unknown3: str = ""
    unknown4: int = 0
    unknown5: int = 0
    slot: int = 0
    unknown7: int = 0

    def get_size(self):
        return (
            _str_size(self.model_name) + _str_size(self.texture_alias) + _str_size(self.semantic_tint)
            + _str_size(self.unknown3) + 4 + 4 + 4 + 4
        )

    def write(self, writer):
        writer.write_string(self.model_name)
        writer.write_string(self.texture_alias)
        writer.write_string(self.semantic_tint)
        writer.write_string(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.slot)
        writer.write_uint(self.unknown7)


@dataclass
class CharacterPayload9(Writable):
    name: str = "Kirmmin"
    unknown0: int = 0
    unknown1: int = 0
    head_id: int = 0
    model_id: int = 0
    gender: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    array_142c34c30: list[int] = field(default_factory=list)
    customizations: list[tuple[int, int, int]] = field(default_factory=list)
    skin_tint: int = 0
    character_attachments: list[CharacterAttachment9] = field(default_factory=list)
    friends: list = field(default_factory=list)
    unknown9: int = 0

    def get_size(self):
        total = 4 + 4 * len(self.array_142c34c30)
        total += 4 + 12 * len(self.customizations)
        total += 4 + sum(a.get_size() for a in self.character_attachments)
        total += 4 + sum(f.get_size() for f in self.friends)
        return total + _str_size(self.name) + 1 + 4 * 6 + 8 + 4 + 8

    def write(self, writer):
        writer.write_uint(self.get_size())
        writer.write_string(self.name)
        writer.write_byte(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.head_id)
        writer.write_uint(self.model_id)
        writer.write_uint(self.gender)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_ulong(self.unknown7)
        writer.write_uint(len(self.array_142c34c30))
        for value in self.array_142c34c30:
            writer.write_uint(value)
        writer.write_uint(len(self.customizations))
        for slot, option, tint in self.customizations:
            writer.write_uint(slot)
            writer.write_uint(option)
            writer.write_uint(tint)
        writer.write_uint(self.skin_tint)
        writer.write_uint(len(self.character_attachments))
        for attachment in self.character_attachments:
            attachment.write(writer)
        writer.write_uint(len(self.friends))
        for friend in self.friends:
            friend.write(writer)
        writer.write_ulong(self.unknown9)


@dataclass
class SelectCharacter9(Writable):
    character_id: int = 0
    last_server_id: int = 0
    last_login: float = 0.0
    status: int = 0
    character_data: CharacterPayload9 = field(default_factory=CharacterPayload9)

    def write(self, writer):
        writer.write_ulong(self.character_id)
        writer.write_ulong(self.last_server_id)
        writer.write_double(self.last_login)
        writer.write_uint(self.status)
        self.character_data.write(writer)


@auth_message(AuthMessageOpcode.CharacterSelectInfoReply, LOGIN_9)
@dataclass
class CharacterSelectInfoReply9(Writable):
    status: int = 0
    can_bypass_server_lock: bool = False
    characters: list[SelectCharacter9] = field(default_factory=list)

    def write(self, writer):
        writer.write_uint(self.status)
        writer.write_bool(self.can_bypass_server_lock)
        writer.write_uint(len(self.characters))
        for character in self.characters:
            character.write(writer)


@auth_message(AuthMessageOpcode.CharacterSelectInfoRequest, LOGIN_ALL)
@dataclass
class CharacterSelectInfoRequest(Readable):
    def read(self, reader):
        pass


# --- Character create / delete -------------------------------------------------------------


@auth_message(AuthMessageOpcode.CharacterCreateRequest, LOGIN_10)
@dataclass
class CharacterCreateRequest(Readable):
    server_id: int = 0
    unknown0: int = 0
    empire_id: int = 0
    profile_type_id: int = 0
    unknown1: int = 0
    name: str = ""
    customisation_options: list[tuple[int, int, int]] = field(default_factory=list)
    skin_tint: int = 0
    unknown2: int = 0
    race: int = 0
    gender: int = 0
    starting_outfit: int = 0

    def read(self, reader):
        self.server_id = reader.read_ulong()
        self.unknown0 = reader.read_uint()
        self.empire_id = reader.read_byte()
        self.profile_type_id = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.name = reader.read_string()
        for _ in range(reader.read_uint()):
            self.customisation_options.append((reader.read_uint(), reader.read_uint(), reader.read_uint()))
        self.skin_tint = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.race = reader.read_uint()
        self.gender = reader.read_uint()
        self.starting_outfit = reader.read_uint()


@auth_message(AuthMessageOpcode.CharacterCreateRequest, LOGIN_9)
@dataclass
class CharacterCreateRequest9(Readable):
    server_id: int = 0
    unknown0: int = 0
    empire_id: int = 0
    profile_type_id: int = 0
    gender: int = 0
    name: str = ""
    customisation_options: list[tuple[int, int, int]] = field(default_factory=list)
    skin_tint: int = 0

    def read(self, reader):
        self.server_id = reader.read_ulong()
        self.unknown0 = reader.read_uint()
        self.empire_id = reader.read_byte()
        self.profile_type_id = reader.read_uint()
        self.gender = reader.read_uint()
        self.name = reader.read_string()
        for _ in range(reader.read_uint()):
            self.customisation_options.append((reader.read_uint(), reader.read_uint(), reader.read_uint()))
        self.skin_tint = reader.read_uint()


@auth_message(AuthMessageOpcode.CharacterCreateReply, LOGIN_ALL)
@dataclass
class CharacterCreateReply(Readable, Writable):
    result: int = 0
    character_id: int = 0

    def read(self, reader):
        self.result = reader.read_uint()
        self.character_id = reader.read_ulong()

    def write(self, writer):
        writer.write_uint(self.result)
        writer.write_ulong(self.character_id)


@auth_message(AuthMessageOpcode.CharacterDeleteRequest, LOGIN_ALL)
@dataclass
class CharacterDeleteRequest(Readable):
    character_id: int = 0

    def read(self, reader):
        self.character_id = reader.read_ulong()


@auth_message(AuthMessageOpcode.CharacterDeleteReply, LOGIN_ALL)
@dataclass
class CharacterDeleteReply(Writable):
    character_id: int = 0
    status: int = 0
    payload: str = ""

    def write(self, writer):
        writer.write_ulong(self.character_id)
        writer.write_uint(self.status)
        writer.write_string(self.payload)


# --- Character login -----------------------------------------------------------------------


@dataclass
class ServerInfo(Readable, Writable):
    server_address: str = ""
    server_ticket: str = ""
    encryption_key: bytes = b""
    character_id: int = 0
    guid: int = 0
    account_name: str = ""
    character_name: str = ""
    unknown0: str = ""

    def get_size(self):
        return (
            _str_size(self.server_address) + _str_size(self.server_ticket) + 4 + len(self.encryption_key)
            + 8 + 8 + _str_size(self.account_name) + _str_size(self.character_name) + _str_size(self.unknown0)
        )

    def read(self, reader):
        reader.read_uint()  # Size
        self.server_address = reader.read_string()
        self.server_ticket = reader.read_string()
        self.encryption_key = reader.read_bytes(reader.read_uint())
        self.character_id = reader.read_ulong()
        self.guid = reader.read_ulong()
        self.account_name = reader.read_string()
        self.character_name = reader.read_string()
        self.unknown0 = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.get_size())
        writer.write_string(self.server_address)
        writer.write_string(self.server_ticket)
        writer.write_uint(len(self.encryption_key))
        writer.write_bytes(self.encryption_key)
        writer.write_ulong(self.character_id)
        writer.write_ulong(self.guid)
        writer.write_string(self.account_name)
        writer.write_string(self.character_name)
        writer.write_string(self.unknown0)


@auth_message(AuthMessageOpcode.CharacterLoginRequest, LOGIN_ALL)
@dataclass
class CharacterLoginRequest(Readable):
    character_id: int = 0
    server_id: int = 0
    unknown0: int = 0
    locale: str = ""
    unknown2: int = 0

    def read(self, reader):
        self.character_id = reader.read_ulong()
        self.server_id = reader.read_ulong()
        self.unknown0 = reader.read_uint()
        self.locale = reader.read_string()
        self.unknown2 = reader.read_ulong()


@auth_message(AuthMessageOpcode.CharacterLoginReply, LOGIN_ALL)
@dataclass
class CharacterLoginReply(Readable, Writable):
    character_id: int = 0
    server_id: int = 0
    result: int = 0
    server: ServerInfo = field(default_factory=ServerInfo)

    def read(self, reader):
        self.character_id = reader.read_ulong()
        self.server_id = reader.read_ulong()
        self.result = reader.read_uint()
        self.server.read(reader)

    def write(self, writer):
        writer.write_ulong(self.character_id)
        writer.write_ulong(self.server_id)
        writer.write_uint(self.result)
        self.server.write(writer)


# --- Tunnel --------------------------------------------------------------------------------


@dataclass
class TunnelPacket(Readable, Writable):
    server_id: int = 0
    type: int = 0
    data: TunnelData | None = None

    def read(self, reader):
        self.server_id = reader.read_ulong()
        reader.read_uint()  # Size of the tunnel data; not needed.
        self.type = reader.read_byte()
        self.data = new_tunnel_data(self.type)
        if self.data is None:
            return
        self.data.read(reader)

    def write(self, writer):
        writer.write_ulong(self.server_id)
        writer.write_uint(self.data.get_size() + 1)
        writer.write_byte(self.type)
        self.data.write(writer)


@auth_message(AuthMessageOpcode.TunnelPacketClientToServer, LOGIN_ALL)
@dataclass
class TunnelPacketClientToServer(TunnelPacket):
    pass


@auth_message(AuthMessageOpcode.TunnelPacketServerToClient, LOGIN_ALL)
@dataclass
class TunnelPacketServerToClient(TunnelPacket):
    pass

