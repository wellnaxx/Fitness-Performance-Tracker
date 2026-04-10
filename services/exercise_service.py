from repositories.exercise_repository import ExerciseRepository
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate
from utils.errors import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseRepositoryError,
    ExerciseUpdateError,
)


class ExerciseService:
    """
    Business logic for exercise-related operations.

    Responsibilities:
    - Ensure users only access their own exercises
    - Coordinate repository operations
    """

    def __init__(self, exercise_repo: ExerciseRepository) -> None:
        self.exercise_repo = exercise_repo

    def create_exercise(
        self,
        exercise_data: ExerciseCreate,
        user_id: int,
    ) -> ExercisePublic:
        """
        Create a new exercise for the authenticated user.

        Business Rules:
        - Exercise names must be unique for the user.
        """
        if self.exercise_repo.name_exists_visible(exercise_data.name, user_id):
            raise ExerciseNameAlreadyExistsError.already_exists()

        try:
            return self.exercise_repo.create(exercise_data, user_id)
        except ExerciseRepositoryError as exc:
            raise ExerciseCreationError.create_failed() from exc

    def get_visible_by_user(self, exercise_id: int, user_id: int) -> ExercisePublic:
        """
        Retrieve an exercise visible to the user (their own exercises).
        """
        exercise = self.exercise_repo.get_visible_by_id(exercise_id, user_id)
        if exercise is None:
            raise ExerciseNotFoundError.not_found()
        return exercise

    def list_visible_by_user(
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
        List exercises visible to the user (their own exercises) with pagination.

        Business Rules:
        - Only exercises visible to the user are returned.
        - Optional filters can be applied for search, muscle group, equipment, etc.
        - Pagination is supported via limit and offset parameters.
        """
        return self.exercise_repo.list_visible(
            user_id, limit, offset, search, muscle_group, equipment, is_compound, is_custom
        )

    def update_exercise(
        self,
        user_id: int,
        exercise_id: int,
        update_data: ExerciseUpdate,
    ) -> ExercisePublic:
        """
        Update an existing exercise if it belongs to the user.

        Business Rules:
        - Only exercises owned by the user can be updated.
        - Exercise names must remain unique for the user.
        """

        if update_data.name and self.exercise_repo.name_exists_visible(
            update_data.name, user_id, exclude_exercise_id=exercise_id
        ):
            raise ExerciseUpdateError.duplicate_name()
        try:
            updated = self.exercise_repo.update_owned(user_id, exercise_id, update_data)
        except ExerciseRepositoryError as exc:
            raise ExerciseUpdateError.update_failed() from exc
        if updated is None:
            raise ExerciseNotFoundError.not_accessible()
        return updated

    def delete_exercise(self, user_id: int, exercise_id: int) -> None:
        """
        Delete an existing exercise if it belongs to the user.

        Business Rules:
        - Only exercises owned by the user can be deleted.
        """
        exercise = self.exercise_repo.get_visible_by_id(exercise_id, user_id)
        if exercise is None:
            raise ExerciseNotFoundError.not_accessible()
        if exercise.is_custom is False:
            raise ExerciseDeleteError.custom_only()

        deleted = self.exercise_repo.delete_owned(user_id, exercise_id)
        if not deleted:
            raise ExerciseDeleteError.not_accessible()
