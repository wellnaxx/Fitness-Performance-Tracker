"""
Workout Repository

This module handles all database interactions for the Workout entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import WorkoutRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.workout import map_workout
from data.queries import QUERIES

if TYPE_CHECKING:
    from datetime import date

    from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate


class WorkoutRepository:
    """
    Repository for Workout database operations.

    Responsibilities:
    - Execute SQL queries related to workouts
    - Convert database row dicts to WorkoutPublic models
    - Handle all workout-related database logic
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
        sql = QUERIES.workouts.create
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
            raise WorkoutRepositoryError.inserted_missing(workout_id)
        return workout

    def get_by_id(self, workout_id: int) -> WorkoutPublic | None:
        """
        Retrieve a workout by its database ID.

        Args:
            workout_id: Workout ID.

        Returns:
            The workout if found, otherwise None.
        """
        row = fetch_one(QUERIES.workouts.get_by_id, (workout_id,))
        if row is None:
            return None
        return map_workout(row)

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
            QUERIES.workouts.get_by_user_and_id,
            (user_id, workout_id),
        )
        if row is None:
            return None
        return map_workout(row)

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

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.workouts.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.workouts.filter_date_to)
            params.append(date_to)

        sql = QUERIES.workouts.list_by_user.format(filters=" ".join(filters))
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [map_workout(row) for row in rows]

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
        sql = QUERIES.workouts.update_owned.format(set_clause=set_clause)
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
                QUERIES.workouts.delete_owned,
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
            QUERIES.workouts.get_visible_by_id,
            (workout_id, user_id),
        )
        if row is None:
            return None
        return map_workout(row)

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

        filters: list[str] = []
        params: list[object] = [user_id]

        if search is not None:
            filters.append(QUERIES.workouts.filter_search)
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            params.extend([pattern, pattern])

        if date_from is not None:
            filters.append(QUERIES.workouts.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.workouts.filter_date_to)
            params.append(date_to)

        sql = QUERIES.workouts.get_all_visible_for_user.format(filters=" ".join(filters))
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [map_workout(row) for row in rows]
