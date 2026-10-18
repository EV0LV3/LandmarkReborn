from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.config import Configuration, DatabaseConfig, NetworkConfig
from ..webapi.config import WebApiConfig


@dataclass
class CharacterCreateRules:
    # Forces RPG-style names: first letter capitalised, no numbers, no spaces.
    strict_name: bool = False


@dataclass
class AuthServerConfiguration:
    network: NetworkConfig
    database: DatabaseConfig
    web_api: WebApiConfig
    game_data_path: str = "gameData"
    creation_rules: CharacterCreateRules = field(default_factory=CharacterCreateRules)
    tick_interval: float = 0.001

    @classmethod
    def bind(cls, config: Configuration) -> AuthServerConfiguration:
        return cls(
            network=NetworkConfig.bind(config),
            database=DatabaseConfig.bind(config),
            web_api=WebApiConfig.bind(config),
            game_data_path=config.get_str("GameDataPath", "gameData"),
            creation_rules=CharacterCreateRules(strict_name=config.get_bool("CreationRules:StrictName", False)),
        )


_current: AuthServerConfiguration | None = None


def set_current(config: AuthServerConfiguration) -> None:
    global _current
    _current = config


def current() -> AuthServerConfiguration:
    if _current is None:
        raise RuntimeError("The auth server configuration has not been loaded.")
    return _current
