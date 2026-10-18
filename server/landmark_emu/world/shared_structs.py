"""Structures shared by several zone messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.game.text import LandmarkText
from ..shared.network.message import Readable, Writable


def _read_list(reader, item_type):
    items = []
    for _ in range(reader.read_uint()):
        item = item_type()
        item.read(reader)
        items.append(item)
    return items


def _write_list(writer, items):
    writer.write_uint(len(items))
    for item in items:
        item.write(writer)


def _read_text(reader) -> LandmarkText:
    text = LandmarkText()
    text.read(reader)
    return text


@dataclass
class Sky(Readable, Writable):
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: str = ""
    unknown5: str = ""
    unknown6: int = 0
    unknown7: list[float] = field(default_factory=lambda: [0.0] * 3)
    unknown8: list[float] = field(default_factory=lambda: [0.0] * 3)
    unknown9: bool = False
    unknown10: bool = False
    unknown11: str = ""
    unknown12: int = 0
    unknown13: str = ""
    unknown14: int = 0
    unknown15: str = ""
    unknown16: int = 0
    unknown17: int = 0
    unknown18: int = 0
    unknown19: int = 0
    unknown20: int = 0
    unknown21: int = 0
    unknown22: list[int] = field(default_factory=lambda: [0] * 4)
    unknown23: int = 0
    unknown24: int = 0
    unknown25: int = 0
    unknown26: int = 0
    unknown27: int = 0
    unknown28: int = 0
    unknown29: int = 0
    unknown30: bool = False
    unknown31: int = 0
    unknown32: bool = False
    unknown33: int = 0
    unknown34: int = 0
    unknown35: int = 0
    unknown36: str = ""

    def read(self, reader):
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_string()
        self.unknown5 = reader.read_string()
        self.unknown6 = reader.read_ulong()
        self.unknown7 = [reader.read_double() for _ in range(3)]
        self.unknown8 = [reader.read_double() for _ in range(3)]
        self.unknown9 = reader.read_bool()
        self.unknown10 = reader.read_bool()
        self.unknown11 = reader.read_string()
        self.unknown12 = reader.read_uint()
        self.unknown13 = reader.read_string()
        self.unknown14 = reader.read_uint()
        self.unknown15 = reader.read_string()
        self.unknown16 = reader.read_uint()
        self.unknown17 = reader.read_uint()
        self.unknown18 = reader.read_uint()
        self.unknown19 = reader.read_uint()
        self.unknown20 = reader.read_uint()
        self.unknown21 = reader.read_uint()
        self.unknown22 = [reader.read_uint() for _ in range(4)]
        self.unknown23 = reader.read_uint()
        self.unknown24 = reader.read_uint()
        self.unknown25 = reader.read_uint()
        self.unknown26 = reader.read_uint()
        self.unknown27 = reader.read_ulong()
        self.unknown28 = reader.read_uint()
        self.unknown29 = reader.read_uint()
        self.unknown30 = reader.read_bool()
        self.unknown31 = reader.read_uint()
        self.unknown32 = reader.read_bool()
        self.unknown33 = reader.read_uint()
        self.unknown34 = reader.read_uint()
        self.unknown35 = reader.read_uint()
        self.unknown36 = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_string(self.unknown4)
        writer.write_string(self.unknown5)
        writer.write_ulong(self.unknown6)
        for value in self.unknown7:
            writer.write_double(value)
        for value in self.unknown8:
            writer.write_double(value)
        writer.write_bool(self.unknown9)
        writer.write_bool(self.unknown10)
        writer.write_string(self.unknown11)
        writer.write_uint(self.unknown12)
        writer.write_string(self.unknown13)
        writer.write_uint(self.unknown14)
        writer.write_string(self.unknown15)
        writer.write_uint(self.unknown16)
        writer.write_uint(self.unknown17)
        writer.write_uint(self.unknown18)
        writer.write_uint(self.unknown19)
        writer.write_uint(self.unknown20)
        writer.write_uint(self.unknown21)
        for value in self.unknown22:
            writer.write_uint(value)
        writer.write_uint(self.unknown23)
        writer.write_uint(self.unknown24)
        writer.write_uint(self.unknown25)
        writer.write_uint(self.unknown26)
        writer.write_ulong(self.unknown27)
        writer.write_uint(self.unknown28)
        writer.write_uint(self.unknown29)
        writer.write_bool(self.unknown30)
        writer.write_uint(self.unknown31)
        writer.write_bool(self.unknown32)
        writer.write_uint(self.unknown33)
        writer.write_uint(self.unknown34)
        writer.write_uint(self.unknown35)
        writer.write_string(self.unknown36)


@dataclass
class StatData(Readable, Writable):
    stat_id: int = 0
    type: int = 0
    base: float = 0.0
    modifier: float = 0.0

    def read(self, reader):
        self.stat_id = reader.read_uint()
        self.type = reader.read_byte()
        if self.type == 0:
            self.base = float(reader.read_uint())
            self.modifier = float(reader.read_uint())
        else:
            self.base = reader.read_single()
            self.modifier = reader.read_single()

    def write(self, writer):
        writer.write_uint(self.stat_id)
        writer.write_byte(self.type)
        if self.type == 0:
            writer.write_uint(int(self.base))
            writer.write_uint(int(self.modifier))
        else:
            writer.write_float(self.base)
            writer.write_float(self.modifier)


@dataclass
class Mount(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: bool = False
    unknown5: int = 0
    unknown6: str = ""

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_ulong()
        self.unknown4 = reader.read_bool()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_string()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_ulong(self.unknown3)
        writer.write_bool(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_string(self.unknown6)


# --- RewardBundle --------------------------------------------------------------------------


@dataclass
class Currency(Readable, Writable):
    currency_id: int = 0
    quantity: int = 0

    def read(self, reader):
        self.currency_id = reader.read_uint()
        self.quantity = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.currency_id)
        writer.write_uint(self.quantity)


@dataclass
class BundleRewardEntry(Readable, Writable):
    type: int = 0
    data: bytes = b""

    def read(self, reader):
        self.type = reader.read_uint()
        if self.type == 1:
            # TODO (from the original): always 42 bytes when type is 1; other types are unknown.
            self.data = reader.read_bytes(42)

    def write(self, writer):
        writer.write_uint(self.type)
        if self.type == 1:
            writer.write_bytes(self.data)


@dataclass
class RewardBundle(Readable, Writable):
    unknown0: bool = False
    unknown1: int = 0
    currencies: list[Currency] = field(default_factory=list)
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0
    unknown9: int = 0
    unknown10: int = 0
    unknown11: int = 0
    character_id: int = 0
    unknown13: int = 0
    unknown14: int = 0
    bundle_reward_entries: list[BundleRewardEntry] = field(default_factory=list)
    unknown16: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_bool()
        self.unknown1 = reader.read_uint()
        self.currencies = _read_list(reader, Currency)
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = reader.read_ulong()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.unknown10 = reader.read_uint()
        self.unknown11 = reader.read_ulong()
        self.character_id = reader.read_ulong()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_uint()
        self.bundle_reward_entries = _read_list(reader, BundleRewardEntry)
        self.unknown16 = reader.read_uint()

    def write(self, writer):
        writer.write_bool(self.unknown0)
        writer.write_uint(self.unknown1)
        _write_list(writer, self.currencies)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        writer.write_ulong(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)
        writer.write_uint(self.unknown8)
        writer.write_uint(self.unknown9)
        writer.write_uint(self.unknown10)
        writer.write_ulong(self.unknown11)
        writer.write_ulong(self.character_id)
        writer.write_uint(self.unknown13)
        writer.write_uint(self.unknown14)
        _write_list(writer, self.bundle_reward_entries)
        writer.write_uint(self.unknown16)


# --- Objective / Achievement ---------------------------------------------------------------


@dataclass
class UnknownStruct142C22E30(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)


@dataclass
class Objective(Readable, Writable):
    objective_id: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)
    description_id: LandmarkText = field(default_factory=LandmarkText)
    objective_reward_bundle: RewardBundle = field(default_factory=RewardBundle)
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0
    unknown8: int = 0
    unknown9: int = 0
    unknown10: int = 0
    unknown11: UnknownStruct142C22E30 = field(default_factory=UnknownStruct142C22E30)
    unknown12: int = 0
    unknown13: int = 0

    def read(self, reader):
        self.objective_id = reader.read_uint()
        self.name_id = _read_text(reader)
        self.description_id = _read_text(reader)
        self.objective_reward_bundle.read(reader)
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_uint()
        self.unknown10 = reader.read_uint()
        self.unknown11.read(reader)
        self.unknown12 = reader.read_byte()
        self.unknown13 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.objective_id)
        self.name_id.write(writer)
        self.description_id.write(writer)
        self.objective_reward_bundle.write(writer)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)
        writer.write_uint(self.unknown8)
        writer.write_uint(self.unknown9)
        writer.write_uint(self.unknown10)
        self.unknown11.write(writer)
        writer.write_byte(self.unknown12)
        writer.write_uint(self.unknown13)


@dataclass
class ObjectiveEntry(Readable, Writable):
    index: int = 0
    objective: Objective = field(default_factory=Objective)

    def read(self, reader):
        self.index = reader.read_uint()
        self.objective.read(reader)

    def write(self, writer):
        writer.write_uint(self.index)
        self.objective.write(writer)


@dataclass
class UnknownStruct142C34B60(Readable, Writable):
    unknown0: list[int] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = [reader.read_uint() for _ in range(reader.read_uint())]

    def write(self, writer):
        writer.write_uint(len(self.unknown0))
        for item in self.unknown0:
            writer.write_uint(item)


@dataclass
class UnknownStruct142C23120(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)


@dataclass
class UnknownStruct142C39F80(Readable, Writable):
    unknown0: list[UnknownStruct142C23120] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = _read_list(reader, UnknownStruct142C23120)

    def write(self, writer):
        _write_list(writer, self.unknown0)


@dataclass
class UnknownStruct142C363D0(Readable, Writable):
    unknown0: list[tuple[int, UnknownStruct142C39F80]] = field(default_factory=list)

    def read(self, reader):
        for _ in range(reader.read_uint()):
            key = reader.read_uint()
            value = UnknownStruct142C39F80()
            value.read(reader)
            self.unknown0.append((key, value))

    def write(self, writer):
        writer.write_uint(len(self.unknown0))
        for key, value in self.unknown0:
            writer.write_uint(key)
            value.write(writer)


@dataclass
class UnknownStruct142C34F90(Readable, Writable):
    unknown0: list[tuple[int, int]] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = [(reader.read_uint(), reader.read_uint()) for _ in range(reader.read_uint())]

    def write(self, writer):
        writer.write_uint(len(self.unknown0))
        for a, b in self.unknown0:
            writer.write_uint(a)
            writer.write_uint(b)


@dataclass
class Achievement(Readable, Writable):
    achievement_id: int = 0
    unknown1: int = 0
    name_id: LandmarkText = field(default_factory=LandmarkText)
    description_id: LandmarkText = field(default_factory=LandmarkText)
    time_started: int = 0
    time_finished: int = 0
    progress: float = 0.0
    achievement_reward_bundle: RewardBundle = field(default_factory=RewardBundle)
    objective_count: int = 0
    achievement_objectives: list[ObjectiveEntry] = field(default_factory=list)
    unknown9: int = 0
    unknown10: int = 0
    unknown11: int = 0
    unknown12: int = 0
    unknown13: int = 0
    unknown14: int = 0
    unknown15: int = 0
    unknown16: bool = False
    unknown17: int = 0
    unknown18: int = 0
    unknown19: int = 0
    unknown20: int = 0
    unknown21: int = 0
    unknown22: int = 0
    unknown23: int = 0
    unknown24: int = 0
    unknown25: int = 0
    unknown26: int = 0
    unknown27: bool = False
    unknown28: bool = False
    unknown29: bool = False
    unknown30: UnknownStruct142C34B60 = field(default_factory=UnknownStruct142C34B60)
    unknown31: UnknownStruct142C363D0 = field(default_factory=UnknownStruct142C363D0)
    unknown32: UnknownStruct142C34F90 = field(default_factory=UnknownStruct142C34F90)
    unknown33: int = 0

    def read(self, reader):
        self.achievement_id = reader.read_uint()
        self.unknown1 = reader.read_byte()
        self.name_id = _read_text(reader)
        self.description_id = _read_text(reader)
        self.time_started = reader.read_ulong()
        self.time_finished = reader.read_ulong()
        self.progress = reader.read_single()
        self.achievement_reward_bundle.read(reader)
        self.objective_count = reader.read_uint()
        for _ in range(self.objective_count):
            entry = ObjectiveEntry()
            entry.read(reader)
            self.achievement_objectives.append(entry)
        self.unknown9 = reader.read_uint()
        self.unknown10 = reader.read_uint()
        self.unknown11 = reader.read_uint()
        self.unknown12 = reader.read_uint()
        self.unknown13 = reader.read_uint()
        self.unknown14 = reader.read_byte()
        self.unknown15 = reader.read_uint()
        self.unknown16 = reader.read_bool()
        self.unknown17 = reader.read_uint()
        self.unknown18 = reader.read_uint()
        self.unknown19 = reader.read_uint()
        self.unknown20 = reader.read_uint()
        self.unknown21 = reader.read_uint()
        self.unknown22 = reader.read_uint()
        self.unknown23 = reader.read_uint()
        self.unknown24 = reader.read_uint()
        self.unknown25 = reader.read_uint()
        self.unknown26 = reader.read_uint()
        self.unknown27 = reader.read_bool()
        self.unknown28 = reader.read_bool()
        self.unknown29 = reader.read_bool()
        self.unknown30.read(reader)
        self.unknown31.read(reader)
        self.unknown32.read(reader)
        self.unknown33 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.achievement_id)
        writer.write_byte(self.unknown1)
        self.name_id.write(writer)
        self.description_id.write(writer)
        writer.write_ulong(self.time_started)
        writer.write_ulong(self.time_finished)
        writer.write_float(self.progress)
        self.achievement_reward_bundle.write(writer)
        _write_list(writer, self.achievement_objectives)
        writer.write_uint(self.unknown9)
        writer.write_uint(self.unknown10)
        writer.write_uint(self.unknown11)
        writer.write_uint(self.unknown12)
        writer.write_uint(self.unknown13)
        writer.write_byte(self.unknown14)
        writer.write_uint(self.unknown15)
        writer.write_bool(self.unknown16)
        writer.write_uint(self.unknown17)
        writer.write_uint(self.unknown18)
        writer.write_uint(self.unknown19)
        writer.write_uint(self.unknown20)
        writer.write_uint(self.unknown21)
        writer.write_uint(self.unknown22)
        writer.write_uint(self.unknown23)
        writer.write_uint(self.unknown24)
        writer.write_uint(self.unknown25)
        writer.write_uint(self.unknown26)
        writer.write_bool(self.unknown27)
        writer.write_bool(self.unknown28)
        writer.write_bool(self.unknown29)
        self.unknown30.write(writer)
        self.unknown31.write(writer)
        self.unknown32.write(writer)
        writer.write_uint(self.unknown33)


# --- InventoryItem -------------------------------------------------------------------------


@dataclass
class UnknownStruct142C2FC70(Readable, Writable):
    unknown0: int = 0
    unknown1: LandmarkText = field(default_factory=LandmarkText)
    unknown2: int = 0
    unknown3: int = 0
    unknown4: bool = False
    unknown5: int = 0
    unknown6: int = 0
    unknown7: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = _read_text(reader)
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_bool()
        self.unknown5 = reader.read_uint()
        self.unknown6 = reader.read_uint()
        self.unknown7 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        self.unknown1.write(writer)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_bool(self.unknown4)
        writer.write_uint(self.unknown5)
        writer.write_uint(self.unknown6)
        writer.write_uint(self.unknown7)


@dataclass
class UnknownStruct142C18530(Readable, Writable):
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
class ItemUnknownData0SubData(Readable, Writable):  # sub_142C20E60
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    unknown5: list[UnknownStruct142C2FC70] = field(default_factory=list)
    unknown6: list[UnknownStruct142C18530] = field(default_factory=list)

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_uint()
        self.unknown5 = _read_list(reader, UnknownStruct142C2FC70)
        self.unknown6 = _read_list(reader, UnknownStruct142C18530)

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_uint(self.unknown4)
        _write_list(writer, self.unknown5)
        _write_list(writer, self.unknown6)


@dataclass
class ItemUnknownData0(Readable, Writable):  # sub_142C20F60
    unknown0: int = 0
    unknown1: int = 0
    unknown2: ItemUnknownData0SubData = field(default_factory=ItemUnknownData0SubData)
    unknown3: ItemUnknownData0SubData = field(default_factory=ItemUnknownData0SubData)
    unknown4: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_uint()
        self.unknown1 = reader.read_uint()
        self.unknown2.read(reader)
        self.unknown3.read(reader)
        self.unknown4 = reader.read_uint()

    def write(self, writer):
        writer.write_uint(self.unknown0)
        writer.write_uint(self.unknown1)
        self.unknown2.write(writer)
        self.unknown3.write(writer)
        writer.write_uint(self.unknown4)


@dataclass
class ItemSubData(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: int = 0

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unknown1 = reader.read_uint()
        self.unknown2 = reader.read_uint()

    def write(self, writer):
        writer.write_ulong(self.unknown0)
        writer.write_uint(self.unknown1)
        writer.write_uint(self.unknown2)


@dataclass
class ItemSubData2(Readable, Writable):
    unknown0: int = 0
    unknown1: str = ""
    unknown2: str = ""

    def read(self, reader):
        self.unknown0 = reader.read_ulong()
        self.unknown1 = reader.read_string()
        self.unknown2 = reader.read_string()

    def write(self, writer):
        writer.write_ulong(self.unknown0)
        writer.write_string(self.unknown1)
        writer.write_string(self.unknown2)


@dataclass
class ItemSubData3(Readable, Writable):
    unknown0: int = 0
    unknown1: int = 0
    unknown2: ItemSubData = field(default_factory=ItemSubData)

    def read(self, reader):
        self.unknown0 = reader.read_byte()
        if self.unknown0 == 0:
            return
        self.unknown1 = reader.read_uint()
        if self.unknown0 != 1:
            return
        self.unknown2.read(reader)

    def write(self, writer):
        writer.write_byte(self.unknown0)
        if self.unknown0 == 0:
            return
        writer.write_uint(self.unknown1)
        if self.unknown0 != 1:
            return
        self.unknown2.write(writer)


@dataclass
class ItemExtraData(Readable, Writable):  # sub_14361AAD0
    unknown0: int = 0

    def read(self, reader):
        # This data may parse differently depending on whether the item is a weapon.
        self.unknown0 = reader.read_byte()

    def write(self, writer):
        # TODO (from the original): handle extra data when unknown0 is not 0.
        writer.write_byte(self.unknown0)


@dataclass
class InventoryItem(Readable, Writable):
    unknown_data: ItemUnknownData0 = field(default_factory=ItemUnknownData0)
    guid: int = 0
    count: int = 0
    unknown2: int = 0
    unknown3: int = 0
    unknown4: int = 0
    container_id: int = 0  # 0 = Inventory, 2 = Equipment, 5 = Collection
    unknown6: int = 0
    slot_id: int = 0
    unknown8: int = 0
    unknown9: int = 0
    unknown10: int = 0
    unknown11: int = 0
    unknown12: int = 0
    unknown13: int = 0
    unknown14: int = 0
    sub_data1_flag: int = 0
    sub_data_item: ItemSubData | None = None
    sub_data2_item: ItemSubData2 | None = None
    sub_data3_item: ItemSubData3 = field(default_factory=ItemSubData3)
    unknown15: int = 0
    extra_data: ItemExtraData = field(default_factory=ItemExtraData)

    def read(self, reader):
        self.unknown_data.read(reader)
        self.guid = reader.read_ulong()
        self.count = reader.read_uint()
        self.unknown2 = reader.read_uint()
        self.unknown3 = reader.read_uint()
        self.unknown4 = reader.read_byte()
        self.container_id = reader.read_uint()
        self.unknown6 = reader.read_ulong()
        self.slot_id = reader.read_uint()
        self.unknown8 = reader.read_uint()
        self.unknown9 = reader.read_ulong()
        self.unknown10 = reader.read_ulong()
        self.unknown11 = reader.read_uint()
        self.unknown12 = reader.read_uint()
        self.unknown13 = reader.read_byte()
        self.unknown14 = reader.read_uint()

        self.sub_data1_flag = reader.read_byte()
        if self.sub_data1_flag != 0:
            self.sub_data_item = ItemSubData()
            self.sub_data_item.read(reader)

        if reader.read_byte() != 0:
            self.sub_data2_item = ItemSubData2()
            self.sub_data2_item.read(reader)

        self.sub_data3_item.read(reader)
        self.unknown15 = reader.read_uint()
        self.extra_data.read(reader)

    def write(self, writer):
        self.unknown_data.write(writer)
        writer.write_ulong(self.guid)
        writer.write_uint(self.count)
        writer.write_uint(self.unknown2)
        writer.write_uint(self.unknown3)
        writer.write_byte(self.unknown4)
        writer.write_uint(self.container_id)
        writer.write_ulong(self.unknown6)
        writer.write_uint(self.slot_id)
        writer.write_uint(self.unknown8)
        writer.write_ulong(self.unknown9)
        writer.write_ulong(self.unknown10)
        writer.write_uint(self.unknown11)
        writer.write_uint(self.unknown12)
        writer.write_byte(self.unknown13)
        writer.write_uint(self.unknown14)

        if self.sub_data_item is None:
            writer.write_byte(0)
        else:
            writer.write_byte(1)
            self.sub_data_item.write(writer)

        if self.sub_data2_item is None:
            writer.write_byte(0)
        else:
            writer.write_byte(1)
            self.sub_data2_item.write(writer)

        self.sub_data3_item.write(writer)
        writer.write_uint(self.unknown15)
        self.extra_data.write(writer)
