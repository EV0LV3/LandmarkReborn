from __future__ import annotations

import re

from ..shared.database.manager import database_manager
from ..shared.game.game_table import game_table_manager
from .tunnel_data import NameValidationResult

# Capitalised, no spaces, English letters only. Example: https://regex101.com/r/Ig0KT4/1
_STRICT_NAME = re.compile(r"^[A-Z](?:[^0-9][^A-Z][a-z]{1,19})$")
_WHITESPACE = re.compile(r"[\s]")


def validate_name(name: str, strict_name: bool) -> NameValidationResult:
    """Whether the provided name is allowed and available. Blocking (queries the database)."""
    upper = name.upper()
    lower = name.lower()
    for entry in game_table_manager.black_list.entries:
        # Must not match a word that requires an exact match.
        if entry.requires_exact_match and upper == entry.word.upper():
            return NameValidationResult.NameNaughty
        # Must not include a bad word that does not require an exact match.
        if not entry.requires_exact_match and entry.word.lower() in lower:
            return NameValidationResult.NameNaughty

    if database_manager.character_database.character_name_exists(name):
        return NameValidationResult.NameTaken

    if strict_name and not _STRICT_NAME.match(name):
        return NameValidationResult.NameInvalid

    # Example: https://regex101.com/r/RIeMXa/1
    if _WHITESPACE.search(name):
        return NameValidationResult.NameInvalid

    if len(name) < 2 or len(name) > 20:
        return NameValidationResult.NameInvalid

    return NameValidationResult.Success
