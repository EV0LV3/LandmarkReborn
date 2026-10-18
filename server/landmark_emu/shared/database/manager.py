"""Database access shared by the servers.

Queries are synchronous SQLAlchemy calls; :meth:`DatabaseManager.run` executes them on a
worker thread and returns an ``asyncio`` future that sessions wrap in a ``TaskEvent``.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..config import DatabaseConfig, DatabaseType
from .auth_database import AuthDatabase
from .character_database import CharacterDatabase
from .engine import create_database_engine

log = logging.getLogger("DatabaseManager")


class DatabaseManager:
    def __init__(self):
        self.auth_database: AuthDatabase | None = None
        self.character_database: CharacterDatabase | None = None
        self._engines = []
        self._executor: ThreadPoolExecutor | None = None

    def initialise(self, config: DatabaseConfig) -> None:
        if config.auth is not None and self.auth_database is None:
            engine = create_database_engine(config.auth)
            self._engines.append(engine)
            self.auth_database = AuthDatabase(engine)

        if config.character is not None and self.character_database is None:
            engine = create_database_engine(config.character)
            self._engines.append(engine)
            self.character_database = CharacterDatabase(engine)

        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db")

    def migrate(self, database_type: DatabaseType) -> None:
        log.info("Applying %s database migrations...", database_type.value)
        try:
            if database_type is DatabaseType.Auth:
                self.auth_database.migrate()
            elif database_type is DatabaseType.Character:
                self.character_database.migrate()
        except Exception:
            log.critical("Database migration failed", exc_info=True)
            raise

    def run(self, func: Callable[..., Any], *args: Any) -> asyncio.Future:
        """Run a blocking database call on the worker pool."""
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, functools.partial(func, *args))

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        for engine in self._engines:
            engine.dispose()
        self._engines.clear()
        self.auth_database = None
        self.character_database = None


database_manager = DatabaseManager()
