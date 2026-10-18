"""Server configuration.

Works like the original Microsoft.Extensions.Configuration setup: a JSON file, overlaid by
environment variables (``Network__Port=20042``) and then command-line arguments
(``Network:Port=20042``, ``--Network:Port 20042`` or ``/Network:Port=20042``). Keys are
case-insensitive.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ConfigurationException(Exception):
    pass


def _flatten(value: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _flatten(child, f"{prefix}:{key}" if prefix else str(key), out)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _flatten(child, f"{prefix}:{index}" if prefix else str(index), out)
    else:
        out[prefix.lower()] = value


def parse_command_line(args: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    items = list(args)
    i = 0
    while i < len(items):
        arg = items[i]
        i += 1
        if arg.startswith("--"):
            key = arg[2:]
        elif arg.startswith("/"):
            key = arg[1:]
        elif "=" in arg and not arg.startswith("-"):
            key = arg
        else:
            continue

        if "=" in key:
            key, value = key.split("=", 1)
        elif i < len(items):
            value = items[i]
            i += 1
        else:
            continue
        if key:
            result[key.lower()] = value
    return result


class Configuration:
    def __init__(self, values: dict[str, Any] | None = None):
        self._values: dict[str, Any] = dict(values or {})

    @classmethod
    def load(
        cls,
        file: str | Path,
        environ: Mapping[str, str] | None = None,
        argv: Iterable[str] | None = None,
    ) -> Configuration:
        path = Path(file)
        if not path.is_file():
            raise ConfigurationException(f"The configuration file '{path}' was not found.")
        with path.open(encoding="utf-8-sig") as handle:
            data = json.load(handle)

        values: dict[str, Any] = {}
        _flatten(data, "", values)

        for name, value in (os.environ if environ is None else environ).items():
            values[name.replace("__", ":").lower()] = value

        values.update(parse_command_line(sys.argv[1:] if argv is None else argv))
        return cls(values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key.lower(), default)

    def get_str(self, key: str, default: str | None = None) -> str | None:
        value = self.get(key)
        return default if value is None else str(value)

    def get_int(self, key: str, default: int | None = None) -> int | None:
        value = self.get(key)
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationException(f"Configuration value '{key}' must be a number, got '{value}'.") from exc

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key)
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no"):
            return False
        raise ConfigurationException(f"Configuration value '{key}' must be true or false, got '{value}'.")

    def has_section(self, key: str) -> bool:
        prefix = key.lower() + ":"
        return any(k.startswith(prefix) for k in self._values)


def resolve_config_file(default_name: str, argv: list[str] | None = None) -> Path:
    """``--config <path>`` wins; otherwise the default file name in the working directory."""
    args = sys.argv[1:] if argv is None else argv
    for i, arg in enumerate(args):
        if arg.startswith("--config="):
            return Path(arg.split("=", 1)[1])
        if arg == "--config" and i + 1 < len(args):
            return Path(args[i + 1])
    return Path(default_name)


@dataclass
class NetworkConfig:
    host: str = "0.0.0.0"
    port: int = 0

    @classmethod
    def bind(cls, config: Configuration, section: str = "Network") -> NetworkConfig:
        return cls(
            host=config.get_str(f"{section}:Host", "0.0.0.0"),
            port=config.get_int(f"{section}:Port", 0),
        )


class DatabaseProvider(Enum):
    MySql = "MySql"
    MicrosoftSqlServer = "MicrosoftSqlServer"
    Sqlite = "Sqlite"

    @classmethod
    def parse(cls, value: str) -> DatabaseProvider:
        for member in cls:
            if member.value.lower() == str(value).strip().lower():
                return member
        raise ConfigurationException(f"Unknown database provider '{value}'.")


class DatabaseType(Enum):
    Auth = "Auth"
    Character = "Character"
    Zone = "Zone"


@dataclass
class DatabaseConnectionString:
    provider: DatabaseProvider
    connection_string: str


@dataclass
class DatabaseConfig:
    auth: DatabaseConnectionString | None = None
    character: DatabaseConnectionString | None = None
    zone: DatabaseConnectionString | None = None

    def get_connection_string(self, database_type: DatabaseType) -> DatabaseConnectionString:
        value = {
            DatabaseType.Auth: self.auth,
            DatabaseType.Character: self.character,
            DatabaseType.Zone: self.zone,
        }[database_type]
        if value is None:
            raise ConfigurationException(f"No connection string is configured for the {database_type.value} database.")
        return value

    @classmethod
    def bind(cls, config: Configuration, section: str = "Database") -> DatabaseConfig:
        def connection(name: str) -> DatabaseConnectionString | None:
            if not config.has_section(f"{section}:{name}"):
                return None
            return DatabaseConnectionString(
                provider=DatabaseProvider.parse(config.get_str(f"{section}:{name}:Provider", "MySql")),
                connection_string=config.get_str(f"{section}:{name}:ConnectionString", ""),
            )

        return cls(auth=connection("Auth"), character=connection("Character"), zone=connection("Zone"))
