"""Persistence contract for user-owned body measurement entries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from datetime import date

    from schemas.body_measurement_schema import (
        BodyMeasurementCreate,
        BodyMeasurementPublic,
        BodyMeasurementUpdate,
    )


class BodyMeasurementRepositoryPort(Protocol):
    """Store and retrieve validated body measurements with user-scoped operations.

    Implementations propagate existing database, row-validation, and repository
    errors for persistence failures. Missing or unowned entries return None or
    False as documented; services decide whether to raise a not-found error.
    """

    def create(self, user_id: int, entry_data: BodyMeasurementCreate) -> BodyMeasurementPublic:
        """Create an entry for the specified user and return the persisted values.

        Raise BodyMeasurementRepositoryError if the inserted entry cannot be
        retrieved afterwards.
        """
        ...

    def get_by_id(self, entry_id: int) -> BodyMeasurementPublic | None:
        """Return an entry by ID, or None if it does not exist.

        This lookup does not check ownership. Callers must verify access before
        exposing the entry or use get_by_user_and_id instead.
        """
        ...

    def get_by_user_and_id(self, user_id: int, entry_id: int) -> BodyMeasurementPublic | None:
        """Return the entry only if owned by the user; otherwise return None."""
        ...

    def get_by_user_and_date(self, user_id: int, entry_date: date) -> BodyMeasurementPublic | None:
        """Return the user's entry for the exact date, or None if absent."""
        ...

    def get_latest_for_user(self, user_id: int) -> BodyMeasurementPublic | None:
        """Return the user's latest entry by entry date, then ID, or None if empty."""
        ...

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BodyMeasurementPublic]:
        """List the user's entries in descending entry-date and ID order.

        Date bounds are optional and inclusive. Use shared pagination defaults
        and normalization; return an empty list when no entries match.
        """
        ...

    def update_owned(
        self,
        user_id: int,
        entry_id: int,
        update_data: BodyMeasurementUpdate,
    ) -> BodyMeasurementPublic | None:
        """Partially update an entry owned by the user and return the result.

        Omitted and None-valued fields retain their stored values, so nullable
        measurements and notes cannot be cleared through this operation. An
        empty update returns the current entry. Return None for a missing or
        unowned entry. Unsupported fields raise BodyMeasurementRepositoryError.
        """
        ...

    def delete_owned(self, user_id: int, entry_id: int) -> bool:
        """Delete an owned entry; return False if missing or owned by another user."""
        ...
