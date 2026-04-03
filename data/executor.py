from typing import Any

from psycopg import Cursor

from data.connection import get_connection
from utils.errors import DatabaseError
import logging

logger = logging.getLogger(__name__)


def _cursor_to_dicts(cursor: Cursor) -> list[dict[str, Any]]:
    """Convert all cursor rows to column-name-keyed dicts."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a SELECT and return all rows as dicts."""
    logger.debug("SELECT %s | params=%s", sql, params)

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return _cursor_to_dicts(cursor)

    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError(
            f"Database read failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    """Execute a SELECT and return the first row as a dict, or None."""
    logger.debug("SELECT (one) %s | params=%s", sql, params)

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()

                if row is None:
                    return None

                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))

    except Exception as exc:
        logger.exception("Database read failed")
        raise DatabaseError(
            f"Database read failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def execute_insert(sql: str, params: tuple = ()) -> int:
    """
    Execute an INSERT and return the new row's id.
    IMPORTANT: SQL must include RETURNING id.
    """
    logger.debug("INSERT %s | params=%s", sql, params)

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                new_id = cursor.fetchone()[0]
                conn.commit()
                return int(new_id)

    except Exception as exc:
        logger.exception("Database insert failed")
        raise DatabaseError(
            f"Database insert failed ({exc.__class__.__name__}): {exc}"
        ) from exc


def execute_write(sql: str, params: tuple = ()) -> int:
    """Execute an UPDATE or DELETE and return affected row count."""
    logger.debug("WRITE %s | params=%s", sql, params)

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                affected = cursor.rowcount
                conn.commit()
                return int(affected)

    except Exception as exc:
        logger.exception("Database write failed")
        raise DatabaseError(
            f"Database write failed ({exc.__class__.__name__}): {exc}"
        ) from exc