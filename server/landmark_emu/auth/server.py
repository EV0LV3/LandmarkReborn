"""Auth server lifecycle."""

from __future__ import annotations

import logging

from ..shared.command import CommandManager
from ..shared.config import DatabaseType
from ..shared.database.manager import database_manager
from ..shared.game.game_table import game_table_manager
from ..shared.network.manager import NetworkManager
from ..shared.network.protocol import protocol_message_count
from ..shared.update_loop import UpdateLoop
from ..webapi.app import AuthWebApi
from . import config as auth_config
from . import message_manager
from .assets import auth_asset_manager
from .commands import AuthCommandHandler
from .config import AuthServerConfiguration
from .session import AuthSession
from .zone import zone_server_manager

log = logging.getLogger("HostedService")


class AuthServer:
    def __init__(self, configuration: AuthServerConfiguration, enable_console: bool = True):
        self.configuration = configuration
        self.network = NetworkManager(AuthSession)
        self.web_api = AuthWebApi(configuration.web_api, database_manager)
        self._update_loop = UpdateLoop(configuration.tick_interval)
        self._commands = CommandManager() if enable_console else None

    async def start(self) -> None:
        log.info("Initialising...")
        cfg = self.configuration
        auth_config.set_current(cfg)

        database_manager.initialise(cfg.database)
        database_manager.migrate(DatabaseType.Auth)
        database_manager.migrate(DatabaseType.Character)

        game_table_manager.initialise(cfg.game_data_path)

        log.info("Initialised %d protocol message(s).", protocol_message_count())
        message_manager.initialise()

        auth_asset_manager.initialise()

        self._update_loop.initialise(self.network.update)

        zone_server_manager.initialise()
        await self.network.initialise(cfg.network)

        await self.web_api.start()

        if self._commands is not None:
            self._commands.initialise(AuthCommandHandler())

        log.info("Service Started!")

    async def stop(self) -> None:
        log.info("Ending Service...")
        if self._commands is not None:
            self._commands.shutdown()
        await self.web_api.stop()
        self.network.shutdown()
        await self._update_loop.shutdown()
        database_manager.shutdown()
        log.info("Service Ended!")
