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
        """Create an entry for the specified user.

        Args:
            user_id: Owner user ID.
            entry_data: Validated creation values including the measurement date.

        Returns:
            The persisted entry with its assigned ID and timestamps.

        Raises:
            BodyMeasurementRepositoryError: If the inserted entry cannot be retrieved afterwards.
            BodyMeasurementDateConflictRepositoryError: If the database rejects an occupied user/date.
        """
        ...

    def get_by_id(self, entry_id: int) -> BodyMeasurementPublic | None:
        """Retrieve an entry without checking ownership.

        Args:
            entry_id: Entry ID. Callers must separately verify access before exposing the result.

        Returns:
            The matching entry, or None if absent. Use get_by_user_and_id for an owned lookup.
        """
        ...

    def get_by_user_and_id(self, user_id: int, entry_id: int) -> BodyMeasurementPublic | None:
        """Retrieve an entry within a user's history.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.

        Returns:
            The owned entry, or None if missing or owned by another user.
        """
        ...

    def get_by_user_and_date(self, user_id: int, entry_date: date) -> BodyMeasurementPublic | None:
        """Retrieve the user's entry for an exact date.

        Args:
            user_id: Owner user ID.
            entry_date: Exact measurement date.

        Returns:
            The matching entry, or None if the user has no entry on that date.
        """
        ...

    def get_latest_for_user(self, user_id: int) -> BodyMeasurementPublic | None:
        """Retrieve the user's most recent entry.

        Args:
            user_id: Owner user ID.

        Returns:
            The latest entry by entry date, then ID, or None for an empty history.
        """
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

        Args:
            user_id: Owner user ID.
            limit: Maximum entries, normalized to the shared pagination bounds.
            offset: Entries to skip, normalized to the shared pagination bounds.
            date_from: Optional inclusive lower date bound.
            date_to: Optional inclusive upper date bound.

        Returns:
            Matching entries, or an empty list when none match.
        """
        ...

    def update_owned(
        self,
        user_id: int,
        entry_id: int,
        update_data: BodyMeasurementUpdate,
    ) -> BodyMeasurementPublic | None:
        """Partially update an entry owned by the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.
            update_data: Fields to change. Omitted and None fields preserve stored values;
                nullable measurements and notes cannot be cleared through this operation.

        Returns:
            The updated entry, current values for an empty update, or None if missing or unowned.

        Raises:
            BodyMeasurementRepositoryError: If unsupported fields are supplied.
            BodyMeasurementDateConflictRepositoryError: If another entry for this user occupies
                the requested date, including a concurrent write after an availability check.
        """
        ...

    def delete_owned(self, user_id: int, entry_id: int) -> bool:
        """Delete an entry within the specified user's history.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.

        Returns:
            True if deleted; False if missing or owned by another user.
        """
        ...
