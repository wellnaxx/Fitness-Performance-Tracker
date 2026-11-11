import logging

from core.errors.exercise import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
)
from core.errors.repository import ExerciseRepositoryError
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from schemas.exercise_schema import ExerciseCreate, ExercisePublic, ExerciseUpdate
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

logger = logging.getLogger(__name__)


class ExerciseService:
    """
    Business logic for exercise-related operations.

    Responsibilities:
    - Ensure users only access their own exercises
    - Coordinate repository operations
    """

    def __init__(self, exercise_repo: ExerciseRepositoryPort) -> None:
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
            logger.warning("Exercise creation rejected: duplicate name | user_id=%s", user_id)
            raise ExerciseNameAlreadyExistsError.already_exists(exercise_name=exercise_data.name)

        try:
            exercise = self.exercise_repo.create(exercise_data, user_id)
        except ExerciseRepositoryError as exc:
            logger.exception("Exercise creation failed | user_id=%s", user_id)
            raise ExerciseCreationError.create_failed() from exc
        logger.info("Exercise created | user_id=%s exercise_id=%s", user_id, exercise.id)
        return exercise

    def get_visible_by_user(self, exercise_id: int, user_id: int) -> ExercisePublic:
        """
        Retrieve an exercise visible to the user (their own exercises).
        """
        exercise = self.exercise_repo.get_visible_by_id(exercise_id, user_id)
        if exercise is None:
            logger.warning(
                "Exercise not found or inaccessible | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseNotFoundError.not_found(exercise_id=exercise_id)
        logger.debug("Exercise retrieved | user_id=%s exercise_id=%s", user_id, exercise_id)
        return exercise

    def list_visible_by_user(
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
        List exercises visible to the user (their own exercises) with pagination.

        Business Rules:
        - Only exercises visible to the user are returned.
        - Optional filters can be applied for search, muscle group, equipment, etc.
        - Pagination is supported via limit and offset parameters.
        """
        exercises = self.exercise_repo.list_visible(
            user_id, limit, offset, search, muscle_group, equipment, is_compound, is_custom
        )
        logger.debug(
            "Exercises listed | user_id=%s count=%s limit=%s offset=%s", user_id, len(exercises), limit, offset
        )
        return exercises

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
            logger.warning(
                "Exercise update rejected: duplicate name | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseUpdateError.duplicate_name(exercise_name=update_data.name)
        try:
            updated = self.exercise_repo.update_owned(user_id, exercise_id, update_data)
        except ExerciseRepositoryError as exc:
            logger.exception("Exercise update failed | user_id=%s exercise_id=%s", user_id, exercise_id)
            raise ExerciseUpdateError.update_failed() from exc
        if updated is None:
            logger.warning("Exercise not found during update | user_id=%s exercise_id=%s", user_id, exercise_id)
            raise ExerciseNotFoundError.not_accessible(exercise_id=exercise_id)
        logger.info("Exercise updated | user_id=%s exercise_id=%s", user_id, exercise_id)
        return updated

    def delete_exercise(self, user_id: int, exercise_id: int) -> None:
        """
        Delete an existing exercise if it belongs to the user.

        Business Rules:
        - Only exercises owned by the user can be deleted.
        """
        exercise = self.exercise_repo.get_visible_by_id(exercise_id, user_id)
        if exercise is None:
            logger.warning(
                "Exercise not found during deletion | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseNotFoundError.not_accessible(exercise_id=exercise_id)
        if exercise.is_custom is False:
            logger.warning(
                "Exercise deletion rejected: predefined exercise | user_id=%s exercise_id=%s",
                user_id,
                exercise_id,
            )
            raise ExerciseDeleteError.custom_only()

        deleted = self.exercise_repo.delete_owned(user_id, exercise_id)
        if not deleted:
            logger.warning(
                "Exercise deletion affected no row | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseDeleteError.not_accessible(exercise_id=exercise_id)
        logger.info("Exercise deleted | user_id=%s exercise_id=%s", user_id, exercise_id)
