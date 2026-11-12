"""User-owned body measurement operations with one entry per user and date."""

import logging
from datetime import date

from core.errors.body_measurement import (
    BodyMeasurementCreationError,
    BodyMeasurementDateConflictError,
    BodyMeasurementNotFoundError,
    BodyMeasurementUpdateError,
)
from core.errors.repository import BodyMeasurementDateConflictRepositoryError, BodyMeasurementRepositoryError
from ports.repositories.body_measurement_repository import BodyMeasurementRepositoryPort
from schemas.body_measurement_schema import BodyMeasurementCreate, BodyMeasurementPublic, BodyMeasurementUpdate
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET


class BodyMeasurementService:
    """Apply ownership and date uniqueness rules to validated measurement payloads.

    Callers supply the authenticated user's ID. Repository lookups and mutations
    are user-scoped. Duplicate checks provide an early conflict response; the
    database constraint remains authoritative for concurrent writes.
    """

    def __init__(self, body_measurement_repo: BodyMeasurementRepositoryPort) -> None:
        """Initialize the service with its persistence dependency.

        Args:
            body_measurement_repo: Repository implementing user-scoped measurement operations.
        """
        self.body_measurement_repo = body_measurement_repo
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, body_measurement_data: BodyMeasurementCreate) -> BodyMeasurementPublic:
        """Create one entry for a date not already occupied by this user.

        Args:
            user_id: Authenticated owner user ID.
            body_measurement_data: Validated date and at least one positive measurement.

        Returns:
            The persisted entry with its assigned ID and timestamps.

        Raises:
            BodyMeasurementDateConflictError: If the date is occupied, including a concurrent insertion.
            BodyMeasurementCreationError: If the repository cannot create or retrieve the new entry.
            DatabaseError: If a database operation fails for another reason.
            BodyMeasurementRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        existing_entry = self.body_measurement_repo.get_by_user_and_date(
            user_id, body_measurement_data.entry_date
        )
        if existing_entry is not None:
            self.logger.warning("Body measurement date already occupied | user_id=%s", user_id)
            raise BodyMeasurementDateConflictError.already_exists(body_measurement_data.entry_date)
        try:
            entry = self.body_measurement_repo.create(user_id, body_measurement_data)
        except BodyMeasurementDateConflictRepositoryError as exc:
            raise BodyMeasurementDateConflictError.already_exists(exc.entry_date) from exc
        except BodyMeasurementRepositoryError as exc:
            self.logger.exception(f"Failed to create body measurement entry for user {user_id}!")
            raise BodyMeasurementCreationError.create_failed() from exc

        self.logger.info(
            f"Body measurement entry created successfully for user {user_id} with entry ID {entry.id}"
        )
        return entry

    def get_by_id(self, user_id: int, entry_id: int) -> BodyMeasurementPublic:
        """Retrieve one entry belonging to the authenticated user.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body measurement entry ID.

        Returns:
            The matching entry after the repository checks ownership.

        Raises:
            BodyMeasurementNotFoundError: If the entry is missing or belongs to another user.
            DatabaseError: If the lookup fails.
            BodyMeasurementRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_measurement_repo.get_by_user_and_id(user_id, entry_id)
        if entry is None:
            self.logger.warning(
                "Body measurement entry not found or inaccessible | user_id=%s body_measurement_entry_id=%s",
                user_id,
                entry_id,
            )
            raise BodyMeasurementNotFoundError.not_found(entry_id)

        self.logger.debug("Body measurement entry retrieved | user_id=%s entry_id=%s", user_id, entry_id)
        return entry

    def get_by_date(self, user_id: int, entry_date: date) -> BodyMeasurementPublic:
        """Retrieve the authenticated user's entry for an exact date.

        Args:
            user_id: Authenticated owner user ID.
            entry_date: Date to look up.

        Returns:
            The user's entry for the requested date.

        Raises:
            BodyMeasurementNotFoundError: If no owned entry matches; the message identifies the date.
            DatabaseError: If the lookup fails.
            BodyMeasurementRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_measurement_repo.get_by_user_and_date(user_id, entry_date)
        if entry is None:
            self.logger.warning(
                "Body measurement entry not found or inaccessible | user_id=%s body_measurement_entry_date=%s",
                user_id,
                entry_date,
            )
            raise BodyMeasurementNotFoundError.not_found_by_date(entry_date)

        self.logger.debug(
            "Body measurement entry retrieved | user_id=%s entry_id=%s entry_date=%s",
            user_id,
            entry.id,
            entry_date,
        )
        return entry

    def get_latest(self, user_id: int) -> BodyMeasurementPublic:
        """Retrieve the user's latest entry by entry date, then ID.

        Args:
            user_id: Authenticated owner user ID.

        Returns:
            The most recent owned entry.

        Raises:
            BodyMeasurementNotFoundError: If the user has no entries.
            DatabaseError: If the lookup fails.
            BodyMeasurementRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_measurement_repo.get_latest_for_user(user_id)
        if entry is None:
            self.logger.warning(
                "Body measurement entry not found or inaccessible | user_id=%s",
                user_id,
            )
            raise BodyMeasurementNotFoundError.no_entries(user_id)

        self.logger.debug("Body measurement entry retrieved | user_id=%s entry_id=%s", user_id, entry.id)
        return entry

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BodyMeasurementPublic]:
        """List the authenticated user's entries in descending date and ID order.

        Args:
            user_id: Authenticated owner user ID.
            limit: Maximum entries to return; the repository applies shared pagination bounds.
            offset: Entries to skip; the repository clamps negative values to zero.
            date_from: Optional inclusive lower date bound.
            date_to: Optional inclusive upper date bound.

        Returns:
            Matching entries, or [] for an empty history, exhausted page, or reversed date range.

        Raises:
            DatabaseError: If the listing fails.
            BodyMeasurementRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        entries = self.body_measurement_repo.list_by_user(user_id, limit, offset, date_from, date_to)
        self.logger.debug(
            "Body measurement entries listed | user_id=%s count=%s limit=%s offset=%s",
            user_id,
            len(entries),
            limit,
            offset,
        )

        return entries

    def update(self, user_id: int, entry_id: int, update_data: BodyMeasurementUpdate) -> BodyMeasurementPublic:
        """Partially update an owned entry after checking ownership and date availability.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body measurement entry ID.
            update_data: Validated changes. Omitted and None fields preserve stored values,
                including nullable measurements and notes. Keeping the current date is valid.

        Returns:
            The resulting entry, or its current values for an empty update.

        Raises:
            BodyMeasurementNotFoundError: If the entry is missing, unowned, or disappears during persistence.
            BodyMeasurementDateConflictError: If another owned entry occupies the new date,
                including a database uniqueness race after the availability check.
            BodyMeasurementUpdateError: If the repository rejects or cannot complete the update.
            DatabaseError: If a database operation fails for another reason.
            BodyMeasurementRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        existing_entry = self.body_measurement_repo.get_by_user_and_id(user_id, entry_id)
        if existing_entry is None:
            self.logger.warning("Body measurement entry not found | user_id=%s entry_id=%s", user_id, entry_id)
            raise BodyMeasurementNotFoundError.not_found(entry_id)

        if update_data.entry_date is not None and update_data.entry_date != existing_entry.entry_date:
            conflict = self.body_measurement_repo.get_by_user_and_date(user_id, update_data.entry_date)
            if conflict is not None and conflict.id != entry_id:
                self.logger.warning(
                    "Body measurement date change rejected | user_id=%s entry_id=%s", user_id, entry_id
                )
                raise BodyMeasurementDateConflictError.already_exists(update_data.entry_date)

        try:
            updated_entry = self.body_measurement_repo.update_owned(user_id, entry_id, update_data)
        except BodyMeasurementDateConflictRepositoryError as exc:
            raise BodyMeasurementDateConflictError.already_exists(exc.entry_date) from exc
        except BodyMeasurementRepositoryError as exc:
            self.logger.exception(
                f"Failed to update body measurement entry with ID {entry_id} for user {user_id}."
            )
            raise BodyMeasurementUpdateError.update_failed(entry_id) from exc

        if updated_entry is None:
            self.logger.warning(
                "Body measurement entry not found during update | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyMeasurementNotFoundError.not_accessible(entry_id)

        self.logger.info("Body measurement entry updated | user_id=%s entry_id=%s", user_id, entry_id)
        return updated_entry

    def delete(self, user_id: int, entry_id: int) -> None:
        """Delete one body measurement entry belonging to the authenticated user.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body measurement entry ID.

        Returns:
            None after successful deletion.

        Raises:
            BodyMeasurementNotFoundError: If missing, unowned, or deleted after the ownership check.
            BodyMeasurementRepositoryError: If the repository rejects the deletion.
            DatabaseError: If the lookup or deletion fails.
            BodyMeasurementRowError: If the ownership lookup returns invalid row types.
            ValidationError: If the ownership lookup violates the public schema.
        """
        entry = self.body_measurement_repo.get_by_user_and_id(user_id, entry_id)
        if entry is None:
            self.logger.warning(
                "Body measurement entry not found during deletion | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyMeasurementNotFoundError.not_found(entry_id)

        deleted = self.body_measurement_repo.delete_owned(user_id, entry_id)
        if not deleted:
            self.logger.warning(
                "Body measurement entry deletion affected no row | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyMeasurementNotFoundError.not_accessible(entry_id)

        self.logger.info("Body measurement entry deleted | user_id=%s entry_id=%s", user_id, entry_id)
