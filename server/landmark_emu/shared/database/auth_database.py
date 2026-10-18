"""Account and zone server storage."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import Engine, func, insert, inspect, select, update

from .models import AccountModel, ZoneServerModel
from .schema import ZONE_SERVER_SEED, account, auth_metadata, zone_server

log = logging.getLogger("AuthDatabase")

SESSION_KEY_LIFETIME = timedelta(minutes=30)


def _account_from_row(row) -> AccountModel:
    return AccountModel(
        id=row.id,
        username=row.username,
        salt=row.s,
        verifier=row.v,
        session_key=row.sessionKey,
        session_key_expiration=row.sessionKeyExpiration,
        server_ticket=row.serverTicket,
        create_time=row.createTime,
    )


class AuthDatabase:
    def __init__(self, engine: Engine):
        self._engine = engine

    def migrate(self) -> None:
        existing = set(inspect(self._engine).get_table_names())
        missing = [t.name for t in auth_metadata.sorted_tables if t.name not in existing]
        if not missing:
            return

        log.info("Creating %d authentication database table(s): %s", len(missing), ", ".join(missing))
        auth_metadata.create_all(self._engine)
        if zone_server.name in missing:
            with self._engine.begin() as conn:
                conn.execute(insert(zone_server).values(**ZONE_SERVER_SEED))

    def account_exists(self, username: str) -> bool:
        with self._engine.connect() as conn:
            return conn.execute(select(account.c.id).where(account.c.username == username)).first() is not None

    def create_account(self, username: str, salt: str, verifier: str) -> None:
        if self.account_exists(username):
            raise ValueError("Account with that username already exists.")
        with self._engine.begin() as conn:
            conn.execute(insert(account).values(username=username, s=salt, v=verifier))

    def delete_account(self, username: str) -> bool:
        with self._engine.begin() as conn:
            return conn.execute(account.delete().where(account.c.username == username)).rowcount > 0

    def update_account_session_key(self, model: AccountModel, session_key: str) -> None:
        model.session_key = session_key
        model.session_key_expiration = datetime.now() + SESSION_KEY_LIFETIME
        with self._engine.begin() as conn:
            conn.execute(
                update(account)
                .where(account.c.id == model.id)
                .values(sessionKey=model.session_key, sessionKeyExpiration=model.session_key_expiration)
            )

    def get_account_by_session_key(self, session_key: str) -> AccountModel | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(account).where(
                    account.c.sessionKey == session_key,
                    account.c.sessionKeyExpiration > datetime.now(),
                )
            ).one_or_none()
        return _account_from_row(row) if row else None

    def get_account_by_username(self, username: str) -> AccountModel | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(account).where(account.c.username == username)).one_or_none()
        return _account_from_row(row) if row else None

    def update_server_ticket(self, model: AccountModel, server_ticket: str) -> None:
        model.server_ticket = server_ticket
        with self._engine.begin() as conn:
            conn.execute(update(account).where(account.c.id == model.id).values(serverTicket=server_ticket))

    def get_account_by_server_ticket(self, server_ticket: str) -> AccountModel | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(account).where(account.c.serverTicket == server_ticket)).one_or_none()
        return _account_from_row(row) if row else None

    def get_zone_servers(self) -> list[ZoneServerModel]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(zone_server).order_by(zone_server.c.id)).all()
        return [
            ZoneServerModel(id=r.id, name_id=r.nameId, host=r.host, port=r.port, flags=r.flags) for r in rows
        ]

    def count_accounts(self) -> int:
        with self._engine.connect() as conn:
            return conn.execute(select(func.count()).select_from(account)).scalar_one()
