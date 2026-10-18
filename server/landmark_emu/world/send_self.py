"""SendSelfToClient: the player's full state sent on zone login."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..shared.game.text import LandmarkText
from ..shared.network.message import CharacterModelInfo, Readable, Writable
from .message_manager import zone_message
from .opcodes import ZoneMessageOpcode
from .shared_structs import (
    Achievement,
    InventoryItem,
    Mount,
    RewardBundle,
    StatData,
    _read_list,
    _read_text,
    _write_list,
)

log = logging.getLogger("SendSelfToClient")

Vector4 = tuple[float, float, float, float]

# 34 trailing bytes present in captured packets that the client does not appear to read.
TRAILING_BYTES = bytes.fromhex(
    "00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-ff-ff-ff-ff-00-00-00-00-00-01-00-00-00-00-00-00-00".replace("-", "")
)


def _read_vector4(reader) -> Vector4:
    return (reader.read_single(), reader.read_single(), reader.read_single(), reader.read_single())


def _read_uints(reader) -> list[int]:
    return [reader.read_uint() for _ in range(reader.read_uint())]


def _write_uints(writer, items) -> None:
    writer.write_uint(len(items))
    for item in items:
        writer.write_uint(item)


@dataclass
class CharacterIdentity(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    first_name: str = "Player"
    last_name: str = ""

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.first_name = reader.read_string()
        self.last_name = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_string(self.first_name)
        writer.write_string(self.last_name)


@dataclass
class Profile(Readable, Writable):
    # Closely matches https://github.com/H1emu/h1z1-server (ClientProtocol_860 shared.ts).
    unknown0: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0
    unknown9: int = 0
    unknown10: list[tuple[int, int, int]] = field(default_factory=list)
    unknown11: int = 0
    unknown12: int = 0
    unknown13: int = 0
    unknown14: int = 0
    unknown15: bool = False
    unknown16: int = 0
    unknown17: int = 0
    unknown18: int = 0
    unknown19: float = 0.0
    unknown20: float = 0.0
    unknown21: float = 0.0
    unknown22: int = 0
    unknown23: float = 0.0
    unknown24: float = 0.0
    unknown25: int = 0
    unknown26: int = 0
    unknown27: int = 0
    unknown28: int = 0
    unknown29: int = 0
    unknown30: int = 0
    unknown31: int = 0
    unknown32: int = 0
    unknown33: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.name_id = _read_text(reader)
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_byte()
        self.unknown9 = reader.read_uint()
        for _ in range(reader.read_uint()):
            self.unknown10.append((reader.read_uint(), reader.read_uint(), reader.read_uint()))
        self.unknown11 = reader.read_byte()
        self.unknown12 = reader.read_uint()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_byte()
        self.unknown15 = reader.read_bool()
        self.unknown16 = reader.read_byte()
        self.unknown17 = reader.read_byte()
        self.unknown18 = reader.read_byte()
        # The original reads these float fields as uints (and converts the number); preserved.
        self.unknown19 = float(reader.read_uint())
        self.unknown20 = float(reader.read_uint())
        self.unknown21 = float(reader.read_uint())
        self.unknown22 = reader.read_uint()
        self.unknown23 = float(reader.read_uint())
        self.unknown24 = float(reader.read_uint())
        self.unknown25 = reader.read_uint()
        self.unknown26 = reader.read_uint()
        self.unknown27 = reader.read_uint()
        self.unknown28 = reader.read_uint()
        self.unknown29 = reader.read_uint()
        self.unknown30 = reader.read_uint()
        self.unknown31 = reader.read_uint()
        self.unknown32 = reader.read_uint()
        self.unknown33 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.name_id.write(writer)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)
        writer.write_byte(self.unknown8)
        writer.write_uint(self.unknown9)
        writer.write_uint(len(self.unknown10))
        for a, b, c in self.unknown10:
            writer.write_uint(a)
            writer.write_uint(b)
            writer.write_uint(c)
        writer.write_byte(self.unknown11)
        writer.write_uint(self.unknown12)
        writer.write_uint(self.unknown13)
        writer.write_byte(self.unknown14)
        writer.write_bool(self.unknown15)
        writer.write_byte(self.unknown16)
        writer.write_byte(self.unknown17)
        writer.write_byte(self.unknown18)
        writer.write_float(self.unknown19)
        writer.write_float(self.unknown20)
        writer.write_float(self.unknown21)
        writer.write_uint(self.unknown22)
        writer.write_float(self.unknown23)
        writer.write_float(self.unknown24)
        writer.write_uint(self.unknown25)
        writer.write_uint(self.unknown26)
        writer.write_uint(self.unknown27)
        writer.write_uint(self.unknown28)
        writer.write_uint(self.unknown29)
        writer.write_uint(self.unknown30)
        writer.write_uint(self.unknown31)
        writer.write_uint(self.unknown32)
        writer.write_uint(self.unknown33)


@dataclass
class Collection(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    reward_bundle_data: RewardBundle = field(default_factory=RewardBundle)
    # TODO (from the original): add the extra data.

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.reward_bundle_data.read(reader)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        self.reward_bundle_data.write(writer)


@dataclass
class Buff(Readable, Writable):
    unknown0: int = 0
    unit_id: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0
    unit_id2: int = 0
    unit_id3: int = 0
    unknown11: int = 0
    unknown12: int = 0
    unknown13: int = 0
    unknown14: int = 0
    unknown15: Vector4 = (0.0, 0.0, 0.0, 0.0)
    unknown16: int = 0
    unknown17: int = 0
    unknown18: int = 0
    unknown19: int = 0
    unknown20: int = 0
    unknown21: Vector4 = (0.0, 0.0, 0.0, 0.0)
    name_id: LandmarkText = field(default_factory=LandmarkText)
    description_id: LandmarkText = field(default_factory=LandmarkText)
    icon_id: int = 0
    unknown25: int = 0
    unknown26: bool = False
    unknown27: int = 0
    unknown28: int = 0
    unknown29: int = 0
    unknown30: int = 0
    unknown31: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unit_id = reader.read_ulong()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unit_id2 = reader.read_ulong()
        self.unit_id3 = reader.read_ulong()
        self.unknown11 = reader.read_uint()
        self.unknown12 = reader.read_ulong()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_uint()
        self.unknown15 = _read_vector4(reader)
        self.unknown16 = reader.read_uint()
        self.unknown17 = reader.read_uint()
        self.unknown18 = reader.read_uint()
        self.unknown19 = reader.read_uint()
        self.unknown20 = reader.read_uint()
        self.unknown21 = _read_vector4(reader)
        self.name_id = _read_text(reader)
        self.description_id = _read_text(reader)
        self.icon_id = reader.read_uint()
        self.unknown25 = reader.read_uint()
        self.unknown26 = reader.read_bool()
        self.unknown27 = reader.read_uint()
        self.unknown28 = reader.read_uint()
        self.unknown29 = reader.read_uint()
        self.unknown30 = reader.read_uint()
        self.unknown31 = reader.read_uint()

    def write(self, writer):
        writer.write_ulong(self.unknown0)
        writer.write_ulong(self.unit_id)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)
        writer.write_uint(self.unknown8)
        writer.write_ulong(self.unit_id2)
        writer.write_ulong(self.unit_id3)
        writer.write_uint(self.unknown11)
        writer.write_ulong(self.unknown12)
        writer.write_uint(self.unknown13)
        writer.write_uint(self.unknown14)
        writer.write_vector4(self.unknown15)
        writer.write_uint(self.unknown16)
        writer.write_uint(self.unknown17)
        writer.write_uint(self.unknown18)
        writer.write_uint(self.unknown19)
        writer.write_uint(self.unknown20)
        writer.write_vector4(self.unknown21)
        self.name_id.write(writer)
        self.description_id.write(writer)
        writer.write_uint(self.icon_id)
        # The original does not write unknown25; preserved for wire compatibility.
        writer.write_bool(self.unknown26)
        writer.write_uint(self.unknown27)
        writer.write_uint(self.unknown28)
        writer.write_uint(self.unknown29)
        writer.write_uint(self.unknown30)
        writer.write_uint(self.unknown31)


def _default_containers() -> list[tuple[int, bool]]:
    # Containers 7+ default to the current number of items in container 0. Fixed at 12.
    return [(40, False), (60, False), (10, False), (10, False), (10, False), (250, False), (250, False),
            (0, True), (0, True), (0, True), (0, True), (0, True)]


@dataclass
class InventoryData(Readable, Writable):
    containers: list[tuple[int, bool]] = field(default_factory=_default_containers)  # (max size, visible?)
    items: list[InventoryItem] = field(default_factory=list)

    def read(self, reader):
        self.containers = [(reader.read_uint(), reader.read_bool()) for _ in range(12)]
        self.items = _read_list(reader, InventoryItem)

    def write(self, writer):
        log.info("Writing %d containers", len(self.containers))
        for max_size, visible in self.containers:
            writer.write_uint(max_size)
            writer.write_bool(visible)
        _write_list(writer, self.items)


@dataclass
class QuestData(Readable, Writable):
    quest_list: int = 0
    unknown0: int = 0
    unknown1: int = 0
    unknown2: bool = False
    unknown3: int = 0
    unknown4: int = 0

    def read(self, reader):
        self.quest_list = reader.read_uint()
        if self.quest_list:
            raise NotImplementedError("Quest entries are not implemented.")
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_bool()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()

    def write(self, writer):
        # TODO (from the original): add support for quests.
        writer.write_uint(self.quest_list)
        if self.quest_list > 0:
            raise NotImplementedError("Quest entries are not implemented.")
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_bool(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)


# --- Recipes -------------------------------------------------------------------------------


@dataclass
class StructUnknown142C1B810(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_ulong()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_ulong(self.unknown2)


@dataclass
class RecipeComponent(Readable, Writable):
    index: int = 0
    unknown1: int = 0
    item_id: int = 0
    quantity: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)
    icon_id: int = 0
    unknown6: int = 0
    unknown7: int = 0

    def read(self, reader):
        self.index = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.item_id = reader.read_uint()
        self.quantity = reader.read_uint()
        self.name_id = _read_text(reader)
        self.icon_id = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.index)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.item_id)
        writer.write_uint(self.quantity)
        self.name_id.write(writer)
        writer.write_uint(self.icon_id)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)


@dataclass
class Recipe(Readable, Writable):
    recipe_id: int = 0
    unknown1: int = 0
    unknown2: int = 0
    item_id: int = 0
    quantity: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)
    description_id: LandmarkText = field(default_factory=LandmarkText)
    icon_id: int = 0
    unknown8: int = 0
    unknown9: int = 0  # Looks like a timestamp (acquired, or duration remaining).
    components: list[RecipeComponent] = field(default_factory=list)
    member_only: bool = False
    unknown12: int = 0  # Possibly the crafting station.
    unknown13: int = 0
    unknown14: int = 0
    unknown15: int = 0
    unknown16: list[int] = field(default_factory=list)
    unknown17: int = 0

    def read(self, reader):
        self.recipe_id = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.item_id = reader.read_uint()
        self.quantity = reader.read_uint()
        self.name_id = _read_text(reader)
        self.description_id = _read_text(reader)
        self.icon_id = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.components = _read_list(reader, RecipeComponent)
        self.member_only = reader.read_bool()
        self.unknown12 = reader.read_uint()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_uint()
        self.unknown15 = reader.read_uint()
        self.unknown16 = _read_uints(reader)
        self.unknown17 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.recipe_id)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.item_id)
        writer.write_uint(self.quantity)
        self.name_id.write(writer)
        self.description_id.write(writer)
        writer.write_uint(self.icon_id)
        writer.write_uint(self.unknown8)
        writer.write_uint(self.unknown9)
        _write_list(writer, self.components)
        writer.write_bool(self.member_only)
        writer.write_uint(self.unknown12)
        writer.write_uint(self.unknown13)
        writer.write_uint(self.unknown14)
        writer.write_uint(self.unknown15)
        _write_uints(writer, self.unknown16)
        writer.write_uint(self.unknown17)


@dataclass
class RecipeData(Readable, Writable):
    unknown0: list[int] = field(default_factory=list)
    unknown1: list[StructUnknown142C1B810] = field(default_factory=list)
    unknown2: list[int] = field(default_factory=list)
    recipe_list: list[Recipe] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = _read_uints(reader)
        self.unknown1 = _read_list(reader, StructUnknown142C1B810)
        self.unknown2 = _read_uints(reader)
        self.recipe_list = _read_list(reader, Recipe)

    def write(self, writer):
        _write_uints(writer, self.unknown0)
        _write_list(writer, self.unknown1)
        _write_uints(writer, self.unknown2)
        _write_list(writer, self.recipe_list)


# --- Hotbars / titles ----------------------------------------------------------------------


@dataclass
class HotbarButton(Readable, Writable):
    hotbar_id: int = 0
    slot_id: int = 0
    button_type: int = 0  # 0 = None, 1 = ItemId, 2 = ItemGuid
    item_id: int = 0

    def read(self, reader):
        self.hotbar_id = reader.read_uint()
        self.slot_id = reader.read_uint()
        self.button_type = reader.read_uint()
        self.item_id = reader.read_ulong()

    def write(self, writer):
        writer.write_uint(self.hotbar_id)
        writer.write_uint(self.slot_id)
        writer.write_uint(self.button_type)
        writer.write_ulong(self.item_id)


@dataclass
class Hotbar(Readable, Writable):
    hotbar_id: int = 0
    hotbar_buttons: list[HotbarButton] = field(default_factory=list)

    def read(self, reader):
        self.hotbar_id = reader.read_uint()
        self.hotbar_buttons = _read_list(reader, HotbarButton)

    def write(self, writer):
        writer.write_uint(self.hotbar_id)
        _write_list(writer, self.hotbar_buttons)


@dataclass
class Title(Readable, Writable):
    title_id: int = 0
    title_type: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)  # Localisation string id.

    def read(self, reader):
        self.title_id = reader.read_uint()
        self.title_type = reader.read_uint()
        self.name_id = _read_text(reader)

    def write(self, writer):
        writer.write_uint(self.title_id)
        writer.write_uint(self.title_type)
        self.name_id.write(writer)


@dataclass
class TitleData(Readable, Writable):
    title_list: list[Title] = field(default_factory=list)
    current_title_id: int = 0

    def read(self, reader):
        self.title_list = _read_list(reader, Title)
        self.current_title_id = reader.read_uint()

    def write(self, writer):
        _write_list(writer, self.title_list)
        writer.write_uint(self.current_title_id)


# --- Unknown structures --------------------------------------------------------------------


@dataclass
class _UIntPair(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)


class UnknownStruct50(_UIntPair):
    pass


class UnknownStruct57(_UIntPair):
    pass


@dataclass
class _FiveUInts(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)


class UnknownStruct58(_FiveUInts):
    pass


class UnknownStruct63(_FiveUInts):
    pass


class UnknownStruct142C1FA30(_FiveUInts):
    pass


@dataclass
class UnknownStruct142C3BF00(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_ulong()
        self.unknown4 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_ulong(self.unknown3)
        writer.write_uint(self.unknown4)


@dataclass
class UnknownStruct142C3F7F0(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_byte()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_ulong()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_byte()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_byte(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_ulong(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_byte(self.unknown6)


@dataclass
class UnknownStruct56(Readable, Writable):
    unknown0: list[UnknownStruct142C3BF00] = field(default_factory=list)
    unknown1: list[UnknownStruct142C3F7F0] = field(default_factory=list)
    unknown2: int = 128

    def read(self, reader):
        self.unknown0 = _read_list(reader, UnknownStruct142C3BF00)
        self.unknown1 = _read_list(reader, UnknownStruct142C3F7F0)
        self.unknown2 = reader.read_byte()

    def write(self, writer):
        _write_list(writer, self.unknown0)
        _write_list(writer, self.unknown1)
        writer.write_byte(self.unknown2)


@dataclass
class UnknownStruct59(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_ulong()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_ulong(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)


class UnknownStruct142C34E50(_UIntPair):
    pass


@dataclass
class UnknownStruct60(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: list[UnknownStruct142C34E50] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_ulong()
        self.unknown2 = _read_list(reader, UnknownStruct142C34E50)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_ulong(self.unknown1)
        _write_list(writer, self.unknown2)


@dataclass
class UnknownStruct142C1F840(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: str = ""
    unknown3: str = ""

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_ulong()
        self.unknown2 = reader.read_string()
        self.unknown3 = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_ulong(self.unknown1)
        writer.write_string(self.unknown2)
        writer.write_string(self.unknown3)


@dataclass
class UnknownStruct142C3BB80(Readable, Writable):
    unknown0: int = 0
    unknown1: UnknownStruct142C1F840 = field(default_factory=UnknownStruct142C1F840)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)


@dataclass
class UnknownStruct142C187F0(Readable, Writable):
    unknown0: int = 0
    unknown1: str = ""
    unknown2: str = ""
    unknown3: list[UnknownStruct142C3BB80] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_string()
        self.unknown2 = reader.read_string()
        self.unknown3 = _read_list(reader, UnknownStruct142C3BB80)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_string(self.unknown1)
        writer.write_string(self.unknown2)
        _write_list(writer, self.unknown3)


@dataclass
class UnknownStruct61(Readable, Writable):
    unknown0: int = 0
    unknown1: UnknownStruct142C187F0 = field(default_factory=UnknownStruct142C187F0)
    unknown2: list[UnknownStruct142C187F0] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)
        self.unknown2 = _read_list(reader, UnknownStruct142C187F0)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)
        _write_list(writer, self.unknown2)


@dataclass
class UnknownStruct62(Readable, Writable):
    unknown0: int = 0
    unknown1: UnknownStruct142C1FA30 = field(default_factory=UnknownStruct142C1FA30)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)


@dataclass
class UnknownStruct64(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)


@dataclass
class UnknownStruct142C25130(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_ulong()
        self.unknown3 = reader.read_ulong()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_ulong(self.unknown2)
        writer.write_ulong(self.unknown3)


@dataclass
class UnknownStruct142C3BC60(Readable, Writable):
    unknown0: int = 0
    unknown1: UnknownStruct142C25130 = field(default_factory=UnknownStruct142C25130)
    unknown2: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)
        self.unknown2 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)
        writer.write_uint(self.unknown2)


@dataclass
class UnknownStruct142C251E0(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_ulong()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_ulong(self.unknown2)


@dataclass
class UnknownStruct142C20DD0(Readable, Writable):
    unknown0: UnknownStruct142C251E0 = field(default_factory=UnknownStruct142C251E0)
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.unknown0.read(reader)
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()

    def write(self, writer):
        self.unknown0.write(writer)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)


@dataclass
class UnknownStruct142C3BDD0(Readable, Writable):
    unknown0: int = 0
    unknown1: UnknownStruct142C20DD0 = field(default_factory=UnknownStruct142C20DD0)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)


@dataclass
class UnknownStruct65(Readable, Writable):
    unknown0: UnknownStruct142C25130 = field(default_factory=UnknownStruct142C25130)
    unknown1: list[UnknownStruct142C3BC60] = field(default_factory=list)
    unknown2: UnknownStruct142C251E0 = field(default_factory=UnknownStruct142C251E0)
    unknown3: list[UnknownStruct142C3BDD0] = field(default_factory=list)
    unknown4: int = 128

    def read(self, reader):
        self.unknown0.read(reader)
        self.unknown1 = _read_list(reader, UnknownStruct142C3BC60)
        self.unknown2.read(reader)
        self.unknown3 = _read_list(reader, UnknownStruct142C3BDD0)
        self.unknown4 = reader.read_byte()

    def write(self, writer):
        self.unknown0.write(writer)
        _write_list(writer, self.unknown1)
        self.unknown2.write(writer)
        _write_list(writer, self.unknown3)
        writer.write_byte(self.unknown4)


@dataclass
class UnknownStruct142C217F0(Readable, Writable):
    unknown0: int = 1
    unknown1: int = 46
    unknown2: str = "Default Loadout"
    unknown3: int = 0
    unknown4: list[int] = field(default_factory=lambda: [0] * 4)
    unknown5: list[int] = field(default_factory=lambda: [0] * 5)
    unknown6: list[int] = field(default_factory=lambda: [0] * 16)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_string()
        self.unknown3 = reader.read_uint()
        self.unknown4 = _read_uints(reader)
        self.unknown5 = _read_uints(reader)
        self.unknown6 = [reader.read_ulong() for _ in range(reader.read_uint())]

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_string(self.unknown2)
        writer.write_uint(self.unknown3)
        _write_uints(writer, self.unknown4)
        _write_uints(writer, self.unknown5)
        writer.write_uint(len(self.unknown6))
        for value in self.unknown6:
            writer.write_ulong(value)


@dataclass
class Loadout(Readable, Writable):
    unknown0: int = 1
    unknown1: UnknownStruct142C217F0 = field(default_factory=UnknownStruct142C217F0)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1.read(reader)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)


@dataclass
class UnknownStruct67(Readable, Writable):
    # These are object lists in the packet, but always empty in captures, so only counts are kept.
    # TODO (from the original): implement the inner objects.
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0

    _FIELDS = ("unknown0", "unknown1", "unknown2", "unknown3", "unknown4")

    def read(self, reader):
        for name in self._FIELDS:
            count = reader.read_uint()
            setattr(self, name, count)
            if count:
                raise NotImplementedError(f"UnknownStruct67.{name} entries are not implemented.")

    def write(self, writer):
        for name in self._FIELDS:
            count = getattr(self, name)
            writer.write_uint(count)
            if count:
                raise NotImplementedError(f"UnknownStruct67.{name} entries are not implemented.")


@dataclass
class UnknownStruct68(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 1487581831
    unknown4: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unknown1 = reader.read_ulong()
        self.unknown2 = reader.read_ulong()
        self.unknown3 = reader.read_ulong()
        self.unknown4 = reader.read_uint()

    def write(self, writer):
        writer.write_ulong(self.unknown0)
        writer.write_ulong(self.unknown1)
        writer.write_ulong(self.unknown2)
        writer.write_ulong(self.unknown3)
        writer.write_uint(self.unknown4)


@dataclass
class UnknownStruct142C37990(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: str = ""
    unknown3: str = ""

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_string()
        self.unknown3 = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_string(self.unknown2)
        writer.write_string(self.unknown3)


@dataclass
class UnknownStruct76(Readable, Writable):
    unknown0: list[UnknownStruct142C37990] = field(default_factory=list)
    unknown1: int = 0

    def read(self, reader):
        self.unknown0 = _read_list(reader, UnknownStruct142C37990)
        self.unknown1 = reader.read_uint()

    def write(self, writer):
        _write_list(writer, self.unknown0)
        writer.write_uint(self.unknown1)


@zone_message(ZoneMessageOpcode.SendSelfToClient, prepend_size=True)
@dataclass
class SendSelfToClient(Readable, Writable):
    unknown0: int = 655356  # The prepended size when read from a capture.
    guid: int = 1000000
    account_name: str = "TestAccount"
    character_id: int = 0
    unknown1: int = 0
    last_login_time_raw: int = 0
    last_login_time: datetime | None = None  # Epoch timestamp of the last login.
    model_id: int = 0
    model: CharacterModelInfo = field(default_factory=CharacterModelInfo)
    unknown3: Vector4 = (0.0, 0.0, 0.0, 0.0)  # Probably position
    unknown4: Vector4 = (0.0, 0.0, 0.0, 0.0)  # Probably rotation
    identity: CharacterIdentity = field(default_factory=CharacterIdentity)
    unknown5: int = 0
    unknown6: list[tuple[int, int]] = field(default_factory=list)
    unknown7: int = 0
    unknown8: int = 0
    unknown9: int = 0  # The same data appears in TemplateBase (possibly coincidence).
    unknown10: bool = False
    unknown11: bool = False
    unknown12: bool = False
    unknown13: int = 0
    unknown14: bool = False
    unknown15: bool = False
    unknown16: int = 0
    unknown17: int = 0
    unknown18: int = 0
    unknown19: int = 0
    unknown20: int = 0
    unknown21: int = 0
    unknown22: int = 0
    unknown23: bool = False
    unknown24: list[tuple[int, int, int]] = field(default_factory=list)
    unknown25: bool = False
    unknown26: bool = False
    unknown27: bool = False
    unknown28: bool = False
    profiles: list[Profile] = field(default_factory=list)
    current_profile: int = 0
    unknown30: list[tuple[int, int]] = field(default_factory=list)
    collections: list[Collection] = field(default_factory=list)
    unknown31: list[tuple[int, int, int]] = field(default_factory=list)
    unknown32: int = 0
    buffs: list[Buff] = field(default_factory=list)
    inventory: InventoryData = field(default_factory=InventoryData)
    unknown35: int = 0
    gender_maybe: int = 0
    quests: QuestData = field(default_factory=QuestData)
    achievements: list[Achievement] = field(default_factory=list)
    acquaintances: int = 0
    recipes: RecipeData = field(default_factory=RecipeData)
    unknown40: list[int] = field(default_factory=list)
    unknown41: list[int] = field(default_factory=list)
    unknown42: list[int] = field(default_factory=list)
    hotbars: list[Hotbar] = field(default_factory=list)
    mounts: list[Mount] = field(default_factory=list)
    send_first_time_events: bool = False
    unknown46: list[int] = field(default_factory=list)
    unknown47: list[int] = field(default_factory=list)
    stats: list[tuple[int, StatData]] = field(default_factory=list)
    titles: TitleData = field(default_factory=TitleData)
    unknown50: list[UnknownStruct50] = field(default_factory=list)
    unknown51: list[int] = field(default_factory=list)
    unknown52: int = 0
    unknown53: list[int] = field(default_factory=list)
    unknown54: list[int] = field(default_factory=list)
    unknown55: list[bool] = field(default_factory=list)
    unknown56: UnknownStruct56 = field(default_factory=UnknownStruct56)
    unknown57: list[UnknownStruct57] = field(default_factory=list)
    unknown58: UnknownStruct58 = field(default_factory=UnknownStruct58)
    unknown59: list[UnknownStruct59] = field(default_factory=list)
    unknown60: list[UnknownStruct60] = field(default_factory=list)
    unknown61: list[UnknownStruct61] = field(default_factory=list)
    unknown62: list[UnknownStruct62] = field(default_factory=list)
    unknown63: UnknownStruct63 = field(default_factory=UnknownStruct63)
    unknown64: UnknownStruct64 = field(default_factory=UnknownStruct64)
    unknown65: UnknownStruct65 = field(default_factory=UnknownStruct65)
    loadouts: list[Loadout] = field(default_factory=lambda: [Loadout()])
    unknown67: UnknownStruct67 = field(default_factory=UnknownStruct67)
    unknown68: UnknownStruct68 = field(default_factory=UnknownStruct68)
    unknown69: int = 0
    unknown70: int = 0
    unknown71: int = 0
    unknown72: int = 0
    unknown73: int = 0
    unknown74: int = 0
    is_admin_maybe: bool = False
    unknown76: UnknownStruct76 = field(default_factory=UnknownStruct76)
    unknown77: str = ""

    # Client 0.589.x (e.g. 0.589.1.128895) has a different tail after unknown68: no unknown69-74,
    # unknown77 or trailing bytes, and the fields below instead (Landmark64.exe 0x142B80420).
    # The client crashes on purpose if the packet is not consumed exactly.
    client_0_589: bool = False
    unknown_0_589_0: list[tuple[int, int]] = field(default_factory=list)  # 0x142BA2610
    unknown_0_589_1: int = 0  # ulong and uint passed to 0x142ED6B30
    unknown_0_589_2: int = 0
    unknown_0_589_3: int = 0  # ulong, ulong, uint, uint passed to 0x142ED6AC0
    unknown_0_589_4: int = 0
    unknown_0_589_5: int = 0
    unknown_0_589_6: int = 0

    def _read_tail_0_589(self, reader):
        self.unknown_0_589_0 = [(reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())]
        self.unknown_0_589_1 = reader.read_ulong()
        self.unknown_0_589_2 = reader.read_uint()
        self.unknown_0_589_3 = reader.read_ulong()
        self.unknown_0_589_4 = reader.read_ulong()
        self.unknown_0_589_5 = reader.read_uint()
        self.unknown_0_589_6 = reader.read_uint()
        self.is_admin_maybe = reader.read_bool()
        self.unknown76.read(reader)

    def _write_tail_0_589(self, writer):
        writer.write_uint(len(self.unknown_0_589_0))
        for a, b in self.unknown_0_589_0:
            writer.write_uint(a)
            writer.write_uint(b)
        writer.write_ulong(self.unknown_0_589_1)
        writer.write_uint(self.unknown_0_589_2)
        writer.write_ulong(self.unknown_0_589_3)
        writer.write_ulong(self.unknown_0_589_4)
        writer.write_uint(self.unknown_0_589_5)
        writer.write_uint(self.unknown_0_589_6)
        writer.write_bool(self.is_admin_maybe)
        self.unknown76.write(writer)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.guid = reader.read_ulong()
        self.account_name = reader.read_string()
        self.character_id = reader.read_ulong()
        self.unknown1 = reader.read_uint_2bit_length()
        self.last_login_time_raw = reader.read_ulong()
        try:
            self.last_login_time = datetime.fromtimestamp(self.last_login_time_raw, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            self.last_login_time = None
        self.model_id = reader.read_uint()
        self.model.read(reader)
        self.unknown3 = _read_vector4(reader)
        self.unknown4 = _read_vector4(reader)
        self.identity.read(reader)
        self.unknown5 = reader.read_uint()
        self.unknown6 = [(reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())]
        self.unknown7 = reader.read_ulong()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.unknown10 = reader.read_bool()
        self.unknown11 = reader.read_bool()
        self.unknown12 = reader.read_bool()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_bool()
        self.unknown15 = reader.read_bool()
        self.unknown16 = reader.read_uint()
        self.unknown17 = reader.read_uint()
        self.unknown18 = reader.read_uint()
        self.unknown19 = reader.read_uint()
        self.unknown20 = reader.read_uint()
        self.unknown21 = reader.read_ulong()
        self.unknown22 = reader.read_uint()
        self.unknown23 = reader.read_bool()
        self.unknown24 = [
            (reader.read_uint(), reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())
        ]
        self.unknown25 = reader.read_bool()
        self.unknown26 = reader.read_bool()
        self.unknown27 = reader.read_bool()
        self.unknown28 = reader.read_bool()
        self.profiles = _read_list(reader, Profile)
        self.current_profile = reader.read_uint()
        self.unknown30 = [(reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())]
        self.collections = _read_list(reader, Collection)
        self.unknown31 = [
            (reader.read_uint(), reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())
        ]
        self.unknown32 = reader.read_uint()
        self.buffs = _read_list(reader, Buff)
        self.inventory.read(reader)

        self.unknown35 = reader.read_uint()
        if self.unknown35:
            raise NotImplementedError("Unknown34 entries are not implemented.")

        self.gender_maybe = reader.read_uint()
        self.quests.read(reader)
        self.achievements = _read_list(reader, Achievement)

        self.acquaintances = reader.read_uint()
        if self.acquaintances:
            raise NotImplementedError("Acquaintance entries are not implemented.")

        self.recipes.read(reader)
        self.unknown40 = _read_uints(reader)
        self.unknown41 = _read_uints(reader)
        self.unknown42 = _read_uints(reader)
        self.hotbars = _read_list(reader, Hotbar)
        self.mounts = _read_list(reader, Mount)
        self.send_first_time_events = reader.read_bool()
        self.unknown46 = _read_uints(reader)
        self.unknown47 = _read_uints(reader)

        self.stats = []
        for _ in range(reader.read_uint()):
            stat_id = reader.read_uint()
            stat = StatData()
            stat.read(reader)
            self.stats.append((stat_id, stat))

        self.titles.read(reader)
        self.unknown50 = _read_list(reader, UnknownStruct50)
        self.unknown51 = _read_uints(reader)
        self.unknown52 = reader.read_uint()
        self.unknown53 = _read_uints(reader)
        self.unknown54 = _read_uints(reader)
        self.unknown55 = [reader.read_bool() for _ in range(reader.read_uint())]
        self.unknown56.read(reader)
        self.unknown57 = _read_list(reader, UnknownStruct57)
        self.unknown58.read(reader)
        self.unknown59 = _read_list(reader, UnknownStruct59)
        self.unknown60 = _read_list(reader, UnknownStruct60)
        self.unknown61 = _read_list(reader, UnknownStruct61)
        self.unknown62 = _read_list(reader, UnknownStruct62)
        self.unknown63.read(reader)
        self.unknown64.read(reader)
        self.unknown65.read(reader)
        # The original appends to the default loadout list when reading.
        self.loadouts.extend(_read_list(reader, Loadout))
        self.unknown67.read(reader)
        self.unknown68.read(reader)
        if self.client_0_589:
            self._read_tail_0_589(reader)
        else:
            self.unknown69 = reader.read_byte()
            self.unknown70 = reader.read_byte()
            self.unknown71 = reader.read_byte()
            self.unknown72 = reader.read_byte()
            self.unknown73 = reader.read_byte()
            self.unknown74 = reader.read_byte()
            self.is_admin_maybe = reader.read_bool()
            self.unknown76.read(reader)
            self.unknown77 = reader.read_string()

            reader.read_bytes(len(TRAILING_BYTES))

        read = reader.total_bytes - reader.bytes_remaining
        log.info("%d / %d (%.2f%%) Bytes Read", read, reader.total_bytes, read / reader.total_bytes * 100.0)

    def write(self, writer):
        # unknown0 is not written: it is the size, which is prepended separately.
        writer.write_ulong(self.guid)
        writer.write_string(self.account_name)
        writer.write_ulong(self.character_id)
        writer.write_uint_with_2bit_length(self.unknown1)
        writer.write_ulong(self.last_login_time_raw)  # TODO (from the original): write the timestamp.
        writer.write_uint(self.model_id)
        self.model.write(writer)
        writer.write_vector4(self.unknown3)
        writer.write_vector4(self.unknown4)
        self.identity.write(writer)
        writer.write_uint(self.unknown5)
        writer.write_uint(len(self.unknown6))
        for a, b in self.unknown6:
            writer.write_uint(a)
            writer.write_uint(b)
        writer.write_ulong(self.unknown7)
        writer.write_uint(self.unknown8)
        writer.write_uint(self.unknown9)
        writer.write_bool(self.unknown10)
        writer.write_bool(self.unknown11)
        writer.write_bool(self.unknown12)
        writer.write_uint(self.unknown13)
        writer.write_bool(self.unknown14)
        writer.write_bool(self.unknown15)
        writer.write_uint(self.unknown16)
        writer.write_uint(self.unknown17)
        writer.write_uint(self.unknown18)
        writer.write_uint(self.unknown19)
        writer.write_uint(self.unknown20)
        writer.write_ulong(self.unknown21)
        writer.write_uint(self.unknown22)
        writer.write_bool(self.unknown23)
        writer.write_uint(len(self.unknown24))
        for a, b, c in self.unknown24:
            writer.write_uint(a)
            writer.write_uint(b)
            writer.write_uint(c)
        writer.write_bool(self.unknown25)
        writer.write_bool(self.unknown26)
        writer.write_bool(self.unknown27)
        writer.write_bool(self.unknown28)
        _write_list(writer, self.profiles)
        writer.write_uint(self.current_profile)
        writer.write_uint(len(self.unknown30))
        for a, b in self.unknown30:
            writer.write_uint(a)
            writer.write_uint(b)
        _write_list(writer, self.collections)
        writer.write_uint(len(self.unknown31))
        for a, b, c in self.unknown31:
            writer.write_uint(a)
            writer.write_uint(b)
            writer.write_uint(c)
        writer.write_uint(self.unknown32)
        _write_list(writer, self.buffs)
        self.inventory.write(writer)

        writer.write_uint(self.unknown35)
        if self.unknown35:
            raise NotImplementedError("Unknown34 entries are not implemented.")

        writer.write_uint(self.gender_maybe)
        self.quests.write(writer)
        _write_list(writer, self.achievements)

        writer.write_uint(self.acquaintances)
        if self.acquaintances:
            raise NotImplementedError("Acquaintance entries are not implemented.")

        self.recipes.write(writer)
        _write_uints(writer, self.unknown40)
        _write_uints(writer, self.unknown41)
        _write_uints(writer, self.unknown42)
        _write_list(writer, self.hotbars)
        _write_list(writer, self.mounts)
        writer.write_bool(self.send_first_time_events)
        _write_uints(writer, self.unknown46)
        _write_uints(writer, self.unknown47)
        writer.write_uint(len(self.stats))
        for stat_id, stat in self.stats:
            writer.write_uint(stat_id)
            stat.write(writer)
        self.titles.write(writer)
        _write_list(writer, self.unknown50)
        _write_uints(writer, self.unknown51)
        writer.write_uint(self.unknown52)
        _write_uints(writer, self.unknown53)
        _write_uints(writer, self.unknown54)
        writer.write_uint(len(self.unknown55))
        for value in self.unknown55:
            writer.write_bool(value)
        self.unknown56.write(writer)
        _write_list(writer, self.unknown57)
        self.unknown58.write(writer)
        _write_list(writer, self.unknown59)
        _write_list(writer, self.unknown60)
        _write_list(writer, self.unknown61)
        _write_list(writer, self.unknown62)
        self.unknown63.write(writer)
        self.unknown64.write(writer)
        self.unknown65.write(writer)
        _write_list(writer, self.loadouts)
        self.unknown67.write(writer)
        self.unknown68.write(writer)
        if self.client_0_589:
            self._write_tail_0_589(writer)
            return
        writer.write_byte(self.unknown69)
        writer.write_byte(self.unknown70)
        writer.write_byte(self.unknown71)
        writer.write_byte(self.unknown72)
        writer.write_byte(self.unknown73)
        writer.write_byte(self.unknown74)
        writer.write_bool(self.is_admin_maybe)
        self.unknown76.write(writer)
        writer.write_string(self.unknown77)
        writer.write_bytes(TRAILING_BYTES)
