from __future__ import annotations


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""

    @classmethod
    def wrong_query_result(cls) -> DatabaseError:
        return cls("Query did not return a result set.")

    @classmethod
    def read_failed(cls, exc: Exception) -> DatabaseError:
        return cls(f"Database read failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def insert_failed(cls, exc: Exception) -> DatabaseError:
        return cls(f"Database insert failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def write_failed(cls, exc: Exception) -> DatabaseError:
        return cls(f"Database write failed ({exc.__class__.__name__}): {exc}")

    @classmethod
    def missing_returning_id(cls) -> DatabaseError:
        return cls("INSERT did not return an id. Did you forget 'RETURNING id'?")

    @classmethod
    def invalid_returned_id_type(cls, value: object) -> DatabaseError:
        return cls(f"Expected returned id to be int, got {type(value).__name__}.")
