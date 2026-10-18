"""Zone messages (other than SendSelfToClient)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.network.message import Readable, Writable
from .message_manager import zone_message
from .opcodes import ZoneMessageOpcode as Op
from .shared_structs import Sky


@zone_message(Op.AbilityCasterInfoRequest)
@dataclass
class AbilityCasterInfoRequest(Readable):
    unknown0: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()


@zone_message(Op.AbilityDefaultInfoRequest)
@dataclass
class AbilityDefaultInfoRequest(Readable):
    def read(self, reader):
        pass


@zone_message(Op.ClientBeginZoning)
@dataclass
class ClientBeginZoning(Readable, Writable):
    zone_name: str = ""
    zone_type: int = 0
    position: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])
    sky_xml: str = ""
    unknown3: int = 0
    world_id: int = 0
    world_name_id: int = 0
    zone_id: int = 0
    zone_name_id: int = 0
    unknown8: int = 0
    unknown9: int = 0
    unknown10: bool = False
    unknown11: bool = False
    sky_data: Sky = field(default_factory=Sky)

    def read(self, reader):
        self.zone_name = reader.read_string()
        self.zone_type = reader.read_uint()
        self.position = [reader.read_single() for _ in range(4)]
        self.rotation = [reader.read_single() for _ in range(4)]
        self.sky_xml = reader.read_string()
        self.unknown3 = reader.read_byte()
        self.world_id = reader.read_uint()
        self.world_name_id = reader.read_uint()
        self.zone_id = reader.read_uint()
        self.zone_name_id = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.unknown10 = reader.read_bool()
        self.unknown11 = reader.read_bool()
        self.sky_data.read(reader)

    def write(self, writer):
        writer.write_string(self.zone_name)
        writer.write_uint(self.zone_type)
        for value in self.position:
            writer.write_float(value)
        for value in self.rotation:
            writer.write_float(value)
        writer.write_string(self.sky_xml)
        writer.write_byte(self.unknown3)
        writer.write_uint(self.world_id)
        writer.write_uint(self.world_name_id)
        writer.write_uint(self.zone_id)
        writer.write_uint(self.zone_name_id)
        writer.write_uint(self.unknown8)
        writer.write_uint(self.unknown9)
        writer.write_bool(self.unknown10)
        writer.write_bool(self.unknown11)
        self.sky_data.write(writer)


@zone_message(Op.ClientFinishedLoading)
@dataclass
class ClientFinishedLoading(Readable):
    def read(self, reader):
        pass


@zone_message(Op.ClientGameSettings)
@dataclass
class ClientGameSettings(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: bool = False
    unknown6: float = 0.0
    unknown7: float = 0.0
    unknown8: float = 0.0
    unknown9: float = 0.0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_bool()
        self.unknown6 = reader.read_single()
        self.unknown7 = reader.read_single()
        self.unknown8 = reader.read_single()
        self.unknown9 = reader.read_single()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_bool(self.unknown5)
        writer.write_float(self.unknown6)
        writer.write_float(self.unknown7)
        writer.write_float(self.unknown8)
        writer.write_float(self.unknown9)


@zone_message(Op.ClientIsReady)
@dataclass
class ClientIsReady(Readable):
    def read(self, reader):
        pass


@zone_message(Op.ClientLog)
@dataclass
class ClientLog(Readable):
    file: str = ""
    message: str = ""

    def read(self, reader):
        self.file = reader.read_string()
        self.message = reader.read_string()


@zone_message(Op.ClientUpdateDoneSendingPreloadCharacters)
@dataclass
class ClientUpdateDoneSendingPreloadCharacters(Writable):
    def write(self, writer):
        writer.write_byte(0)


@dataclass
class RespawnLocation(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unknown1 = reader.read_byte()
        self.unknown2 = reader.read_ulong()
        self.unknown3 = reader.read_ulong()
        self.unknown4 = reader.read_ulong()
        self.unknown5 = reader.read_ulong()
        self.unknown6 = reader.read_ulong()
        self.unknown7 = reader.read_ulong()
        self.unknown8 = reader.read_ushort()

    def write(self, writer):
        pass  # Not implemented in the original.


@zone_message(Op.ClientUpdateRespawnLocations)
@dataclass
class ClientUpdateRespawnLocations(Readable, Writable):
    respawn_locations: list[RespawnLocation] = field(default_factory=list)

    def read(self, reader):
        for _ in range(reader.read_uint()):
            location = RespawnLocation()
            location.read(reader)
            self.respawn_locations.append(location)

    def write(self, writer):
        pass  # Not implemented in the original.


@zone_message(Op.ClientUpdateZonePopulation)
@dataclass
class ClientUpdateZonePopulation(Readable, Writable):
    populations: list[int] = field(default_factory=list)
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.populations = [reader.read_byte() for _ in range(reader.read_uint())]
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(len(self.populations))
        for value in self.populations:
            writer.write_byte(value)
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)


@zone_message(Op.GameTimeSync)
@dataclass
class GameTimeSync(Readable, Writable):
    time: float = 0.0
    cycle_speed: float = 0.0
    unknown0: bool = False

    def read(self, reader):
        self.time = reader.read_double()
        self.cycle_speed = reader.read_single()
        self.unknown0 = reader.read_bool()

    def write(self, writer):
        writer.write_double(self.time)
        writer.write_float(self.cycle_speed)
        writer.write_bool(self.unknown0)


@zone_message(Op.InitializationParameters)
@dataclass
class InitializationParameters(Readable, Writable):
    environment: str = ""

    def read(self, reader):
        self.environment = reader.read_string()

    def write(self, writer):
        writer.write_string(self.environment)


@zone_message(Op.KeepAlive)
@dataclass
class KeepAlive(Readable, Writable):
    game_time: int = 0

    def read(self, reader):
        self.game_time = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.game_time)


@zone_message(Op.PlayerUpdateBindingCustomization)
@dataclass
class PlayerUpdateBindingCustomization(Readable):
    def read(self, reader):
        pass


@zone_message(Op.PlayerUpdateSetPlayerBio)
@dataclass
class PlayerUpdateSetPlayerBio(Readable, Writable):
    def read(self, reader):
        pass

    def write(self, writer):
        pass


@zone_message(Op.ReferenceDataItemCategoryDefinitions)
@dataclass
class ReferenceDataItemCategoryDefinitions(Readable, Writable):
    categories: list[int] = field(default_factory=list)

    def read(self, reader):
        reader.read_uint()  # Category count; categories are not parsed by the original.

    def write(self, writer):
        writer.write_uint(len(self.categories))


@zone_message(Op.ReferenceDataItemClassDefinitions)
@dataclass
class ReferenceDataItemClassDefinitions(Readable, Writable):
    classes: list[int] = field(default_factory=list)

    def read(self, reader):
        reader.read_uint()  # Class count; classes are not parsed by the original.

    def write(self, writer):
        writer.write_uint(len(self.classes))


@dataclass
class ReferenceProfile(Readable, Writable):
    def read(self, reader):
        pass

    def write(self, writer):
        pass


@zone_message(Op.ReferenceDataProfileDefinitions)
@dataclass
class ReferenceDataProfileDefinitions(Readable, Writable):
    profiles: list[ReferenceProfile] = field(default_factory=list)

    def read(self, reader):
        for _ in range(reader.read_uint()):
            profile = ReferenceProfile()
            profile.read(reader)
            self.profiles.append(profile)

    def write(self, writer):
        writer.write_uint(len(self.profiles))


@zone_message(Op.SendZoneDetails)
@dataclass
class SendZoneDetails(Readable, Writable):
    unknown0: str = ""
    unknown1: int = 0
    unknown2: bool = False
    unknown3: str = ""
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0
    unknown9: int = 0
    sky_data: Sky = field(default_factory=Sky)

    def read(self, reader):
        self.unknown0 = reader.read_string()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_bool()
        self.unknown3 = reader.read_string()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_ulong()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.sky_data.read(reader)

    def write(self, writer):
        pass  # Not implemented in the original; the captured payload is sent instead.


@zone_message(Op.Synchronization)
@dataclass
class Synchronization(Readable, Writable):
    time1: float = 0.0
    time2: float = 0.0
    client_time: float = 0.0
    server_time: float = 0.0
    server_time2: float = 0.0
    time3: float = 0.0
    unknown0: bool = False

    def read(self, reader):
        self.time1 = reader.read_double()
        self.time2 = reader.read_double()
        self.client_time = reader.read_double()
        self.server_time = reader.read_double()
        self.server_time2 = reader.read_double()
        self.time3 = reader.read_double()
        self.unknown0 = reader.read_bool()

    def write(self, writer):
        writer.write_double(self.time1)
        writer.write_double(self.time2)
        writer.write_double(self.client_time)
        writer.write_double(self.server_time)
        writer.write_double(self.server_time2)
        writer.write_double(self.time3)
        writer.write_bool(self.unknown0)


@zone_message(Op.ZoneDoneSendingInitialData)
@dataclass
class ZoneDoneSendingInitialData(Writable):
    def write(self, writer):
        pass
