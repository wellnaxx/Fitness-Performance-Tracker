import logging

from core.errors.exercise import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
    ExerciseValidationError,
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
        """Initialize the operation's persistence dependencies.

        Args:
            exercise_repo: Repository contract for exercise persistence and visibility checks.
        """
        self.exercise_repo = exercise_repo

    def create(
        self,
        user_id: int,
        exercise_data: ExerciseCreate,
    ) -> ExercisePublic:
        """Create a custom exercise after checking names visible to the user.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            exercise_data: Validated exercise creation values.

        Returns:
            The persisted exercise with its assigned ID and timestamps.

        Raises:
            ExerciseNameAlreadyExistsError: If the name is already visible to the user.
            ExerciseCreationError: If the repository reports a creation failure.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        if self.exercise_repo.name_exists_visible(user_id, exercise_data.name):
            logger.warning("Exercise creation rejected: duplicate name | user_id=%s", user_id)
            raise ExerciseNameAlreadyExistsError.already_exists(exercise_name=exercise_data.name)

        try:
            exercise = self.exercise_repo.create(user_id, exercise_data)
        except ExerciseRepositoryError as exc:
            logger.exception("Exercise creation failed | user_id=%s", user_id)
            raise ExerciseCreationError.create_failed() from exc
        logger.info("Exercise created | user_id=%s exercise_id=%s", user_id, exercise.id)
        return exercise

    def get_by_id(self, user_id: int, exercise_id: int) -> ExercisePublic:
        """Retrieve a predefined exercise or a custom exercise owned by the user.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            exercise_id: Requested exercise ID.

        Returns:
            The exercise visible to the authenticated user.

        Raises:
            ExerciseNotFoundError: If the exercise is missing or not visible to the user.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        exercise = self.exercise_repo.get_visible_by_id(user_id, exercise_id)
        if exercise is None:
            logger.warning(
                "Exercise not found or inaccessible | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseNotFoundError.not_found(exercise_id=exercise_id)
        logger.debug("Exercise retrieved | user_id=%s exercise_id=%s", user_id, exercise_id)
        return exercise

    def list_by_user(
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
        """List predefined and owned exercises with pagination and optional filters.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            limit: Maximum records to return, using the shared pagination default and bounds.
            offset: Records to skip, using the shared pagination default and bounds.
            search: Optional text search applied to visible records.
            muscle_group: Optional muscle-group filter.
            equipment: Optional equipment filter.
            is_compound: Optional compound-exercise filter; False remains an active filter.
            is_custom: Optional custom-exercise filter; False remains an active filter.

        Returns:
            Matching visible exercises, or an empty list when none match.

        Raises:
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        exercises = self.exercise_repo.list_visible(
            user_id, limit, offset, search, muscle_group, equipment, is_compound, is_custom
        )
        logger.debug(
            "Exercises listed | user_id=%s count=%s limit=%s offset=%s", user_id, len(exercises), limit, offset
        )
        return exercises

    def update(
        self,
        user_id: int,
        exercise_id: int,
        update_data: ExerciseUpdate,
    ) -> ExercisePublic:
        """Verify ownership before validating a rename and updating the exercise.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            exercise_id: Requested exercise ID.
            update_data: Validated partial changes; omitted and None-valued fields preserve stored values.

        Returns:
            The updated exercise, or current values for an empty update.

        Raises:
            ExerciseNotFoundError: If the exercise is missing, unowned, predefined,
                or disappears during the write.
            ExerciseNameAlreadyExistsError: If another visible exercise uses the requested name.
            ExerciseUpdateError: If the repository reports an update failure.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """

        existing = self.exercise_repo.get_visible_by_id(user_id, exercise_id)
        if existing is None or existing.created_by != user_id:
            logger.warning("Exercise not owned during update | user_id=%s exercise_id=%s", user_id, exercise_id)
            raise ExerciseNotFoundError.not_accessible(exercise_id)

        if update_data.name and self.exercise_repo.name_exists_visible(
            user_id, update_data.name, exclude_exercise_id=exercise_id
        ):
            logger.warning(
                "Exercise update rejected: duplicate name | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseNameAlreadyExistsError.already_exists(exercise_name=update_data.name)
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

    def delete(self, user_id: int, exercise_id: int) -> None:
        """Delete an owned custom exercise after checking visibility and business rules.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            exercise_id: Requested exercise ID.

        Returns:
            None after successful deletion.

        Raises:
            ExerciseNotFoundError: If the exercise is inaccessible or disappears before deletion.
            ExerciseValidationError: If deletion of a predefined exercise is requested.
            ExerciseDeleteError: If the repository reports a deletion failure.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        exercise = self.exercise_repo.get_visible_by_id(user_id, exercise_id)
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
            raise ExerciseValidationError.custom_only()

        try:
            deleted = self.exercise_repo.delete_owned(user_id, exercise_id)
        except ExerciseRepositoryError as exc:
            logger.exception("Exercise deletion failed | user_id=%s exercise_id=%s", user_id, exercise_id)
            raise ExerciseDeleteError.delete_failed(exercise_id) from exc
        if not deleted:
            logger.warning(
                "Exercise deletion affected no row | user_id=%s exercise_id=%s", user_id, exercise_id
            )
            raise ExerciseNotFoundError.not_accessible(exercise_id=exercise_id)
        logger.info("Exercise deleted | user_id=%s exercise_id=%s", user_id, exercise_id)
