"""
Body Weight Entry Repository

This module handles all database interactions for the BodyWeightEntry entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from psycopg.errors import UniqueViolation

from core.errors.database import DatabaseError
from core.errors.repository import BodyWeightEntryDateConflictRepositoryError, BodyWeightEntryRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.body_weight_entry import map_body_weight_entry
from data.queries import QUERIES
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET, normalize_pagination

if TYPE_CHECKING:
    from datetime import date

    from schemas.body_weight_entry_schema import (
        BodyWeightEntryCreate,
        BodyWeightEntryPublic,
        BodyWeightEntryUpdate,
    )


logger = logging.getLogger(__name__)


def _is_date_conflict(error: DatabaseError) -> bool:
    """Recognize only the PostgreSQL uniqueness constraint on user and measurement date.

    Args:
        error: Database error whose explicit cause is the original driver error.

    Returns:
        True only for the body-weight user/date constraint. Other constraints
        and message text do not identify a date conflict.
    """
    cause = error.__cause__
    return (
        isinstance(cause, UniqueViolation)
        and cause.diag.constraint_name == "body_weight_entries_user_id_entry_date_key"
    )


class BodyWeightEntryRepository:
    """
    Repository for BodyWeightEntry database operations.

    Responsibilities:
    - Execute SQL queries related to body weight entries
    - Convert database row dicts to BodyWeightEntryPublic models
    - Handle all body-weight-related database logic
    """

    _BODY_WEIGHT_ENTRY_UPDATE_WHITELIST: Final[set[str]] = {
        "weight",
        "entry_date",
    }

    def create(
        self,
        user_id: int,
        entry_data: BodyWeightEntryCreate,
    ) -> BodyWeightEntryPublic:
        """
        Create a new body weight entry for a user.

        Args:
            user_id: Owner user ID.
            entry_data: Entry creation payload.

        Returns:
            The newly created body weight entry.

        Raises:
            BodyWeightEntryRepositoryError: If the inserted row cannot be retrieved afterwards.
            BodyWeightEntryDateConflictRepositoryError: If the user already has an entry on the date,
                including a concurrent insertion after a service-level availability check.
        """
        try:
            entry_id = execute_insert(
                QUERIES.body_weight_entries.create,
                (user_id, entry_data.weight, entry_data.entry_date),
            )
        except DatabaseError as exc:
            if _is_date_conflict(exc):
                raise BodyWeightEntryDateConflictRepositoryError(entry_data.entry_date) from exc
            raise

        entry = self.get_by_id(entry_id)
        if entry is None:
            logger.warning("Inserted row missing during readback | entity_id=%s", entry_id)
            raise BodyWeightEntryRepositoryError.inserted_missing(entry_id)
        return entry

    def get_by_id(self, entry_id: int) -> BodyWeightEntryPublic | None:
        """Retrieve a body weight entry by its database ID.

        Args:
            entry_id: Entry ID.

        Returns:
            The entry if found, otherwise None.

        This lookup does not authorize access; services must verify ownership or visibility.
        """
        row = fetch_one(QUERIES.body_weight_entries.get_by_id, (entry_id,))
        if row is None:
            return None
        return map_body_weight_entry(row)

    def get_by_user_and_id(
        self,
        user_id: int,
        entry_id: int,
    ) -> BodyWeightEntryPublic | None:
        """
        Retrieve a body weight entry by ID only if it belongs to the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.

        Returns:
            The entry if found and owned by the user, otherwise None.
        """
        row = fetch_one(
            QUERIES.body_weight_entries.get_by_user_and_id,
            (user_id, entry_id),
        )
        if row is None:
            return None
        return map_body_weight_entry(row)

    def get_by_user_and_date(
        self,
        user_id: int,
        entry_date: date,
    ) -> BodyWeightEntryPublic | None:
        """
        Retrieve a body weight entry for a user by date.

        Args:
            user_id: Owner user ID.
            entry_date: Entry date.

        Returns:
            The entry if found, otherwise None.
        """
        row = fetch_one(
            QUERIES.body_weight_entries.get_by_user_and_date,
            (user_id, entry_date),
        )
        if row is None:
            return None
        return map_body_weight_entry(row)

    def get_latest_for_user(self, user_id: int) -> BodyWeightEntryPublic | None:
        """
        Retrieve the most recent body weight entry for a user.

        Args:
            user_id: Owner user ID.

        Returns:
            The latest entry if one exists, otherwise None.
        """
        row = fetch_one(
            QUERIES.body_weight_entries.get_latest_for_user,
            (user_id,),
        )
        if row is None:
            return None
        return map_body_weight_entry(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BodyWeightEntryPublic]:
        """
        List body weight entries for a user with pagination and date filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `entry_date`.
            date_to: Optional inclusive upper bound for `entry_date`.

        Returns:
            Entries ordered from newest to oldest.
        """
        pagination = normalize_pagination(limit, offset)

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.body_weight_entries.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.body_weight_entries.filter_date_to)
            params.append(date_to)

        sql = QUERIES.body_weight_entries.list_by_user.format(filters=" ".join(filters))
        params.extend([pagination.limit, pagination.offset])

        rows = fetch_all(sql, tuple(params))
        return [map_body_weight_entry(row) for row in rows]

    def update_owned(
        self,
        user_id: int,
        entry_id: int,
        update_data: BodyWeightEntryUpdate,
    ) -> BodyWeightEntryPublic | None:
        """
        Partially update a body weight entry owned by the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.
            update_data: Partial update payload.

        Returns:
            The updated entry if found, otherwise None.

        Raises:
            BodyWeightEntryRepositoryError: If any provided fields are not allowed to be updated.
            BodyWeightEntryDateConflictRepositoryError: If another entry for this user occupies
                the requested date. Keeping the current date is valid.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, entry_id)

        unknown = set(fields) - self._BODY_WEIGHT_ENTRY_UPDATE_WHITELIST
        if unknown:
            logger.warning("Unsupported update fields rejected | field_count=%s", len(unknown))
            raise BodyWeightEntryRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.body_weight_entries.update_owned.format(set_clause=set_clause)
        try:
            execute_write(sql, (*fields.values(), user_id, entry_id))
        except DatabaseError as exc:
            if update_data.entry_date is not None and _is_date_conflict(exc):
                raise BodyWeightEntryDateConflictRepositoryError(update_data.entry_date) from exc
            raise
        return self.get_by_user_and_id(user_id, entry_id)

    def delete_owned(self, user_id: int, entry_id: int) -> bool:
        """
        Delete a body weight entry owned by the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                QUERIES.body_weight_entries.delete_owned,
                (user_id, entry_id),
            )
            > 0
        )
