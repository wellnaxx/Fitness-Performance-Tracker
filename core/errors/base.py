from __future__ import annotations


class AppError(RuntimeError):
    """Base application error."""


class ServiceError(AppError):
    """Base service-layer error."""


class RepositoryError(Exception):
    """Base repository-layer error."""

    entity_name = "Record"

    @classmethod
    def inserted_missing(cls, entity_id: int) -> RepositoryError:
        return cls(f"{cls.entity_name} {entity_id} was inserted but could not be retrieved.")

    @classmethod
    def updated_missing(cls, entity_id: int) -> RepositoryError:
        return cls(f"{cls.entity_name} {entity_id} was updated but could not be retrieved.")

    @classmethod
    def invalid_update_fields(cls, fields: set[str]) -> RepositoryError:
        joined = ", ".join(sorted(fields))
        return cls(f"Invalid fields for update: {joined}")
    
    @classmethod
    def transaction_failed(cls, exc: Exception) -> RepositoryError:
        return cls(f"{cls.entity_name} transaction failed: {exc}")


class RowValidationError(TypeError):
    """Base error raised when a database row cannot be converted."""

    row_name = "row"

    @classmethod
    def invalid_type(cls, field: str, expected: str) -> RowValidationError:
        return cls(f"Invalid {cls.row_name} row: '{field}' must be {expected}")
