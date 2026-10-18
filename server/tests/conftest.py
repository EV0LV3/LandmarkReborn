import json
from pathlib import Path

import pytest

from landmark_emu.shared.config import DatabaseConfig, DatabaseConnectionString, DatabaseProvider, NetworkConfig
from landmark_emu.shared.game.text import TextManager

GOLDEN_PATH = Path(__file__).parent / "golden" / "golden.json"

HUMAN_PROFILE = (
    "46^571666^0^0^3^0^0^0^0^2514^0^0^0^0^0^0^0^1^1^0^0^0^0^0^1^^390^392^0^0^0^2.8^2.75^0.4^1^11294^2512"
    "^1.4^15^0^0^0^0^0^0^0^0^3^3^3^0^"
)


def write_game_data(directory: Path) -> None:
    """Minimal stand-ins for the client's game data files."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "en_us_data.dat").write_text(
        "# header\n"
        f"{TextManager.get_hash(62147)}\tx\tEmulated Server\n"
        f"{TextManager.get_hash(571666)}\tx\tHuman\n",
        encoding="utf-8",
    )
    (directory / "ProfileDefinitions.txt").write_text("ID^NAME_ID^...\n" + HUMAN_PROFILE + "\n", encoding="utf-8")
    (directory / "BlackListEntries.txt").write_text("WORD^...\nbadword^^0^^0^0\n", encoding="utf-8")


def sqlite(path: Path) -> DatabaseConnectionString:
    return DatabaseConnectionString(DatabaseProvider.Sqlite, f"Data Source={path}")


@pytest.fixture
async def servers(tmp_path):
    """Auth (with web API) and World servers on ephemeral ports, backed by SQLite."""
    from landmark_emu.auth.config import AuthServerConfiguration
    from landmark_emu.auth.server import AuthServer
    from landmark_emu.webapi.config import WebApiConfig
    from landmark_emu.world.server import WorldServer, WorldServerConfiguration

    game_data = tmp_path / "gameData"
    write_game_data(game_data)
    database = DatabaseConfig(auth=sqlite(tmp_path / "auth.db"), character=sqlite(tmp_path / "character.db"))

    auth = AuthServer(
        AuthServerConfiguration(
            network=NetworkConfig("127.0.0.1", 0),
            database=database,
            web_api=WebApiConfig(enabled=True, base_uri="http://127.0.0.1:0"),
            game_data_path=str(game_data),
        ),
        enable_console=False,
    )
    await auth.start()
    world = WorldServer(
        WorldServerConfiguration(network=NetworkConfig("127.0.0.1", 0), database=database, game_data_path=str(game_data))
    )
    await world.start()
    try:
        yield auth, world
    finally:
        await world.stop()
        await auth.stop()


@pytest.fixture(scope="session")
def golden() -> dict:
    """Byte-level reference vectors produced by the original C# implementation (see tests/golden/README.md)."""
    with GOLDEN_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session", autouse=True)
def registries():
    from landmark_emu.auth import message_manager as auth_messages
    from landmark_emu.gateway import messages as gateway_messages
    from landmark_emu.world import message_manager as zone_messages

    auth_messages.initialise()
    gateway_messages.initialise()
    zone_messages.initialise()
