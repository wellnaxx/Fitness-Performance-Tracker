"""
Exercise Repository

This module handles all database interactions for the Exercise entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, TypedDict

from core.errors.repository import ExerciseRepositoryError, ExerciseRowError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate


class ExerciseRow(TypedDict):
    id: int
    name: str
    description: str | None
    muscle_group: str
    equipment: str | None
    is_compound: bool
    created_by: int | None
    is_custom: bool
    created_at: datetime
    updated_at: datetime


class ExerciseRepository:
    """
    Repository for Exercise database operations.

    Responsibilities:
    - Execute SQL queries related to exercises
    - Convert database row dicts to ExercisePublic models
    - Handle all exercise-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, name, description, muscle_group, equipment, is_compound,
               created_by, is_custom, created_at, updated_at
        FROM exercises
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
        sql = """
            INSERT INTO exercises
            (name, description, muscle_group, equipment, is_compound, created_by, is_custom)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
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
        sql = self._BASE_SELECT + " WHERE id = %s"
        row = fetch_one(sql, (exercise_id,))
        if row is None:
            return None
        return self._row_to_exercise(row)

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
        limit: int = 100,
        offset: int = 0,
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
        safe_limit = max(1, min(limit, 1000))  # Enforce reasonable limits to prevent abuse
        safe_offset = max(0, offset)
        sql = (
            self._BASE_SELECT
            + """
            WHERE (created_by IS NULL OR created_by = %s)
        """
        )
        params: list[object] = [user_id]

        if search is not None:
            sql += " AND (name ILIKE %s OR description ILIKE %s)"
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_pattern = f"%{escaped}%"
            params.extend([search_pattern, search_pattern])
        if muscle_group is not None:
            sql += " AND muscle_group = %s"
            params.append(muscle_group)
        if equipment is not None:
            sql += " AND equipment = %s"
            params.append(equipment)
        if is_compound is not None:
            sql += " AND is_compound = %s"
            params.append(is_compound)
        if is_custom is not None:
            sql += " AND is_custom = %s"
            params.append(is_custom)

        sql += " ORDER BY is_custom ASC, name ASC LIMIT %s OFFSET %s"
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_exercise(row) for row in rows]

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
        sql = f"""
            UPDATE exercises
            SET {set_clause}, updated_at = NOW()
            WHERE id = %s AND created_by = %s
        """
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
        sql = "DELETE FROM exercises WHERE id = %s AND created_by = %s"
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
        sql = """
            SELECT 1 FROM exercises
            WHERE name = %s AND (created_by IS NULL OR created_by = %s)
        """
        params: list[object] = [name, user_id]

        if exclude_exercise_id is not None:
            sql += " AND id <> %s"
            params.append(exclude_exercise_id)

        sql += " LIMIT 1"
        return fetch_one(sql, tuple(params)) is not None

    @staticmethod
    def _parse_exercise_row(row: dict[str, object]) -> ExerciseRow:
        """Validate and normalize a raw database row into a typed ExerciseRow."""
        id_value = row["id"]
        name = row["name"]
        description = row["description"]
        muscle_group = row["muscle_group"]
        equipment = row["equipment"]
        is_compound = row["is_compound"]
        created_by = row["created_by"]
        is_custom = row["is_custom"]
        created_at = row["created_at"]
        updated_at = row["updated_at"]

        if not isinstance(id_value, int):
            raise ExerciseRowError.invalid_type("id", "int")
        if not isinstance(name, str):
            raise ExerciseRowError.invalid_type("name", "str")
        if description is not None and not isinstance(description, str):
            raise ExerciseRowError.invalid_type("description", "str | None")
        if not isinstance(muscle_group, str):
            raise ExerciseRowError.invalid_type("muscle_group", "str")
        if equipment is not None and not isinstance(equipment, str):
            raise ExerciseRowError.invalid_type("equipment", "str | None")
        if not isinstance(is_compound, bool):
            raise ExerciseRowError.invalid_type("is_compound", "bool")
        if created_by is not None and not isinstance(created_by, int):
            raise ExerciseRowError.invalid_type("created_by", "int | None")
        if not isinstance(is_custom, bool):
            raise ExerciseRowError.invalid_type("is_custom", "bool")
        if not isinstance(created_at, datetime):
            raise ExerciseRowError.invalid_type("created_at", "datetime")
        if not isinstance(updated_at, datetime):
            raise ExerciseRowError.invalid_type("updated_at", "datetime")
        return ExerciseRow(
            id=id_value,
            name=name,
            description=description,
            muscle_group=muscle_group,
            equipment=equipment,
            is_compound=is_compound,
            created_by=created_by,
            is_custom=is_custom,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _row_to_exercise(cls, row: dict[str, object]) -> ExercisePublic:
        """Convert a raw database row into a validated ExercisePublic model."""
        exercise_row = cls._parse_exercise_row(row)
        return ExercisePublic.model_validate(exercise_row)
