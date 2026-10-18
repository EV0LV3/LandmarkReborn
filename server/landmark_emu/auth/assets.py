"""Static assets and id allocation for the auth server."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .. import RESOURCES_DIR
from ..shared.database.manager import database_manager
from .tunnel_data import ArtData

log = logging.getLogger("AuthAssetManager")

ART_TINTS_PATH = RESOURCES_DIR / "auth" / "ArtTints.json"


class AuthAssetManager:
    def __init__(self):
        self._next_character_id = 0
        self.art_data: ArtData | None = None

    def initialise(self, art_tints_path: Path = ART_TINTS_PATH) -> None:
        self._next_character_id = database_manager.character_database.get_next_character_id() + 1
        self._initialise_art_data(art_tints_path)

    def next_character_id(self) -> int:
        """Id to be assigned to the next created character."""
        value = self._next_character_id
        self._next_character_id += 1
        return value

    def _initialise_art_data(self, path: Path) -> None:
        with path.open(encoding="utf-8-sig") as handle:
            self.art_data = ArtData.from_json(json.load(handle))
        # Encode once up front so the first login doesn't pay for it.
        log.info("Loaded art data (%d bytes encoded).", self.art_data.get_size())


auth_asset_manager = AuthAssetManager()
