import argparse
from pathlib import Path
from psycopg import Cursor

from data.connection import get_connection


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"
SEED_FILE = BASE_DIR / "seed.sql"


def run_sql_file(cursor: Cursor, file_path: Path) -> None:
    with open(file_path, "r", encoding="utf-8") as file:
        sql = file.read()
        cursor.execute(sql)


def reset_database(cursor: Cursor) -> None:
    cursor.execute("DROP SCHEMA public CASCADE;")
    cursor.execute("CREATE SCHEMA public;")


def init_db(reset: bool = True, seed: bool = True) -> None:
    conn = get_connection()
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            if reset:
                print("Resetting database...")
                reset_database(cursor)

            print("Running schema.sql...")
            run_sql_file(cursor, SCHEMA_FILE)

            if seed and SEED_FILE.exists():
                print("Running seed.sql...")
                run_sql_file(cursor, SEED_FILE)

        print("Database initialized successfully.")

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