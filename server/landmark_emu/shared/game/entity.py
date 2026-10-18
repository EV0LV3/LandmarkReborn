from enum import IntEnum


class AttachmentSlot(IntEnum):
    Chest = 7
    Head = 8
    Hair = 9
    FacialHair = 10
    Eyes = 11


class Gender(IntEnum):
    Male = 1
    Female = 2


class Race(IntEnum):
    Human = 1
    HumanLarge = 5


def enum_text(enum_type: type[IntEnum], value: int) -> str:
    """C# ``enum.ToString()``: the member name, or the number when undefined."""
    try:
        return enum_type(value).name
    except ValueError:
        return str(value)
