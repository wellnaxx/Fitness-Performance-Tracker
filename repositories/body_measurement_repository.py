"""
Body Measurement Repository

This module handles all database interactions for the BodyMeasurement entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.body_measurement_schema import (
    BodyMeasurementCreate,
    BodyMeasurementPublic,
    BodyMeasurementUpdate,
)
from core.errors.repository import BodyMeasurementRepositoryError, BodyMeasurementRowError


class BodyMeasurementRow(TypedDict):
    id: int
    user_id: int
    entry_date: date
    neck: Decimal | None
    shoulders: Decimal | None
    waist: Decimal | None
    chest: Decimal | None
    hips: Decimal | None
    left_bicep: Decimal | None
    right_bicep: Decimal | None
    left_forearm: Decimal | None
    right_forearm: Decimal | None
    left_thigh: Decimal | None
    right_thigh: Decimal | None
    left_calf: Decimal | None
    right_calf: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BodyMeasurementRepository:
    """
    Repository for BodyMeasurement database operations.

    Responsibilities:
    - Execute SQL queries related to body measurements
    - Convert database row dicts to BodyMeasurementPublic models
    - Handle all body-measurement-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, user_id, entry_date, neck, shoulders, waist, chest, hips,
               left_bicep, right_bicep, left_forearm, right_forearm,
               left_thigh, right_thigh, left_calf, right_calf,
               notes, created_at, updated_at
        FROM body_measurements
    """

    _BODY_MEASUREMENT_UPDATE_WHITELIST: Final[set[str]] = {
        "entry_date",
        "neck",
        "shoulders",
        "waist",
        "chest",
        "hips",
        "left_bicep",
        "right_bicep",
        "left_forearm",
        "right_forearm",
        "left_thigh",
        "right_thigh",
        "left_calf",
        "right_calf",
        "notes",
    }

    def create(
        self,
        user_id: int,
        entry_data: BodyMeasurementCreate,
    ) -> BodyMeasurementPublic:
        """
        Create a new body measurement entry for a user.

        Args:
            user_id: Owner user ID.
            entry_data: Entry creation payload.

        Returns:
            The newly created body measurement entry.

        Raises:
            BodyMeasurementRepositoryError: If the inserted row cannot be retrieved afterwards.
        """
        entry_id = execute_insert(
            """
            INSERT INTO body_measurements
            (user_id, entry_date, neck, shoulders, waist, chest, hips,
             left_bicep, right_bicep, left_forearm, right_forearm,
             left_thigh, right_thigh, left_calf, right_calf, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                entry_data.entry_date,
                entry_data.neck,
                entry_data.shoulders,
                entry_data.waist,
                entry_data.chest,
                entry_data.hips,
                entry_data.left_bicep,
                entry_data.right_bicep,
                entry_data.left_forearm,
                entry_data.right_forearm,
                entry_data.left_thigh,
                entry_data.right_thigh,
                entry_data.left_calf,
                entry_data.right_calf,
                entry_data.notes,
            ),
        )

        entry = self.get_by_id(entry_id)
        if entry is None:
            raise BodyMeasurementRepositoryError.inserted_missing(entry_id)
        return entry

    def get_by_id(self, entry_id: int) -> BodyMeasurementPublic | None:
        """
        Retrieve a body measurement entry by its database ID.

        Args:
            entry_id: Entry ID.

        Returns:
            The entry if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (entry_id,))
        if row is None:
            return None
        return self._row_to_body_measurement(row)

    def get_by_user_and_id(
        self,
        user_id: int,
        entry_id: int,
    ) -> BodyMeasurementPublic | None:
        """
        Retrieve a body measurement entry by ID only if it belongs to the user.

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
        return self._row_to_body_measurement(row)

    def get_by_user_and_date(
        self,
        user_id: int,
        entry_date: date,
    ) -> BodyMeasurementPublic | None:
        """
        Retrieve a body measurement entry for a user by date.

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
        return self._row_to_body_measurement(row)

    def get_latest_for_user(self, user_id: int) -> BodyMeasurementPublic | None:
        """
        Retrieve the most recent body measurement entry for a user.

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
        return self._row_to_body_measurement(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[BodyMeasurementPublic]:
        """
        List body measurement entries for a user with pagination and date filters.

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
        return [self._row_to_body_measurement(row) for row in rows]

    def update_owned(
        self,
        user_id: int,
        entry_id: int,
        update_data: BodyMeasurementUpdate,
    ) -> BodyMeasurementPublic | None:
        """
        Partially update a body measurement entry owned by the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.
            update_data: Partial update payload.

        Returns:
            The updated entry if found, otherwise None.

        Raises:
            BodyMeasurementRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, entry_id)

        unknown = set(fields) - self._BODY_MEASUREMENT_UPDATE_WHITELIST
        if unknown:
            raise BodyMeasurementRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = (
            f"UPDATE body_measurements SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND id = %s"
        )
        execute_write(sql, (*fields.values(), user_id, entry_id))
        return self.get_by_user_and_id(user_id, entry_id)

    def delete_owned(self, user_id: int, entry_id: int) -> bool:
        """
        Delete a body measurement entry owned by the user.

        Args:
            user_id: Owner user ID.
            entry_id: Entry ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                "DELETE FROM body_measurements WHERE user_id = %s AND id = %s",
                (user_id, entry_id),
            )
            > 0
        )

    @staticmethod
    def _to_decimal_or_none(field_name: str, value: object) -> Decimal | None:
        """Convert a numeric database value into Decimal while preserving None."""
        if value is None:
            return None
        if not isinstance(value, (Decimal, int, float)):
            raise BodyMeasurementRowError.invalid_type(field_name, "numeric | None")
        return Decimal(str(value))

    @classmethod
    def _parse_body_measurement_row(
        cls,
        row: dict[str, object],
    ) -> BodyMeasurementRow:
        """Validate and normalize a raw database row into a typed BodyMeasurementRow."""
        id_value = row.get("id")
        user_id = row.get("user_id")
        entry_date = row.get("entry_date")
        notes = row.get("notes")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        if not isinstance(id_value, int):
            raise BodyMeasurementRowError.invalid_type("id", "int")
        if not isinstance(user_id, int):
            raise BodyMeasurementRowError.invalid_type("user_id", "int")
        if not isinstance(entry_date, date):
            raise BodyMeasurementRowError.invalid_type("entry_date", "date")
        if notes is not None and not isinstance(notes, str):
            raise BodyMeasurementRowError.invalid_type("notes", "str | None")
        if not isinstance(created_at, datetime):
            raise BodyMeasurementRowError.invalid_type("created_at", "datetime")
        if not isinstance(updated_at, datetime):
            raise BodyMeasurementRowError.invalid_type("updated_at", "datetime")

        return BodyMeasurementRow(
            id=id_value,
            user_id=user_id,
            entry_date=entry_date,
            neck=cls._to_decimal_or_none("neck", row.get("neck")),
            shoulders=cls._to_decimal_or_none("shoulders", row.get("shoulders")),
            waist=cls._to_decimal_or_none("waist", row.get("waist")),
            chest=cls._to_decimal_or_none("chest", row.get("chest")),
            hips=cls._to_decimal_or_none("hips", row.get("hips")),
            left_bicep=cls._to_decimal_or_none("left_bicep", row.get("left_bicep")),
            right_bicep=cls._to_decimal_or_none("right_bicep", row.get("right_bicep")),
            left_forearm=cls._to_decimal_or_none("left_forearm", row.get("left_forearm")),
            right_forearm=cls._to_decimal_or_none("right_forearm", row.get("right_forearm")),
            left_thigh=cls._to_decimal_or_none("left_thigh", row.get("left_thigh")),
            right_thigh=cls._to_decimal_or_none("right_thigh", row.get("right_thigh")),
            left_calf=cls._to_decimal_or_none("left_calf", row.get("left_calf")),
            right_calf=cls._to_decimal_or_none("right_calf", row.get("right_calf")),
            notes=notes,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _row_to_body_measurement(
        cls,
        row: dict[str, object],
    ) -> BodyMeasurementPublic:
        """Convert a raw database row into a validated BodyMeasurementPublic model."""
        measurement_row = cls._parse_body_measurement_row(row)
        return BodyMeasurementPublic.model_validate(measurement_row)
