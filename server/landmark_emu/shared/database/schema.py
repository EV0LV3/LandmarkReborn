"""Table definitions.

Table and column names match the schema created by the original EF Core migrations, so a
database created by the C# server can be used as-is.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    func,
)
from sqlalchemy.dialects import mysql


def _u64():
    return BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")


def _u32():
    return BigInteger().with_variant(mysql.INTEGER(unsigned=True), "mysql")


def _u16():
    return Integer().with_variant(mysql.SMALLINT(unsigned=True), "mysql")


def _u8():
    return SmallInteger().with_variant(mysql.TINYINT(unsigned=True), "mysql")


_MYSQL_TABLE_ARGS = {"mysql_charset": "utf8mb4"}

auth_metadata = MetaData()

account = Table(
    "account",
    auth_metadata,
    Column("id", _u64(), primary_key=True, autoincrement=True),
    Column("username", String(255), nullable=False, server_default=""),
    Column("s", String(32), nullable=False, server_default=""),
    Column("v", String(512), nullable=False, server_default=""),
    Column("sessionKey", String(32), nullable=False, server_default=""),
    Column("sessionKeyExpiration", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("serverTicket", String(32), nullable=False, server_default=""),
    Column("createTime", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("salt", "s"),
    Index("username", "username"),
    Index("verifier", "v"),
    **_MYSQL_TABLE_ARGS,
)

zone_server = Table(
    "zone_server",
    auth_metadata,
    Column("id", _u64(), primary_key=True, autoincrement=True),
    Column("nameId", _u32(), nullable=False, server_default="62147"),
    Column("host", String(64), nullable=False, server_default="127.0.0.1"),
    Column("port", _u16(), nullable=False, server_default="19000"),
    Column("flags", _u32(), nullable=False, server_default="0"),
    **_MYSQL_TABLE_ARGS,
)

# Seed row created by the original "HelloAuth" migration.
ZONE_SERVER_SEED = {"id": 1, "nameId": 62147, "host": "127.0.0.1", "port": 19000, "flags": 1}

character_metadata = MetaData()

character = Table(
    "character",
    character_metadata,
    Column("id", _u64(), primary_key=True, autoincrement=False, server_default="0"),
    Column("accountId", _u64(), nullable=False, server_default="0"),
    Column("name", String(50), nullable=True, server_default=""),
    Column("gender", _u8(), nullable=False, server_default="0"),
    Column("race", _u8(), nullable=False, server_default="0"),
    Column("profileTypeId", _u32(), nullable=False, server_default="0"),
    Column("lastServerId", _u64(), nullable=False, server_default="0"),
    Column("lastOnline", DateTime, nullable=True),
    Column("createTime", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("deleteTime", DateTime, nullable=True),
    Column("originalName", String(50), nullable=True),
    Column("skinTint", _u32(), nullable=False, server_default="0"),
    Index("accountId", "accountId"),
    **_MYSQL_TABLE_ARGS,
)

character_customisation = Table(
    "character_customisation",
    character_metadata,
    Column("id", _u64(), nullable=False, server_default="0"),
    Column("slot", _u32(), nullable=False, server_default="0"),
    Column("option", _u32(), nullable=False, server_default="0"),
    Column("tint", _u32(), nullable=False, server_default="0"),
    PrimaryKeyConstraint("id", "slot", name="PRIMARY"),
    ForeignKeyConstraint(
        ["id"],
        ["character.id"],
        name="FK__character_customisation_id__character_id",
        ondelete="CASCADE",
    ),
    **_MYSQL_TABLE_ARGS,
)
