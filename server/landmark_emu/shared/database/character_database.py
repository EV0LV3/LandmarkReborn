"""Character storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Engine, func, insert, inspect, select, update

from .models import CharacterCustomisationModel, CharacterModel
from .schema import character, character_customisation, character_metadata

log = logging.getLogger("CharacterDatabase")


def _character_from_row(row) -> CharacterModel:
    return CharacterModel(
        id=row.id,
        account_id=row.accountId,
        name=row.name,
        gender=row.gender,
        race=row.race,
        skin_tint=row.skinTint,
        profile_type_id=row.profileTypeId,
        last_server_id=row.lastServerId,
        last_online=row.lastOnline,
        create_time=row.createTime,
        delete_time=row.deleteTime,
        original_name=row.originalName,
    )


class CharacterDatabase:
    def __init__(self, engine: Engine):
        self._engine = engine

    def migrate(self) -> None:
        existing = set(inspect(self._engine).get_table_names())
        missing = [t.name for t in character_metadata.sorted_tables if t.name not in existing]
        if not missing:
            return
        log.info("Creating %d character database table(s): %s", len(missing), ", ".join(missing))
        character_metadata.create_all(self._engine)

    def get_all_characters(self) -> list[CharacterModel]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(character).where(character.c.deleteTime.is_(None))).all()
        return [_character_from_row(r) for r in rows]

    def get_next_character_id(self) -> int:
        """The highest character id in use (0 when there are none)."""
        with self._engine.connect() as conn:
            return conn.execute(select(func.coalesce(func.max(character.c.id), 0))).scalar_one()

    def get_character_by_id(self, character_id: int) -> CharacterModel | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(character).where(character.c.id == character_id)).first()
        return _character_from_row(row) if row else None

    def get_character_by_name(self, name: str) -> CharacterModel | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(character).where(character.c.name == name)).first()
        return _character_from_row(row) if row else None

    def get_characters(self, account_id: int) -> list[CharacterModel]:
        """All of an account's characters (including deleted ones) with their customisations."""
        with self._engine.connect() as conn:
            rows = conn.execute(select(character).where(character.c.accountId == account_id)).all()
            models = [_character_from_row(r) for r in rows]
            if not models:
                return models

            by_id = {m.id: m for m in models}
            custom_rows = conn.execute(
                select(character_customisation).where(character_customisation.c.id.in_(list(by_id)))
            ).all()
        for row in custom_rows:
            by_id[row.id].customisation.append(
                CharacterCustomisationModel(id=row.id, slot=row.slot, option=row.option, tint=row.tint)
            )
        return models

    def character_name_exists(self, name: str) -> bool:
        with self._engine.connect() as conn:
            return conn.execute(select(character.c.id).where(character.c.name == name)).first() is not None

    def create_character(self, model: CharacterModel) -> None:
        with self._engine.begin() as conn:
            values = {
                "id": model.id,
                "accountId": model.account_id,
                "name": model.name,
                "gender": model.gender,
                "race": model.race,
                "profileTypeId": model.profile_type_id,
                "lastServerId": model.last_server_id,
                "lastOnline": model.last_online,
                "deleteTime": model.delete_time,
                "originalName": model.original_name,
                "skinTint": model.skin_tint,
            }
            if model.create_time is not None:
                values["createTime"] = model.create_time
            conn.execute(insert(character).values(**values))
            for custom in model.customisation:
                custom.id = model.id
                conn.execute(
                    insert(character_customisation).values(
                        id=model.id, slot=custom.slot, option=custom.option, tint=custom.tint
                    )
                )

    def soft_delete_character(self, character_id: int, original_name: str | None) -> None:
        """Marks the character deleted, keeping its name in ``originalName`` and freeing ``name``."""
        with self._engine.begin() as conn:
            conn.execute(
                update(character)
                .where(character.c.id == character_id)
                .values(
                    deleteTime=datetime.now(timezone.utc).replace(tzinfo=None),
                    originalName=original_name,
                    name=None,
                )
            )
