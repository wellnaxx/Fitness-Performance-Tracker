from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from psycopg.abc import QueryNoTemplate

from data.connection import get_connection
from utils.errors import DatabaseError

if TYPE_CHECKING:
    from psycopg import Cursor

logger = logging.getLogger(__name__)

type SQLParams = tuple[object, ...]
type SQLQuery = str | QueryNoTemplate
type Row = tuple[object, ...]
type RowDict = dict[str, object]

def _as_query(sql: SQLQuery) -> QueryNoTemplate:
    return cast(QueryNoTemplate, sql)


def _get_column_names(cursor: Cursor[Row]) -> list[str]:
    if cursor.description is None:
        raise DatabaseError("Query did not return a result set.")

    return [col.name for col in cursor.description]

def _cursor_to_dicts(cursor: Cursor[Row]) -> list[RowDict]:
    """Convert all cursor rows to column-name-keyed dicts."""
    columns = _get_column_names(cursor)
    rows = cursor.fetchall()
    return [dict(zip(columns, row, strict=False)) for row in rows]

def fetch_all(sql: SQLQuery, params: SQLParams = ()) -> list[RowDict]:
    """Execute a SELECT and return all rows as dicts."""
    logger.debug("SELECT %s | params=%s", sql, params)

    try:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(_as_query(sql), params)
            return _cursor_to_dicts(cursor)

    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError(
            f"Database read failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def fetch_one(sql: SQLQuery, params: SQLParams = ()) -> RowDict | None:
    """Execute a SELECT and return the first row as a dict, or None."""
    logger.debug("SELECT (one) %s | params=%s", sql, params)

    try:
        with get_connection() as conn, conn.cursor() as cursor:
            typed_cursor = cursor
            typed_cursor.execute(_as_query(sql), params)
            row = typed_cursor.fetchone()

            if row is None:
                return None

            columns = _get_column_names(typed_cursor)
            return dict(zip(columns, row, strict=False))

    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError(
            f"Database read failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def execute_insert(sql: SQLQuery, params: SQLParams = ()) -> int:
    """
    Execute an INSERT and return the new row's id.
    IMPORTANT: SQL must include RETURNING id.
    """
    logger.debug("INSERT %s | params=%s", sql, params)

    try:
        with get_connection() as conn, conn.cursor() as cursor:
            typed_cursor = cursor
            typed_cursor.execute(_as_query(sql), params)

            row = typed_cursor.fetchone()
            if row is None:
                raise DatabaseError(
                    "INSERT did not return an id. Did you forget 'RETURNING id'?"
                )

            new_id = row[0]
            if not isinstance(new_id, int):
                raise DatabaseError(
                    f"Expected returned id to be int, got {type(new_id).__name__}."
                )

            conn.commit()
            return new_id

    except Exception as exc:
        logger.exception("Database insert failed")
        raise DatabaseError(
            f"Database insert failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def execute_write(sql: SQLQuery, params: SQLParams = ()) -> int:
    """Execute an UPDATE or DELETE and return affected row count."""
    logger.debug("WRITE %s | params=%s", sql, params)

    try:
        with get_connection() as conn, conn.cursor() as cursor:
            typed_cursor = cursor
            typed_cursor.execute(_as_query(sql), params)
            affected = typed_cursor.rowcount
            conn.commit()
            return int(affected)

    except Exception as exc:
        logger.exception("Database write failed")
        raise DatabaseError(
            f"Database write failed ({exc.__class__.__name__}): {exc}"
        ) from exc