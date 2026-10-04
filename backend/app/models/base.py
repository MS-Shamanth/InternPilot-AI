"""Declarative base, portable column types and shared value sets (design.md §4, NFR2)."""

from collections.abc import Iterable
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

EXPERIENCE_LEVELS: tuple[str, ...] = ("internship", "entry", "junior", "mid", "senior")
EDUCATION_LEVELS: tuple[str, ...] = ("high_school", "diploma", "bachelor", "master", "phd")

# JSON on every database, JSONB on PostgreSQL.
PortableJSON = sa.JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(sa.TypeDecorator[datetime]):
    """Timezone-aware UTC timestamp that behaves the same on PostgreSQL and SQLite.

    Binding a naive datetime raises `ValueError`; aware values are converted to UTC.
    Loaded values are always aware UTC (SQLite returns naive values, which are stored as UTC).
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime requires a timezone-aware datetime")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def check_in(column_name: str, values: Iterable[str]) -> sa.ColumnElement[bool]:
    """Build a portable `column IN (...)` expression for a CHECK constraint."""
    return sa.column(column_name).in_(list(values))


def empty_json_list() -> sa.TextClause:
    """Server default for JSON list columns."""
    return sa.text("'[]'")


class Base(DeclarativeBase):
    """Declarative base with a naming convention for stable constraint names."""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """`created_at` set by the database on insert."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=sa.func.now()
    )


class TimestampMixin(CreatedAtMixin):
    """`created_at` plus `updated_at` refreshed on every ORM update."""

    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()
    )
