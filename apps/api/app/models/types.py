"""Dialect-aware SQLAlchemy custom types.

These TypeDecorators use PostgreSQL-native types in production and fall back
to standard JSON types when running under SQLite (e.g. in-memory test DBs).
"""

from typing import Any

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.engine import Dialect


class _JSONBCompat(TypeDecorator[Any]):
    """JSONB in PostgreSQL, JSON in other dialects (e.g. SQLite for tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())  # type: ignore[no-untyped-call]
        return dialect.type_descriptor(JSON())


class _StringArrayCompat(TypeDecorator[list[str]]):
    """String ARRAY in PostgreSQL, JSON in other dialects (e.g. SQLite for tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String()))
        return dialect.type_descriptor(JSON())
