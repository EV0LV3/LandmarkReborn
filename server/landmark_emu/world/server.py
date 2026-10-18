"""World (zone) server lifecycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..gateway import messages as gateway_messages
from ..shared.config import Configuration, DatabaseConfig, DatabaseType, NetworkConfig
from ..shared.database.manager import database_manager
from ..shared.game.game_table import game_table_manager
from ..shared.network.manager import NetworkManager
from ..shared.network.protocol import protocol_message_count
from ..shared.update_loop import UpdateLoop
from . import message_manager
from .session import WorldSession

log = logging.getLogger("HostedService")


@dataclass
class WorldServerConfiguration:
    network: NetworkConfig
    database: DatabaseConfig
    game_data_path: str = "gameData"
    tick_interval: float = 0.001

    @classmethod
    def bind(cls, config: Configuration) -> WorldServerConfiguration:
        return cls(
            network=NetworkConfig.bind(config),
            database=DatabaseConfig.bind(config),
            game_data_path=config.get_str("GameDataPath", "gameData"),
        )


class WorldServer:
    def __init__(self, configuration: WorldServerConfiguration):
        self.configuration = configuration
        self.network = NetworkManager(WorldSession)
        self._update_loop = UpdateLoop(configuration.tick_interval)

    async def start(self) -> None:
        log.info("Initialising...")
        cfg = self.configuration

        database_manager.initialise(cfg.database)
        database_manager.migrate(DatabaseType.Auth)
        database_manager.migrate(DatabaseType.Character)

        game_table_manager.initialise(cfg.game_data_path)

        log.info("Initialised %d protocol message(s).", protocol_message_count())
        gateway_messages.initialise()
        message_manager.initialise()

        self._update_loop.initialise(self.network.update)
        await self.network.initialise(cfg.network)

        log.info("Service Started!")

    async def stop(self) -> None:
        log.info("Ending Service...")
        self.network.shutdown()
        await self._update_loop.shutdown()
        database_manager.shutdown()
        log.info("Service Ended!")
