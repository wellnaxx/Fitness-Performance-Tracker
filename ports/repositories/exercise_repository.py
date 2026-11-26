"""Repository contract for Exercise."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

if TYPE_CHECKING:
    from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate


class ExerciseRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_id: int, exercise_data: ExerciseCreate) -> ExercisePublic:
        """Create a new custom exercise in the database.

        Args:
            exercise_data (ExerciseCreate): The data for the new exercise.
            user_id (int): The ID of the user creating the exercise.

        Returns:
            ExercisePublic: The newly created exercise data.

        Raises:
            ExerciseRepositoryError: If the exercise could not be retrieved after creation.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_visible_by_id(self, user_id: int, exercise_id: int) -> ExercisePublic | None:
        """Retrieve an exercise by its ID if it is visible to the specified user.

        An exercise is considered visible if it is either a predefined exercise (created_by IS NULL)
        or a custom exercise created by the user.

        Args:
            exercise_id (int): The unique identifier of the exercise to retrieve.
            user_id (int): The ID of the user for visibility filtering.

        Returns:
            ExercisePublic: The exercise data if found and visible, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

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
        """List all exercises visible to the specified user.

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

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_owned(self, user_id: int, exercise_id: int, updates: ExerciseUpdate) -> ExercisePublic | None:
        """Update an existing exercise owned by the specified user.

        Args:
            user_id (int): The ID of the user who owns the exercise.
            exercise_id (int): The unique identifier of the exercise to update.
            updates (ExerciseUpdate): The fields to update.

        Returns:
            ExercisePublic: The updated exercise data if the update was successful, otherwise None.
        Raises:
            ExerciseRepositoryError: If invalid update fields are provided.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def delete_owned(self, user_id: int, exercise_id: int) -> bool:
        """Delete an existing exercise owned by the specified user.

        Args:
            user_id (int): The ID of the user who owns the exercise.
            exercise_id (int): The unique identifier of the exercise to delete.

        Returns:
            bool: True if the exercise was deleted, False if it was not found or not owned by the user.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...

    def name_exists_visible(self, user_id: int, name: str, exclude_exercise_id: int | None = None) -> bool:
        """Check if an exercise with the given name exists and is visible to the specified user.

        Args:
            name (str): The name of the exercise to check for existence.
            user_id (int): The ID of the user for visibility filtering.
            exclude_exercise_id (int | None): Optional exercise ID to exclude from the check.

        Returns:
            bool: True if an exercise with the given name exists and is visible, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...
