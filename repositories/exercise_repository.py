"""
Exercise Repository

This module handles all database interactions for the Exercise entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import ExerciseRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.exercise import map_exercise
from data.queries import QUERIES
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET, normalize_pagination

if TYPE_CHECKING:
    from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate


class ExerciseRepository:
    """
    Repository for Exercise database operations.

    Responsibilities:
    - Execute SQL queries related to exercises
    - Convert database row dicts to ExercisePublic models
    - Handle all exercise-related database logic
    """

    _EXERCISE_UPDATE_WHITELIST: Final[set[str]] = {
        "name",
        "description",
        "muscle_group",
        "equipment",
        "is_compound",
    }

    def create(self, exercise_data: ExerciseCreate, user_id: int) -> ExercisePublic:
        """
        Create a new custom exercise in the database.

        Args:
            exercise_data (ExerciseCreate): The data for the new exercise.
            user_id (int): The ID of the user creating the exercise.

        Returns:
            ExercisePublic: The newly created exercise data.

        Raises:
            ExerciseRepositoryError: If the exercise could not be retrieved after creation.
        """
        sql = QUERIES.exercises.create
        exercise_id = execute_insert(
            sql,
            (
                exercise_data.name,
                exercise_data.description,
                exercise_data.muscle_group,
                exercise_data.equipment,
                exercise_data.is_compound,
                user_id,
                True,  # is_custom is always True for user-created exercises
            ),
        )

        exercise = self.get_by_id(exercise_id)
        if exercise is None:
            raise ExerciseRepositoryError.inserted_missing(exercise_id)
        return exercise

    def get_by_id(self, exercise_id: int) -> ExercisePublic | None:
        """
        Retrieve an exercise by its ID.

        Args:
            exercise_id (int): The unique identifier of the exercise to retrieve.

        Returns:
            ExercisePublic: The exercise data if found, otherwise None.
        """
        sql = QUERIES.exercises.get_by_id
        row = fetch_one(sql, (exercise_id,))
        if row is None:
            return None
        return map_exercise(row)

    def get_visible_by_id(self, exercise_id: int, user_id: int) -> ExercisePublic | None:
        """
        Retrieve an exercise by its ID if it is visible to the specified user.

        An exercise is considered visible if it is either a predefined exercise (created_by IS NULL)
        or a custom exercise created by the user.

        Args:
            exercise_id (int): The unique identifier of the exercise to retrieve.
            user_id (int): The ID of the user for visibility filtering.

        Returns:
            ExercisePublic: The exercise data if found and visible, otherwise None.
        """
        exercise = self.get_by_id(exercise_id)
        if exercise is None:
            return None
        if exercise.created_by is not None and exercise.created_by != user_id:
            return None
        return exercise

    def list_visible(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        search: str | None = None,
        muscle_group: str | None = None,
        equipment: str | None = None,
        is_compound: bool | None = None,
        is_custom: bool | None = None,
    ) -> list[ExercisePublic]:
        """
        List all exercises visible to the specified user.

        An exercise is considered visible if it is either a predefined exercise (created_by IS NULL)
        or a custom exercise created by the user.

        Args:
            user_id (int): The ID of the user for visibility filtering.
            limit (int): The maximum number of exercises to return.
            offset (int): The number of exercises to skip before starting to return results.
            search (str | None): A search term to filter exercises by name or description.
            muscle_group (str | None): A muscle group to filter exercises by.
            equipment (str | None): An equipment type to filter exercises by.
            is_compound (bool | None): A flag to filter compound exercises.
            is_custom (bool | None): A flag to filter custom exercises.

        Returns:
            list[ExercisePublic]: A list of visible exercises.
        """
        pagination = normalize_pagination(limit, offset)
        filters: list[str] = []
        params: list[object] = [user_id]

        if search is not None:
            filters.append(QUERIES.exercises.filter_search)
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_pattern = f"%{escaped}%"
            params.extend([search_pattern, search_pattern])
        if muscle_group is not None:
            filters.append(QUERIES.exercises.filter_muscle_group)
            params.append(muscle_group)
        if equipment is not None:
            filters.append(QUERIES.exercises.filter_equipment)
            params.append(equipment)
        if is_compound is not None:
            filters.append(QUERIES.exercises.filter_is_compound)
            params.append(is_compound)
        if is_custom is not None:
            filters.append(QUERIES.exercises.filter_is_custom)
            params.append(is_custom)

        sql = QUERIES.exercises.list_visible.format(filters=" ".join(filters))
        params.extend([pagination.limit, pagination.offset])

        rows = fetch_all(sql, tuple(params))
        return [map_exercise(row) for row in rows]

    def update_owned(self, user_id: int, exercise_id: int, updates: ExerciseUpdate) -> ExercisePublic | None:
        """
        Update an existing exercise owned by the specified user.

        Args:
            user_id (int): The ID of the user who owns the exercise.
            exercise_id (int): The unique identifier of the exercise to update.
            updates (ExerciseUpdate): The fields to update.

        Returns:
            ExercisePublic: The updated exercise data if the update was successful, otherwise None.
        Raises:
            ExerciseRepositoryError: If invalid update fields are provided.
        """

        fields = updates.model_dump(exclude_none=True)
        if not fields:
            return self.get_visible_by_id(exercise_id, user_id)

        unknown = set(fields) - self._EXERCISE_UPDATE_WHITELIST
        if unknown:
            raise ExerciseRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.exercises.update_owned.format(set_clause=set_clause)
        params: list[object] = [*fields.values(), exercise_id, user_id]

        rows_affected = execute_write(sql, tuple(params))
        if rows_affected == 0:
            return None

        return self.get_visible_by_id(exercise_id, user_id)

    def delete_owned(self, user_id: int, exercise_id: int) -> bool:
        """
        Delete an existing exercise owned by the specified user.

        Args:
            user_id (int): The ID of the user who owns the exercise.
            exercise_id (int): The unique identifier of the exercise to delete.

        Returns:
            bool: True if the exercise was deleted, False if it was not found or not owned by the user.
        """
        sql = QUERIES.exercises.delete_owned
        rows_affected = execute_write(sql, (exercise_id, user_id))
        return rows_affected > 0

    def name_exists_visible(
        self,
        name: str,
        user_id: int,
        exclude_exercise_id: int | None = None,
    ) -> bool:
        """
        Check if an exercise with the given name exists and is visible to the specified user.

        Args:
            name (str): The name of the exercise to check for existence.
            user_id (int): The ID of the user for visibility filtering.
            exclude_exercise_id (int | None): Optional exercise ID to exclude from the check.

        Returns:
            bool: True if an exercise with the given name exists and is visible, otherwise False.
        """
        filters: list[str] = []
        params: list[object] = [name, user_id]

        if exclude_exercise_id is not None:
            filters.append(QUERIES.exercises.filter_exclude_exercise_id)
            params.append(exclude_exercise_id)

        sql = QUERIES.exercises.name_exists_visible.format(filters=" ".join(filters))
        return fetch_one(sql, tuple(params)) is not None
