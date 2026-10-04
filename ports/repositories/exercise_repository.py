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

    def create(self, exercise_data: ExerciseCreate, user_id: int) -> ExercisePublic:
        """Create a new custom exercise in the database."""
        ...

    def get_visible_by_id(self, exercise_id: int, user_id: int) -> ExercisePublic | None:
        """Retrieve an exercise by its ID if it is visible to the specified user."""
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
        """List all exercises visible to the specified user."""
        ...

    def update_owned(self, user_id: int, exercise_id: int, updates: ExerciseUpdate) -> ExercisePublic | None:
        """Update an existing exercise owned by the specified user."""
        ...

    def delete_owned(self, user_id: int, exercise_id: int) -> bool:
        """Delete an existing exercise owned by the specified user."""
        ...

    def name_exists_visible(self, name: str, user_id: int, exclude_exercise_id: int | None = None) -> bool:
        """Check if an exercise with the given name exists and is visible to the specified user."""
        ...
