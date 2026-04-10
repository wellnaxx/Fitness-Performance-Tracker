"""
Body Weight Entry Repository

This module handles all database interactions for the BodyWeightEntry entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.body_weight_entry_schema import (
    BodyWeightEntryCreate,
    BodyWeightEntryPublic,
    BodyWeightEntryUpdate,
)
from utils.errors import BodyWeightEntryRepositoryError, BodyWeightEntryRowError


class BodyWeightEntryRow(TypedDict):
    id: int
    user_id: int
    weight: Decimal
    entry_date: date
    created_at: datetime


class BodyWeightEntryRepository:
    """
    Repository for BodyWeightEntry database operations.

    Responsibilities:
    - Execute SQL queries related to body weight entries
    - Convert database row dicts to BodyWeightEntryPublic models
    - Handle all body-weight-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, user_id, weight, entry_date, created_at
        FROM body_weight_entries
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
        """
        entry_id = execute_insert(
            """
            INSERT INTO body_weight_entries (user_id, weight, entry_date)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (user_id, entry_data.weight, entry_data.entry_date),
        )

        entry = self.get_by_id(entry_id)
        if entry is None:
            raise BodyWeightEntryRepositoryError.inserted_missing(entry_id)
        return entry

    def get_by_id(self, entry_id: int) -> BodyWeightEntryPublic | None:
        """
        Retrieve a body weight entry by its database ID.

        Args:
            entry_id: Entry ID.

        Returns:
            The entry if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (entry_id,))
        if row is None:
            return None
        return self._row_to_body_weight_entry(row)

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
            f"{self._BASE_SELECT} WHERE user_id = %s AND id = %s",
            (user_id, entry_id),
        )
        if row is None:
            return None
        return self._row_to_body_weight_entry(row)

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
            f"{self._BASE_SELECT} WHERE user_id = %s AND entry_date = %s",
            (user_id, entry_date),
        )
        if row is None:
            return None
        return self._row_to_body_weight_entry(row)

    def get_latest_for_user(self, user_id: int) -> BodyWeightEntryPublic | None:
        """
        Retrieve the most recent body weight entry for a user.

        Args:
            user_id: Owner user ID.

        Returns:
            The latest entry if one exists, otherwise None.
        """
        row = fetch_one(
            f"{self._BASE_SELECT} WHERE user_id = %s ORDER BY entry_date DESC, id DESC LIMIT 1",
            (user_id,),
        )
        if row is None:
            return None
        return self._row_to_body_weight_entry(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
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
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        sql = f"{self._BASE_SELECT} WHERE user_id = %s"
        params: list[object] = [user_id]

        if date_from is not None:
            sql += " AND entry_date >= %s"
            params.append(date_from)

        if date_to is not None:
            sql += " AND entry_date <= %s"
            params.append(date_to)

        sql += " ORDER BY entry_date DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_body_weight_entry(row) for row in rows]

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
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, entry_id)

        unknown = set(fields) - self._BODY_WEIGHT_ENTRY_UPDATE_WHITELIST
        if unknown:
            raise BodyWeightEntryRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = f"UPDATE body_weight_entries SET {set_clause} WHERE user_id = %s AND id = %s"
        execute_write(sql, (*fields.values(), user_id, entry_id))
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
                "DELETE FROM body_weight_entries WHERE user_id = %s AND id = %s",
                (user_id, entry_id),
            )
            > 0
        )

    @staticmethod
    def _parse_body_weight_entry_row(
        row: dict[str, object],
    ) -> BodyWeightEntryRow:
        """Validate and normalize a raw database row into a typed BodyWeightEntryRow."""
        id_value = row.get("id")
        user_id = row.get("user_id")
        weight = row.get("weight")
        entry_date = row.get("entry_date")
        created_at = row.get("created_at")

        if not isinstance(id_value, int):
            raise BodyWeightEntryRowError.invalid_type("id", "int")
        if not isinstance(user_id, int):
            raise BodyWeightEntryRowError.invalid_type("user_id", "int")
        if not isinstance(weight, (Decimal, int, float)):
            raise BodyWeightEntryRowError.invalid_type("weight", "numeric")
        if not isinstance(entry_date, date):
            raise BodyWeightEntryRowError.invalid_type("entry_date", "date")
        if not isinstance(created_at, datetime):
            raise BodyWeightEntryRowError.invalid_type("created_at", "datetime")

        return BodyWeightEntryRow(
            id=id_value,
            user_id=user_id,
            weight=Decimal(str(weight)),
            entry_date=entry_date,
            created_at=created_at,
        )

    @classmethod
    def _row_to_body_weight_entry(
        cls,
        row: dict[str, object],
    ) -> BodyWeightEntryPublic:
        """Convert a raw database row into a validated BodyWeightEntryPublic model."""
        entry_row = cls._parse_body_weight_entry_row(row)
        return BodyWeightEntryPublic.model_validate(entry_row)
