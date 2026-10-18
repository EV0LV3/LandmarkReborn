"""Plain data models returned by the database layer (safe to pass between threads)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AccountModel:
    id: int = 0
    username: str = ""
    salt: str = ""
    verifier: str = ""
    session_key: str = ""
    session_key_expiration: datetime | None = None
    server_ticket: str = ""
    create_time: datetime | None = None


@dataclass
class ZoneServerModel:
    id: int = 0
    name_id: int = 62147
    host: str = "127.0.0.1"
    port: int = 19000
    flags: int = 0


@dataclass
class CharacterCustomisationModel:
    id: int = 0
    slot: int = 0
    option: int = 0
    tint: int = 0


@dataclass
class CharacterModel:
    id: int = 0
    account_id: int = 0
    name: str | None = ""
    gender: int = 0
    race: int = 0
    skin_tint: int = 0
    profile_type_id: int = 0
    last_server_id: int = 0
    last_online: datetime | None = None
    create_time: datetime | None = None
    delete_time: datetime | None = None
    original_name: str | None = None
    customisation: list[CharacterCustomisationModel] = field(default_factory=list)
