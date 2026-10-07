"""Typed validation helpers for database rows, preserving entity-specific errors."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from core.errors.base import RowValidationError


@dataclass(frozen=True, slots=True)
class RowValidator:
    """Bind reusable checks to the row error class belonging to a mapper.

    Checks preserve the mappers' existing isinstance semantics. Pydantic models
    remain responsible for value constraints such as positive weights and dates.
    """

    error_type: type[RowValidationError] = RowValidationError

    def _require[T](self, value: object, field: str, value_type: type[T]) -> T:
        if not isinstance(value, value_type):
            raise self.error_type.invalid_type(field, value_type.__name__)
        return value

    def _require_optional[T](self, value: object, field: str, value_type: type[T]) -> T | None:
        if value is None:
            return None
        if not isinstance(value, value_type):
            raise self.error_type.invalid_type(field, f"{value_type.__name__} | None")
        return value

    def require_int(self, value: object, field: str) -> int:
        """Require an integer using the existing database mapper type rules."""
        return self._require(value, field, int)

    def require_optional_int(self, value: object, field: str) -> int | None:
        """Require an integer or None."""
        return self._require_optional(value, field, int)

    def require_str(self, value: object, field: str) -> str:
        """Require a string without trimming or coercing its contents."""
        return self._require(value, field, str)

    def require_optional_str(self, value: object, field: str) -> str | None:
        """Require a string or None."""
        return self._require_optional(value, field, str)

    def require_bool(self, value: object, field: str) -> bool:
        """Require a boolean without accepting integers or strings."""
        return self._require(value, field, bool)

    def require_date(self, value: object, field: str) -> date:
        """Require a date using the existing mapper rules for date subclasses."""
        return self._require(value, field, date)

    def require_optional_date(self, value: object, field: str) -> date | None:
        """Require a date or None."""
        return self._require_optional(value, field, date)

    def require_datetime(self, value: object, field: str) -> datetime:
        """Require a datetime without parsing date strings."""
        return self._require(value, field, datetime)

    def require_optional_datetime(self, value: object, field: str) -> datetime | None:
        """Require a datetime or None."""
        return self._require_optional(value, field, datetime)

    def require_numeric(self, value: object, field: str) -> Decimal | int | float:
        """Require an existing numeric value; conversion remains the mapper's choice."""
        if not isinstance(value, (Decimal, int, float)):
            raise self.error_type.invalid_type(field, "numeric")
        return value

    def require_optional_numeric(self, value: object, field: str) -> Decimal | int | float | None:
        """Require a numeric value or None, preserving the nullable error message."""
        if value is None:
            return None
        if not isinstance(value, (Decimal, int, float)):
            raise self.error_type.invalid_type(field, "numeric | None")
        return value

    def require_optional_decimal(self, value: object, field: str) -> Decimal | None:
        """Normalize nullable measurements through str, preserving float conversion."""
        normalized = self.require_optional_numeric(value, field)
        if normalized is None:
            return None
        return Decimal(str(normalized))
