from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from data.connection import get_connection

if TYPE_CHECKING:
    from psycopg import Cursor
    from psycopg.abc import Query

type Row = tuple[object, ...]


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"
SEED_FILE = BASE_DIR / "seed.sql"

logger = logging.getLogger(__name__)

def run_sql_file(cursor: Cursor[Row], file_path: Path) -> None:
    with file_path.open("r", encoding="utf-8") as file:
        sql = file.read()
        cursor.execute(cast("Query", sql))


def reset_database(cursor: Cursor[Row]) -> None:
    cursor.execute(cast("Query", "DROP SCHEMA public CASCADE;"))
    cursor.execute(cast("Query", "CREATE SCHEMA public;"))


def init_db(reset: bool = True, seed: bool = True) -> None:
    conn = get_connection()
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            typed_cursor: Cursor[Row] = cursor

            if reset:
                logger.info("Resetting database...")
                reset_database(typed_cursor)

            logger.info("Running schema.sql...")
            run_sql_file(typed_cursor, SCHEMA_FILE)

            if seed and SEED_FILE.exists():
                logger.info("Running seed.sql...")
                run_sql_file(typed_cursor, SEED_FILE)

        logger.info("Database initialized successfully.")

    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize the fitness performance tracker database."
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not drop and recreate the public schema before running schema.sql.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Do not run seed.sql after schema.sql.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    init_db(
        reset=not args.no_reset,
        seed=not args.no_seed,
    )
