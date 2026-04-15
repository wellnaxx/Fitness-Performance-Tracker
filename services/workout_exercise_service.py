"""
Workout Exercise Service - Business Logic Layer for Workout Exercise operations.

This module handles the business logic for workout exercise-related operations including:
- Adding exercises to workouts
- Retrieving exercises within a workout
- Updating exercises within a workout
- Removing exercises from workouts

Responsibilities:
- Ensure users only modify exercises within their own workouts
- Coordinate repository operations
"""

import logging

from core.errors.exercise import ExerciseNotFoundError
from core.errors.repository import WorkoutExerciseRepositoryError
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import (
    WorkoutExerciseCreationError,
    WorkoutExerciseDeleteError,
    WorkoutExerciseNotFoundError,
    WorkoutExerciseUpdateError,
    WorkoutExerciseValidationError,
)
from repositories.exercise_repository import ExerciseRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from repositories.workout_repository import WorkoutRepository
from schemas.workout_exercises_schema import (
    WorkoutExerciseCreate,
    WorkoutExercisePublic,
    WorkoutExerciseUpdate,
)
from schemas.workout_schema import WorkoutPublic


class WorkoutExerciseService:
    def __init__(
        self,
        workout_exercise_repository: WorkoutExerciseRepository,
        workout_repository: WorkoutRepository,
        exercise_repository: ExerciseRepository,
    ) -> None:
        """
        Initialize WorkoutExerciseService with repository dependencies.

        Args:
            workout_exercise_repository: WorkoutExerciseRepository instance for database operations
            workout_repository: WorkoutRepository instance for database operations
            exercise_repository: ExerciseRepository instance for database operations
        """
        self.workout_exercise_repository = workout_exercise_repository
        self.workout_repository = workout_repository
        self.exercise_repository = exercise_repository
        self.logger = logging.getLogger(__name__)

    def create_workout_exercise(
        self, user_id: int, workout_id: int, workout_exercise_data: WorkoutExerciseCreate
    ) -> WorkoutExercisePublic:
        """
        Add a new exercise to a workout.

        Args:
            user_id: ID of the user adding the exercise
            workout_id: ID of the workout to add the exercise to
            workout_exercise_data: WorkoutExerciseCreate schema with exercise details

        Returns:
            WorkoutExercisePublic schema of the created workout exercise

        Raises:
            WorkoutExerciseCreationError: If adding the exercise fails, or if the order index is invalid
            WorkoutNotFoundError: If the workout does not exist or is not accessible to the user
            ExerciseNotFoundError: If the exercise does not exist or is not accessible to the user
        """
        self._get_owned_workout(user_id, workout_id)
        self._validate_target_exercise(user_id, workout_exercise_data.exercise_id)

        existing_entries = self.workout_exercise_repository.list_by_workout(workout_id)
        current_count = len(existing_entries)
        self._validate_order_index(workout_exercise_data.order_index, current_count)

        try:
            workout_exercise = self.workout_exercise_repository.create(workout_id, workout_exercise_data)
        except WorkoutExerciseRepositoryError as exc:
            self.logger.exception(f"Failed to add exercise to workout for user {user_id}!")
            raise WorkoutExerciseCreationError.create_failed() from exc

        self.logger.info(
            f"Exercise added successfully to workout for user {user_id} with workout exercise ID {workout_exercise.id}"  # noqa: E501
        )
        return workout_exercise

    def get_workout_exercise(
        self, user_id: int, workout_id: int, workout_exercise_id: int
    ) -> WorkoutExercisePublic:
        """
        Retrieve a workout exercise by ID that is visible to the user.

        Args:
            workout_exercise_id: ID of the workout exercise to retrieve
            user_id: ID of the user requesting the workout exercise

        Returns:
            WorkoutExercisePublic schema of the retrieved workout exercise

        Raises:
            WorkoutExerciseNotFoundError: If the workout exercise is not found, not in the specified workout,
            or not visible to the user
            WorkoutNotFoundError: If the workout does not exist or is not accessible to the user
        """
        self._get_owned_workout(user_id, workout_id)
        workout_exercise = self._get_workout_exercise_or_raise(workout_id, workout_exercise_id)

        self.logger.info(
            f"Workout exercise with ID {workout_exercise_id} retrieved successfully for user {user_id}."
        )
        return workout_exercise

    def list_workout_exercises(self, user_id: int, workout_id: int) -> list[WorkoutExercisePublic]:
        """
        List all exercises in a workout that are visible to the user.

        Args:
            workout_id: ID of the workout to list exercises from
            user_id: ID of the user requesting the workout exercises

        Returns:
            List of WorkoutExercisePublic schemas of the exercises in the workout

        Raises:
            WorkoutNotFoundError: If the workout does not exist or is not accessible to the user
        """
        self._get_owned_workout(user_id, workout_id)

        workout_exercises = self.workout_exercise_repository.list_by_workout(workout_id)
        self.logger.info(
            f"Listed {len(workout_exercises)} exercises for workout {workout_id} and user {user_id}."
        )
        return workout_exercises

    def update_workout_exercise(
        self,
        user_id: int,
        workout_id: int,
        workout_exercise_id: int,
        workout_exercise_data: WorkoutExerciseUpdate,
    ) -> WorkoutExercisePublic:
        """
        Update a workout exercise's details.

        Args:
            workout_exercise_id: ID of the workout exercise to update
            workout_exercise_data: WorkoutExerciseUpdate schema with updated details
            user_id: ID of the user requesting the update

        Returns:
            WorkoutExercisePublic schema of the updated workout exercise

        Raises:
            WorkoutExerciseNotFoundError: If the workout exercise is not found, not in the specified workout,
            or not visible to the user
            WorkoutNotFoundError: If the workout does not exist or is not accessible to the user
            ExerciseNotFoundError: If the new exercise does not exist or is not accessible to the user
            WorkoutExerciseUpdateError: If updating the workout exercise fails
        """
        self._get_owned_workout(user_id, workout_id)

        self._get_workout_exercise_or_raise(workout_id, workout_exercise_id)

        if workout_exercise_data.exercise_id is not None:
            self._validate_target_exercise(user_id, workout_exercise_data.exercise_id)

        existing_entries = self.workout_exercise_repository.list_by_workout(workout_id)
        if workout_exercise_data.order_index is not None:
            current_count = len(existing_entries)
            self._validate_update_order_index(workout_exercise_data.order_index, current_count)

        try:
            updated = self.workout_exercise_repository.update(
                workout_id, workout_exercise_id, workout_exercise_data
            )
        except WorkoutExerciseRepositoryError as exc:
            self.logger.exception(
                f"Failed to update workout exercise with ID {workout_exercise_id} for user {user_id}."
            )
            raise WorkoutExerciseUpdateError.update_failed(workout_exercise_id=workout_exercise_id) from exc

        if updated is None:
            self.logger.warning(
                f"Workout exercise with ID {workout_exercise_id} not found after update attempt for user {user_id}."  # noqa: E501
            )
            raise WorkoutExerciseNotFoundError.not_accessible(workout_exercise_id=workout_exercise_id)

        self.logger.info(
            f"Workout exercise with ID {workout_exercise_id} updated successfully for user {user_id}."
        )
        return updated

    def delete_workout_exercise(self, user_id: int, workout_id: int, workout_exercise_id: int) -> None:
        """
        Remove an exercise from a workout.

        Args:
            user_id: ID of the user requesting the deletion
            workout_id: ID of the workout to remove the exercise from
            workout_exercise_id: ID of the workout exercise to delete

        Raises:
            WorkoutExerciseNotFoundError: If the workout exercise is not found, not in the specified
            workout, or not visible to the user
            WorkoutNotFoundError: If the workout does not exist or is not accessible to the user
            WorkoutExerciseDeleteError: If deleting the workout exercise fails
        """
        self._get_owned_workout(user_id, workout_id)
        self._get_workout_exercise_or_raise(workout_id, workout_exercise_id)

        try:
            deleted = self.workout_exercise_repository.delete(workout_id, workout_exercise_id)
        except WorkoutExerciseRepositoryError as exc:
            self.logger.exception(
                f"Failed to delete workout exercise with ID {workout_exercise_id} for user {user_id}."
            )
            raise WorkoutExerciseDeleteError.delete_failed(workout_exercise_id=workout_exercise_id) from exc

        if not deleted:
            self.logger.warning(
                f"Workout exercise with ID {workout_exercise_id} not found after delete attempt for user {user_id}."  # noqa: E501
            )
            raise WorkoutExerciseNotFoundError.not_accessible(workout_exercise_id=workout_exercise_id)

        self.logger.info(
            f"Workout exercise with ID {workout_exercise_id} deleted successfully for user {user_id}."
        )

    def _get_owned_workout(self, user_id: int, workout_id: int) -> WorkoutPublic:
        workout = self.workout_repository.get_by_user_and_id(user_id, workout_id)
        if workout is None:
            self.logger.warning(f"Workout with ID {workout_id} not found or not visible to user {user_id}.")
            raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)
        return workout


    def _get_workout_exercise_or_raise(
        self,
        workout_id: int,
        workout_exercise_id: int,
    ) -> WorkoutExercisePublic:
        workout_exercise = self.workout_exercise_repository.get_by_workout_and_id(
            workout_id,
            workout_exercise_id,
        )
        if workout_exercise is None:
            self.logger.warning(
                f"Workout exercise with ID {workout_exercise_id} not found in workout {workout_id}."
            )
            raise WorkoutExerciseNotFoundError.not_in_workout(
                workout_exercise_id=workout_exercise_id,
                workout_id=workout_id,
            )
        return workout_exercise

    def _validate_target_exercise(self, user_id: int, exercise_id: int) -> None:
        if not self.exercise_repository.get_visible_by_id(exercise_id, user_id):
            self.logger.warning(f"Exercise with ID {exercise_id} not found or not visible to user {user_id}.")
            raise ExerciseNotFoundError.not_accessible(exercise_id=exercise_id)

    def _validate_order_index(self, order_index: int, current_count: int) -> None:
        if order_index < 0 or order_index > current_count:
            self.logger.warning(f"Invalid order index {order_index} for workout.")
            raise WorkoutExerciseValidationError.invalid_create_order_index(order_index=order_index)

    def _validate_update_order_index(self, order_index: int, current_count: int) -> None:
        max_index = current_count - 1
        if order_index < 0 or order_index > max_index:
            self.logger.warning(f"Invalid order index {order_index} for workout update.")
            raise WorkoutExerciseValidationError.invalid_update_order_index(order_index=order_index)
