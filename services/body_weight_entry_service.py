"""User-owned body weight operations with one entry per user and measurement date."""

import logging
from datetime import date

from core.errors.body_weight_entry import (
    BodyWeightEntryCreationError,
    BodyWeightEntryDateConflictError,
    BodyWeightEntryNotFoundError,
    BodyWeightEntryUpdateError,
)
from core.errors.repository import BodyWeightEntryDateConflictRepositoryError, BodyWeightEntryRepositoryError
from ports.repositories.body_weight_entry_repository import BodyWeightEntryRepositoryPort
from schemas.body_weight_entry_schema import BodyWeightEntryCreate, BodyWeightEntryPublic, BodyWeightEntryUpdate
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET


class BodyWeightEntryService:
    """Apply ownership and date uniqueness rules to validated body weight entries.

    Callers supply the authenticated user's ID. Reads and mutations remain
    user-scoped. Early date checks give clear conflict responses; the database
    constraint also protects writes when another request wins a race.
    Weights are stored in kilograms without conversion in this service. The
    schemas enforce DECIMAL(5,2): positive values up to 999.99, with at most
    two decimal places, so writes need no rounding or truncation here.
    """

    def __init__(self, body_weight_entry_repo: BodyWeightEntryRepositoryPort) -> None:
        """Initialize the service with its persistence dependency.

        Args:
            body_weight_entry_repo: Repository implementing user-scoped body weight operations.
        """
        self.body_weight_entry_repo = body_weight_entry_repo
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, body_weight_entry_data: BodyWeightEntryCreate) -> BodyWeightEntryPublic:
        """Create an entry on a date not already occupied by this user.

        Args:
            user_id: Authenticated owner user ID.
            body_weight_entry_data: Validated date and positive kilogram weight with at most
                three integer digits and two decimal places.

        Returns:
            The persisted entry with its assigned ID and creation timestamp.

        Raises:
            BodyWeightEntryDateConflictError: If the date is occupied, including a concurrent insertion.
            BodyWeightEntryCreationError: If the repository cannot create or retrieve the entry.
            DatabaseError: If a database operation fails for another reason.
            BodyWeightEntryRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        existing_entry = self.body_weight_entry_repo.get_by_user_and_date(
            user_id, body_weight_entry_data.entry_date
        )
        if existing_entry is not None:
            self.logger.warning("Body weight entry date already occupied | user_id=%s", user_id)
            raise BodyWeightEntryDateConflictError.already_exists(body_weight_entry_data.entry_date)
        try:
            entry = self.body_weight_entry_repo.create(user_id, body_weight_entry_data)
        except BodyWeightEntryDateConflictRepositoryError as exc:
            raise BodyWeightEntryDateConflictError.already_exists(exc.entry_date) from exc
        except BodyWeightEntryRepositoryError as exc:
            self.logger.exception(f"Failed to create body weight entry for user {user_id}!")
            raise BodyWeightEntryCreationError.create_failed() from exc

        self.logger.info(f"Body weight entry created successfully for user {user_id} with entry ID {entry.id}")
        return entry

    def get_by_id(self, user_id: int, entry_id: int) -> BodyWeightEntryPublic:
        """Retrieve an entry belonging to the authenticated user.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body weight entry ID.

        Returns:
            The matching entry after the repository checks ownership.

        Raises:
            BodyWeightEntryNotFoundError: If the entry is missing or belongs to another user.
            DatabaseError: If the lookup fails.
            BodyWeightEntryRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_weight_entry_repo.get_by_user_and_id(user_id, entry_id)
        if entry is None:
            self.logger.warning(
                "Body weight entry not found or inaccessible | user_id=%s body_weight_entry_id=%s",
                user_id,
                entry_id,
            )
            raise BodyWeightEntryNotFoundError.not_found(entry_id)

        self.logger.debug("Body weight entry retrieved | user_id=%s entry_id=%s", user_id, entry_id)
        return entry

    def get_by_date(self, user_id: int, entry_date: date) -> BodyWeightEntryPublic:
        """Retrieve the authenticated user's entry for an exact date.

        Args:
            user_id: Authenticated owner user ID.
            entry_date: Measurement date to look up.

        Returns:
            The user's entry for the requested date.

        Raises:
            BodyWeightEntryNotFoundError: If no owned entry matches; the message identifies the date.
            DatabaseError: If the lookup fails.
            BodyWeightEntryRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_weight_entry_repo.get_by_user_and_date(user_id, entry_date)
        if entry is None:
            self.logger.warning(
                "Body weight entry not found or inaccessible | user_id=%s body_weight_entry_date=%s",
                user_id,
                entry_date,
            )
            raise BodyWeightEntryNotFoundError.not_found_by_date(entry_date)

        self.logger.debug(
            "Body weight entry retrieved | user_id=%s entry_id=%s entry_date=%s",
            user_id,
            entry.id,
            entry_date,
        )
        return entry

    def get_latest(self, user_id: int) -> BodyWeightEntryPublic:
        """Retrieve the latest entry by measurement date, then ID.

        Args:
            user_id: Authenticated owner user ID.

        Returns:
            The most recent owned entry, ordered by entry date rather than insertion time.

        Raises:
            BodyWeightEntryNotFoundError: If the user has no entries.
            DatabaseError: If the lookup fails.
            BodyWeightEntryRowError: If the returned row has invalid types.
            ValidationError: If the returned row violates the public schema.
        """
        entry = self.body_weight_entry_repo.get_latest_for_user(user_id)
        if entry is None:
            self.logger.warning(
                "Body weight entry not found or inaccessible | user_id=%s",
                user_id,
            )
            raise BodyWeightEntryNotFoundError.no_entries(user_id)

        self.logger.debug("Body weight entry retrieved | user_id=%s entry_id=%s", user_id, entry.id)
        return entry

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BodyWeightEntryPublic]:
        """List the user's entries in descending measurement-date and ID order.

        Args:
            user_id: Authenticated owner user ID.
            limit: Maximum entries; the repository applies shared pagination bounds.
            offset: Entries to skip; the repository clamps negative values to zero.
            date_from: Optional inclusive lower date bound.
            date_to: Optional inclusive upper date bound.

        Returns:
            Matching entries, or [] for an empty history, exhausted page, or reversed date range.

        Raises:
            DatabaseError: If the listing fails.
            BodyWeightEntryRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        entries = self.body_weight_entry_repo.list_by_user(user_id, limit, offset, date_from, date_to)
        self.logger.debug(
            "Body weight entries listed | user_id=%s count=%s limit=%s offset=%s",
            user_id,
            len(entries),
            limit,
            offset,
        )

        return entries

    def update(self, user_id: int, entry_id: int, update_data: BodyWeightEntryUpdate) -> BodyWeightEntryPublic:
        """Partially update an owned entry after checking date availability.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body weight entry ID.
            update_data: Validated weight or date changes. Omitted and None-valued fields
                preserve stored values. Keeping the current date is valid.

        Returns:
            The resulting entry, or its current values for an empty update.

        Raises:
            BodyWeightEntryNotFoundError: If missing, unowned, or disappearing during persistence.
            BodyWeightEntryDateConflictError: If another owned entry occupies the requested date,
                including a database uniqueness race after the initial check.
            BodyWeightEntryUpdateError: If the repository rejects or cannot complete the update.
            DatabaseError: If a database operation fails for another reason.
            BodyWeightEntryRowError: If a returned row has invalid types.
            ValidationError: If a returned row violates the public schema.
        """
        existing_entry = self.body_weight_entry_repo.get_by_user_and_id(user_id, entry_id)
        if existing_entry is None:
            self.logger.warning("Body weight entry not found | user_id=%s entry_id=%s", user_id, entry_id)
            raise BodyWeightEntryNotFoundError.not_found(entry_id)

        if update_data.entry_date is not None and update_data.entry_date != existing_entry.entry_date:
            conflict = self.body_weight_entry_repo.get_by_user_and_date(user_id, update_data.entry_date)
            if conflict is not None and conflict.id != entry_id:
                self.logger.warning(
                    "Body weight date change rejected | user_id=%s entry_id=%s", user_id, entry_id
                )
                raise BodyWeightEntryDateConflictError.already_exists(update_data.entry_date)

        try:
            updated_entry = self.body_weight_entry_repo.update_owned(user_id, entry_id, update_data)
        except BodyWeightEntryDateConflictRepositoryError as exc:
            raise BodyWeightEntryDateConflictError.already_exists(exc.entry_date) from exc
        except BodyWeightEntryRepositoryError as exc:
            self.logger.exception(f"Failed to update body weight entry with ID {entry_id} for user {user_id}.")
            raise BodyWeightEntryUpdateError.update_failed(entry_id) from exc

        if updated_entry is None:
            self.logger.warning(
                "Body weight entry not found during update | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyWeightEntryNotFoundError.not_accessible(entry_id)

        self.logger.info("Body weight entry updated | user_id=%s entry_id=%s", user_id, entry_id)
        return updated_entry

    def delete(self, user_id: int, entry_id: int) -> None:
        """Delete one body weight entry belonging to the authenticated user.

        Args:
            user_id: Authenticated owner user ID.
            entry_id: Body weight entry ID.

        Returns:
            None after successful deletion.

        Raises:
            BodyWeightEntryNotFoundError: If missing, unowned, or deleted after the ownership check.
            BodyWeightEntryRepositoryError: If the repository rejects the deletion.
            DatabaseError: If the lookup or deletion fails.
            BodyWeightEntryRowError: If the ownership lookup returns invalid row types.
            ValidationError: If the ownership lookup violates the public schema.
        """
        entry = self.body_weight_entry_repo.get_by_user_and_id(user_id, entry_id)
        if entry is None:
            self.logger.warning(
                "Body weight entry not found during deletion | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyWeightEntryNotFoundError.not_found(entry_id)

        deleted = self.body_weight_entry_repo.delete_owned(user_id, entry_id)
        if not deleted:
            self.logger.warning(
                "Body weight entry deletion affected no row | user_id=%s entry_id=%s", user_id, entry_id
            )
            raise BodyWeightEntryNotFoundError.not_accessible(entry_id)

        self.logger.info("Body weight entry deleted | user_id=%s entry_id=%s", user_id, entry_id)
