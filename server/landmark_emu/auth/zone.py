"""Zone (world) servers advertised in the server list."""

from __future__ import annotations

from enum import IntFlag

from ..shared.database.manager import database_manager
from ..shared.database.models import ZoneServerModel
from ..shared.game.text import text_manager
from .messages import Server


class ServerFlags(IntFlag):
    NONE = 0
    IsRecommended = 1


class ZoneServer:
    def __init__(self, model: ZoneServerModel):
        self.id = model.id
        self.name_id = model.name_id
        self.zone_name = text_manager.get_text_for_id(model.name_id)
        self.host = model.host
        self.port = model.port
        self.flags = ServerFlags(model.flags)

    def build(self) -> Server:
        recommended = 1 if self.flags & ServerFlags.IsRecommended else 0
        return Server(
            server_id=self.id,
            allowed_access=True,  # TODO (from the original): ask the zone server whether the user is allowed.
            is_locked=False,  # TODO (from the original): ask the zone server whether it is locked.
            name_id=self.name_id,
            name=self.zone_name,
            # Region is supported, but weird in-game, so it is left out.
            server_info=f'<ServerInfo IsRecommended="{recommended}"></ServerInfo>',
        )


class ZoneServerManager:
    def __init__(self):
        self.zone_servers: list[ZoneServer] = []

    def initialise(self) -> None:
        self.zone_servers = [ZoneServer(m) for m in database_manager.auth_database.get_zone_servers()]


zone_server_manager = ZoneServerManager()
