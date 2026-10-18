"""``^``-delimited game data tables exported from the client."""

from __future__ import annotations

import dataclasses
import logging
import time
import typing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from .text import text_manager

log = logging.getLogger("GameTableManager")

T = TypeVar("T")


class GameTableException(Exception):
    pass


def _converter(annotation) -> typing.Callable[[str], object]:
    if annotation is bool:
        return lambda text: int(text) != 0
    if annotation is int:
        return int
    if annotation is float:
        return float
    return str


class GameTable(Generic[T]):
    def __init__(self, entry_type: type[T], path: str | Path, has_id: bool = True):
        self._entries: dict[int, T] = {}
        self._entry_type = entry_type
        self._has_id = has_id
        hints = typing.get_type_hints(entry_type)
        self._fields = [(f.name, _converter(hints[f.name])) for f in dataclasses.fields(entry_type)]
        with open(path, encoding="utf-8", errors="replace") as handle:
            self._read_entries(handle)

    def _read_entries(self, handle) -> None:
        record_count = 0
        for line in handle:
            line = line.rstrip("\r\n")
            if record_count == 0:  # Header row.
                record_count += 1
                continue

            pieces = line.split("^")
            values = {}
            for index, (name, convert) in enumerate(self._fields):
                piece = pieces[index] if index < len(pieces) else None
                try:
                    if piece is None:
                        raise IndexError("missing column")
                    values[name] = convert(piece)
                except Exception as exc:
                    log.error("%s errored with value %s.", name, piece)
                    raise GameTableException(f"Failed to parse {self._entry_type.__name__}.{name}") from exc

            entry = self._entry_type(**values)
            entry_id = getattr(entry, self._fields[0][0]) if self._has_id else record_count
            self._entries.setdefault(entry_id, entry)
            record_count += 1

    @property
    def entries(self) -> list[T]:
        return list(self._entries.values())

    @property
    def record_count(self) -> int:
        return len(self._entries)

    def get_entry(self, entry_id: int) -> T | None:
        return self._entries.get(entry_id)


@dataclass
class BlackListEntry:
    word: str
    replacement_word: str
    filter_type: int
    exempt_words: str
    ignore_substring_checks: bool
    requires_exact_match: bool


@dataclass
class ProfileDefinitionEntry:
    # Human: 46^571666^0^0^3^0^0^0^0^2514^0^0^0^0^0^0^0^1^1^0^0^0^0^0^1^^390^392^0^0^0^2.8^2.75^0.4^1^11294^2512^1.4^15^0^0^0^0^0^0^0^0^3^3^3^0^
    id: int
    name_id: int
    description_id: int
    requirement_id: int
    profile_type: int
    starting_equipment_set_id: int
    icon_id: int
    category: int
    ability_bg_image_set_id: int
    switch_profile_effect_id: int
    switch_profile_animation: int
    members_only: bool
    displayed_stat_set_id: int
    preview_hint_string_id: int
    show_preview: bool
    trial_enabled: bool
    trainer_locator_quest_id: int
    experience_modifier: float
    coin_modifier: float
    trial_level_cap: int
    grandfathered_free: bool
    auto_grant: bool
    wield_type_override: int
    content_id: int
    faction_id: int
    identifier: str
    male_model_id: int
    female_model_id: int
    no_crouch: bool
    no_jump: bool
    no_strafe: bool
    stand_camera_height: float
    line_of_sight_height: float
    capsule_radius: float
    ui_model_camera_id: int
    spawn_effect_id: int
    despawn_effect_id: int
    crouch_camera_height: float
    mass: float
    acquire_sec: int
    currency_type: int
    cost: int
    weapon_set_id01: int
    weapon_set_id02: int
    weapon_set_id03: int
    weapon_set_id04: int
    weapon_set_id05: int
    char_size: int
    armor: int
    feet: int
    repairable_damage_angle: float


class GameTableManager:
    # (attribute, file name, entry type, has id column)
    TABLES = (
        ("black_list", "BlackListEntries.txt", BlackListEntry, False),
        ("profile_definitions", "ProfileDefinitions.txt", ProfileDefinitionEntry, True),
    )

    def __init__(self):
        self.black_list: GameTable[BlackListEntry] | None = None
        self.profile_definitions: GameTable[ProfileDefinitionEntry] | None = None

    def initialise(self, game_data_path: str | Path) -> None:
        """Load the text tables, then every game table (in parallel)."""
        text_manager.initialise(game_data_path)

        log.info("Loading GameTables...")
        started = time.perf_counter()
        errors: list[BaseException] = []

        def load(attribute: str, file_name: str, entry_type, has_id: bool):
            table_started = time.perf_counter()
            try:
                table = GameTable(entry_type, Path(game_data_path) / file_name, has_id)
            except Exception as exc:
                log.error("Failed to load %s in %dms", file_name, (time.perf_counter() - table_started) * 1000)
                errors.append(exc)
                return
            setattr(self, attribute, table)
            log.info("Completed loading %s in %dms", file_name, (time.perf_counter() - table_started) * 1000)

        with ThreadPoolExecutor(max_workers=max(2, min(16, len(self.TABLES)))) as pool:
            for table in self.TABLES:
                pool.submit(load, *table)

        if errors:
            log.critical("Failed to load game tables", exc_info=errors[0])
            raise ExceptionGroup("Failed to load game tables", [e for e in errors if isinstance(e, Exception)])

        log.info("Loaded GameTables in %dms.", (time.perf_counter() - started) * 1000)


game_table_manager = GameTableManager()
