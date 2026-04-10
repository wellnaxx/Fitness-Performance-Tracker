"""
Workout Repository

This module handles all database interactions for the Workout entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate
from utils.errors import WorkoutRepositoryError, WorkoutRowError


class WorkoutRow(TypedDict):
    id: int
    user_id: int | None
    name: str
    description: str | None
    workout_date: date
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WorkoutRepository:
    """
    Repository for Workout database operations.

    Responsibilities:
    - Execute SQL queries related to workouts
    - Convert database row dicts to WorkoutPublic models
    - Handle all workout-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, user_id, name, description, workout_date,
               started_at, completed_at, notes, created_at, updated_at
        FROM workouts
    """

    _WORKOUT_UPDATE_WHITELIST: Final[set[str]] = {
        "name",
        "description",
        "workout_date",
        "started_at",
        "completed_at",
        "notes",
    }

    def create(self, user_id: int, workout_data: WorkoutCreate) -> WorkoutPublic:
        """
        Create a new workout for a specific user.

        Args:
            user_id: Owner user ID.
            workout_data: Workout creation payload.

        Returns:
            The newly created workout.

        Raises:
            WorkoutRepositoryError: If the inserted row cannot be retrieved afterwards.
        """
        sql = """
            INSERT INTO workouts
            (user_id, name, description, workout_date, started_at, completed_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        workout_id = execute_insert(
            sql,
            (
                user_id,
                workout_data.name,
                workout_data.description,
                workout_data.workout_date,
                workout_data.started_at,
                workout_data.completed_at,
                workout_data.notes,
            ),
        )

        workout = self.get_by_id(workout_id)
        if workout is None:
            raise WorkoutRepositoryError.inserted_workout_missing(workout_id)
        return workout

    def get_by_id(self, workout_id: int) -> WorkoutPublic | None:
        """
        Retrieve a workout by its database ID.

        Args:
            workout_id: Workout ID.

        Returns:
            The workout if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (workout_id,))
        if row is None:
            return None
        return self._row_to_workout(row)

    def get_by_user_and_id(self, user_id: int, workout_id: int) -> WorkoutPublic | None:
        """
        Retrieve a workout by ID only if it belongs to the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.

        Returns:
            The workout if found and owned by the user, otherwise None.
        """
        row = fetch_one(
            f"{self._BASE_SELECT} WHERE user_id = %s AND id = %s",
            (user_id, workout_id),
        )
        if row is None:
            return None
        return self._row_to_workout(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutPublic]:
        """
        List workouts for a user with pagination and date filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `workout_date`.
            date_to: Optional inclusive upper bound for `workout_date`.

        Returns:
            Workouts ordered from newest to oldest.
        """
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        sql = f"{self._BASE_SELECT} WHERE user_id = %s"
        params: list[object] = [user_id]

        if date_from is not None:
            sql += " AND workout_date >= %s"
            params.append(date_from)

        if date_to is not None:
            sql += " AND workout_date <= %s"
            params.append(date_to)

        sql += " ORDER BY workout_date DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_workout(row) for row in rows]

    def update_owned(
        self,
        user_id: int,
        workout_id: int,
        update_data: WorkoutUpdate,
    ) -> WorkoutPublic | None:
        """
        Partially update a workout owned by the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.
            update_data: Partial update payload.

        Returns:
            The updated workout if found, otherwise None.

        Raises:
            WorkoutRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, workout_id)

        unknown = set(fields) - self._WORKOUT_UPDATE_WHITELIST
        if unknown:
            raise WorkoutRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = f"UPDATE workouts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s"
        execute_write(sql, (*fields.values(), workout_id, user_id))
        return self.get_by_user_and_id(user_id, workout_id)

    def delete_owned(self, user_id: int, workout_id: int) -> bool:
        """
        Delete a workout owned by the user.

        Args:
            user_id: Owner user ID.
            workout_id: Workout ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                "DELETE FROM workouts WHERE id = %s AND user_id = %s",
                (workout_id, user_id),
            )
            > 0
        )

    def get_visible_by_id(self, workout_id: int, user_id: int) -> WorkoutPublic | None:
        """
        Retrieve a workout by ID if it is globally visible or owned by the user.

        Args:
            workout_id: Workout ID.
            user_id: Requesting user ID.

        Returns:
            The workout if visible to the user, otherwise None.
        """
        row = fetch_one(
            f"{self._BASE_SELECT} WHERE id = %s AND (user_id IS NULL OR user_id = %s)",
            (workout_id, user_id),
        )
        if row is None:
            return None
        return self._row_to_workout(row)

    def get_all_visible_for_user(
        self,
        user_id: int,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutPublic]:
        """
        List workouts for a user with optional search filtering.

        Args:
            user_id: Owner user ID.
            search: Optional case-insensitive name/description filter.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `workout_date`.
            date_to: Optional inclusive upper bound for `workout_date`.

        Returns:
            Workouts ordered from newest to oldest.
        """
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        sql = f"{self._BASE_SELECT} WHERE (user_id IS NULL OR user_id = %s)"
        params: list[object] = [user_id]

        if search is not None:
            sql += " AND (name ILIKE %s OR description ILIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern])

        if date_from is not None:
            sql += " AND workout_date >= %s"
            params.append(date_from)

        if date_to is not None:
            sql += " AND workout_date <= %s"
            params.append(date_to)

        sql += " ORDER BY workout_date DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_workout(row) for row in rows]

    def update(
        self,
        workout_id: int,
        user_id: int,
        update_data: WorkoutUpdate,
    ) -> WorkoutPublic | None:
        """Compatibility wrapper for `update_owned`."""
        return self.update_owned(user_id, workout_id, update_data)

    def delete(self, workout_id: int, user_id: int) -> bool:
        """Compatibility wrapper for `delete_owned`."""
        return self.delete_owned(user_id, workout_id)

    @staticmethod
    def _parse_workout_row(row: dict[str, object]) -> WorkoutRow:
        """Validate and normalize a raw database row into a typed WorkoutRow."""
        id_value = row.get("id")
        user_id = row.get("user_id")
        name = row.get("name")
        description = row.get("description")
        workout_date = row.get("workout_date")
        started_at = row.get("started_at")
        completed_at = row.get("completed_at")
        notes = row.get("notes")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        if not isinstance(id_value, int):
            raise WorkoutRowError.invalid_type("id", "int")
        if user_id is not None and not isinstance(user_id, int):
            raise WorkoutRowError.invalid_type("user_id", "int | None")
        if not isinstance(name, str):
            raise WorkoutRowError.invalid_type("name", "str")
        if description is not None and not isinstance(description, str):
            raise WorkoutRowError.invalid_type("description", "str | None")
        if not isinstance(workout_date, date):
            raise WorkoutRowError.invalid_type("workout_date", "date")
        if started_at is not None and not isinstance(started_at, datetime):
            raise WorkoutRowError.invalid_type("started_at", "datetime | None")
        if completed_at is not None and not isinstance(completed_at, datetime):
            raise WorkoutRowError.invalid_type("completed_at", "datetime | None")
        if notes is not None and not isinstance(notes, str):
            raise WorkoutRowError.invalid_type("notes", "str | None")
        if not isinstance(created_at, datetime):
            raise WorkoutRowError.invalid_type("created_at", "datetime")
        if not isinstance(updated_at, datetime):
            raise WorkoutRowError.invalid_type("updated_at", "datetime")

        return WorkoutRow(
            id=id_value,
            user_id=user_id,
            name=name,
            description=description,
            workout_date=workout_date,
            started_at=started_at,
            completed_at=completed_at,
            notes=notes,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _row_to_workout(cls, row: dict[str, object]) -> WorkoutPublic:
        """Convert a raw database row into a validated WorkoutPublic model."""
        workout_row = cls._parse_workout_row(row)
        return WorkoutPublic.model_validate(workout_row)
