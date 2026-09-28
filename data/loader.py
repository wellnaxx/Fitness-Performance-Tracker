"""Load repository SQL from files relative to this module."""

from functools import cache
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"


@cache
def load_sql(relative_path: str) -> str:
    """Read and cache a UTF-8 query, raising FileNotFoundError if it is missing."""
    return (SQL_DIR / relative_path).read_text(encoding="utf-8").strip()
