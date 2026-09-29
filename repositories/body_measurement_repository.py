"""
Body Measurement Repository

This module handles all database interactions for the BodyMeasurement entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import BodyMeasurementRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.body_measurement import map_body_measurement
from data.queries import QUERIES

if TYPE_CHECKING:
    from datetime import date

    from schemas.body_measurement_schema import (
        BodyMeasurementCreate,
        BodyMeasurementPublic,
        BodyMeasurementUpdate,
    )


class BodyMeasurementRepository:
    """
    Repository for BodyMeasurement database operations.

    Responsibilities:
    - Execute SQL queries related to body measurements
    - Convert database row dicts to BodyMeasurementPublic models
    - Handle all body-measurement-related database logic
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
            QUERIES.body_measurements.create,
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
        row = fetch_one(QUERIES.body_measurements.get_by_id, (entry_id,))
        if row is None:
            return None
        return map_body_measurement(row)

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
            QUERIES.body_measurements.get_by_user_and_id,
            (user_id, entry_id),
        )
        if row is None:
            return None
        return map_body_measurement(row)

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
            QUERIES.body_measurements.get_by_user_and_date,
            (user_id, entry_date),
        )
        if row is None:
            return None
        return map_body_measurement(row)

    def get_latest_for_user(self, user_id: int) -> BodyMeasurementPublic | None:
        """
        Retrieve the most recent body measurement entry for a user.

        Args:
            user_id: Owner user ID.

        Returns:
            The latest entry if one exists, otherwise None.
        """
        row = fetch_one(
            QUERIES.body_measurements.get_latest_for_user,
            (user_id,),
        )
        if row is None:
            return None
        return map_body_measurement(row)

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

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.body_measurements.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.body_measurements.filter_date_to)
            params.append(date_to)

        sql = QUERIES.body_measurements.list_by_user.format(filters=" ".join(filters))
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [map_body_measurement(row) for row in rows]

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
            QUERIES.body_measurements.update_owned.format(set_clause=set_clause)
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
                QUERIES.body_measurements.delete_owned,
                (user_id, entry_id),
            )
            > 0
        )
