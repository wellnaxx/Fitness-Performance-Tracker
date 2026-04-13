from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from psycopg.abc import QueryNoTemplate

from core.errors.database import DatabaseError
from data.connection import get_connection

if TYPE_CHECKING:
    from psycopg import Cursor

logger = logging.getLogger(__name__)

type SQLParams = tuple[object, ...]
type SQLQuery = str | QueryNoTemplate
type Row = tuple[object, ...]
type RowDict = dict[str, object]


def _as_query(sql: SQLQuery) -> QueryNoTemplate:
    return cast("QueryNoTemplate", sql)


def _get_column_names(cursor: Cursor[Row]) -> list[str]:
    if cursor.description is None:
        raise DatabaseError.wrong_query_result()

    return [col.name for col in cursor.description]


def _extract_inserted_id(row: Row | None) -> int:
    if row is None:
        raise DatabaseError.missing_returning_id()

    new_id = row[0]
    if not isinstance(new_id, int):
        raise DatabaseError.invalid_returned_id_type(new_id)

    return new_id


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
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError.read_failed(exc) from exc


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
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError.read_failed(exc) from exc


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

            new_id = _extract_inserted_id(typed_cursor.fetchone())
            conn.commit()
            return new_id
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Database insert failed")
        raise DatabaseError.insert_failed(exc) from exc


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
    except DatabaseError:
        raise
    except Exception as exc:
        logger.exception("Database write failed")
        raise DatabaseError.write_failed(exc) from exc
