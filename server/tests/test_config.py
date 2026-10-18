import json

import pytest

from landmark_emu.auth.config import AuthServerConfiguration
from landmark_emu.shared.config import (
    Configuration,
    ConfigurationException,
    DatabaseConnectionString,
    DatabaseProvider,
    parse_command_line,
)
from landmark_emu.shared.database.engine import build_url
from landmark_emu.world.server import WorldServerConfiguration


def test_example_configs_bind(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    auth = AuthServerConfiguration.bind(Configuration.load(root / "AuthServer.example.json", environ={}, argv=[]))
    assert (auth.network.host, auth.network.port) == ("0.0.0.0", 20042)
    assert auth.database.auth.provider is DatabaseProvider.MySql
    assert auth.web_api.enabled and auth.web_api.base_uri == "http://0.0.0.0:5080"
    assert auth.creation_rules.strict_name is False
    assert auth.game_data_path == "gameData"

    world = WorldServerConfiguration.bind(Configuration.load(root / "WorldServer.example.json", environ={}, argv=[]))
    assert world.network.port == 19000 and world.database.character is not None


def test_overrides_env_then_command_line(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("﻿" + json.dumps({"Network": {"Host": "0.0.0.0", "Port": 1}, "CreationRules": {"StrictName": False}}), encoding="utf-8")
    config = Configuration.load(
        path,
        environ={"NETWORK__PORT": "2", "CreationRules__StrictName": "true"},
        argv=["--network:port", "3", "GameDataPath=/data", "/WebApi:Enabled=false"],
    )
    assert config.get_int("Network:Port") == 3
    assert config.get_bool("creationrules:strictname") is True
    assert config.get_str("GameDataPath") == "/data"
    assert config.get_bool("WebApi:Enabled", True) is False


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigurationException):
        Configuration.load(tmp_path / "nope.json", environ={}, argv=[])


def test_command_line_forms():
    assert parse_command_line(["a=1", "--b=2", "--c", "3", "/d", "4", "/e=5", "-f", "ignored"]) == {
        "a": "1", "b": "2", "c": "3", "d": "4", "e": "5",
    }


def test_mysql_connection_string_from_original_format():
    url = build_url(
        DatabaseConnectionString(
            DatabaseProvider.MySql,
            "server=127.0.0.1;port=3306;user=landmarkemu;password=p@ss;word;database=lmemu_auth",
        )
    )
    assert url.drivername == "mysql+pymysql"
    assert (url.host, url.port, url.username, url.database) == ("127.0.0.1", 3306, "landmarkemu", "lmemu_auth")
    assert url.query["charset"] == "utf8mb4"


def test_sqlite_and_raw_urls():
    assert build_url(DatabaseConnectionString(DatabaseProvider.Sqlite, "Data Source=auth.db")).database == "auth.db"
    assert build_url(DatabaseConnectionString(DatabaseProvider.Sqlite, "auth.db")).database == "auth.db"
    assert build_url(DatabaseConnectionString(DatabaseProvider.MySql, "mysql+pymysql://u:p@h/db")) == "mysql+pymysql://u:p@h/db"
    with pytest.raises(ConfigurationException):
        build_url(DatabaseConnectionString(DatabaseProvider.MicrosoftSqlServer, "server=x"))
