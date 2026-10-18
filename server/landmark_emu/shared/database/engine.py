"""Engine creation from the original ADO.NET-style connection strings."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.pool import StaticPool

from ..config import ConfigurationException, DatabaseConnectionString, DatabaseProvider

_MYSQL_KEYS = {
    "server": "host",
    "host": "host",
    "data source": "host",
    "datasource": "host",
    "port": "port",
    "user": "user",
    "uid": "user",
    "user id": "user",
    "userid": "user",
    "username": "user",
    "password": "password",
    "pwd": "password",
    "database": "database",
    "initial catalog": "database",
}


def parse_ado_connection_string(value: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for segment in value.split(";"):
        if "=" not in segment:
            continue
        key, item = segment.split("=", 1)
        parts[key.strip().lower()] = item.strip()
    return parts


def build_url(connection: DatabaseConnectionString) -> URL | str:
    text = connection.connection_string.strip()
    if "://" in text:
        return text  # Already an SQLAlchemy URL.

    if connection.provider is DatabaseProvider.MySql:
        mapped: dict[str, str] = {}
        for key, item in parse_ado_connection_string(text).items():
            if key in _MYSQL_KEYS:
                mapped[_MYSQL_KEYS[key]] = item
        return URL.create(
            "mysql+pymysql",
            username=mapped.get("user"),
            password=mapped.get("password"),
            host=mapped.get("host", "127.0.0.1"),
            port=int(mapped["port"]) if mapped.get("port") else 3306,
            database=mapped.get("database"),
            query={"charset": "utf8mb4"},
        )

    if connection.provider is DatabaseProvider.Sqlite:
        parts = parse_ado_connection_string(text)
        path = parts.get("data source") or parts.get("datasource") or parts.get("filename") or text
        return URL.create("sqlite", database=path)

    raise ConfigurationException(f"The requested database provider: {connection.provider.value} is not supported.")


def create_database_engine(connection: DatabaseConnectionString) -> Engine:
    url = build_url(connection)
    url_text = url if isinstance(url, str) else url.render_as_string(hide_password=False)

    if url_text.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url_text or url_text in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)
