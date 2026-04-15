"""
Workout Service - Business Logic Layer for Workout operations.

This module handles the business logic for workout-related operations including:
- Creating workouts
- Retrieving workouts
- Updating workouts
- Deleting workouts

Responsibilities:
- Ensure users only access their own workouts
- Coordinate repository operations
"""

import logging
from datetime import date

from core.errors.repository import WorkoutRepositoryError
from core.errors.workout import (
    WorkoutCreationError,
    WorkoutDeleteError,
    WorkoutNotFoundError,
    WorkoutUpdateError,
)
from repositories.workout_repository import WorkoutRepository
from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate


class WorkoutService:
    def __init__(self, workout_repository: WorkoutRepository) -> None:
        """
        Initialize WorkoutService with repository dependency.

        Args:
            workout_repository: WorkoutRepository instance for database operations
        """
        self.workout_repository = workout_repository
        self.logger = logging.getLogger(__name__)

    def create_workout(self, user_id: int, workout_data: WorkoutCreate) -> WorkoutPublic:
        """
        Create a new workout for the user.

        Args:
            user_id: ID of the user creating the workout
            workout_data: WorkoutCreate schema with workout details

        Returns:
            WorkoutPublic schema of the created workout

        Raises:
            WorkoutCreationError: If workout creation fails
        """
        try:
            workout = self.workout_repository.create(user_id, workout_data)
        except WorkoutRepositoryError as exc:
            self.logger.exception(f"Failed to create workout for user {user_id}!")
            raise WorkoutCreationError.create_failed() from exc

        self.logger.info(f"Workout created successfully for user {user_id} with workout ID {workout.id}")
        return workout

    def get_visible_by_user(self, workout_id: int, user_id: int) -> WorkoutPublic:
        """
        Retrieve a workout by ID that is visible to the user.

        Args:
            workout_id: ID of the workout to retrieve
            user_id: ID of the user requesting the workout

        Returns:
            WorkoutPublic schema of the retrieved workout

        Raises:
            WorkoutNotFoundError: If the workout is not found or not visible to the user
        """

        workout = self.workout_repository.get_visible_by_id(workout_id, user_id)
        if workout is None:
            self.logger.warning(f"Workout with ID {workout_id} not found or not visible to user {user_id}.")
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        self.logger.info(f"Workout with ID {workout_id} retrieved successfully for user {user_id}.")
        return workout

    def list_visible_by_user(
        self,
        user_id: int,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorkoutPublic]:
        """
        List workouts visible to the user with pagination.

        Args:
            user_id: ID of the user requesting the workouts
            search: Optional search term to filter workouts by name or description
            limit: Maximum number of workouts to return (default 100)
            offset: Number of workouts to skip for pagination (default 0)
            date_from: Optional start date to filter workouts
            date_to: Optional end date to filter workouts

        Returns:
            List of WorkoutPublic schemas for the visible workouts
        """
        workouts = self.workout_repository.get_all_visible_for_user(
            user_id, search, limit, offset, date_from, date_to
        )
        self.logger.info(
            f"Listed {len(workouts)} workouts for user {user_id} with limit {limit} and offset {offset}."
        )
        return workouts

    def update_workout(self, workout_id: int, user_id: int, workout_data: WorkoutUpdate) -> WorkoutPublic:
        """
        Update a workout by ID if it belongs to the user.

        Args:
            workout_id: ID of the workout to update
            user_id: ID of the user requesting the update
            workout_data: WorkoutUpdate schema with updated workout details

        Returns:
            WorkoutPublic schema of the updated workout

        Raises:
            WorkoutNotFoundError: If the workout is not found or not visible to the user
            WorkoutUpdateError: If the update operation fails
        """

        existing_workout = self.workout_repository.get_by_user_and_id(user_id, workout_id)
        if existing_workout is None:
            self.logger.warning(
                f"Workout with ID {workout_id} not found or not visible to user {user_id} for update."
            )
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        try:
            updated_workout = self.workout_repository.update_owned(user_id, workout_id, workout_data)
        except WorkoutRepositoryError as exc:
            self.logger.exception(f"Failed to update workout with ID {workout_id} for user {user_id}.")
            raise WorkoutUpdateError.update_failed(workout_id=workout_id) from exc

        if updated_workout is None:
            self.logger.warning(
                f"Workout with ID {workout_id} not found after update attempt for user {user_id}."
            )
            raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)

        self.logger.info(f"Workout with ID {workout_id} updated successfully for user {user_id}.")

        return updated_workout

    def delete_workout(self, workout_id: int, user_id: int) -> None:
        """
        Delete a workout by ID if it belongs to the user.

        Args:
            workout_id: ID of the workout to delete
            user_id: ID of the user requesting the deletion

        Raises:
            WorkoutNotFoundError: If the workout is not found or not visible to the user
            WorkoutDeleteError: If the delete operation fails
        """
        existing_workout = self.workout_repository.get_by_user_and_id(user_id, workout_id)
        if existing_workout is None:
            self.logger.warning(
                f"Workout with ID {workout_id} not found or not visible to user {user_id} for deletion."
            )
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        try:
            deleted = self.workout_repository.delete_owned(user_id, workout_id)
        except WorkoutRepositoryError as exc:
            self.logger.exception(f"Failed to delete workout with ID {workout_id} for user {user_id}.")
            raise WorkoutDeleteError.delete_failed(workout_id=workout_id) from exc

        if not deleted:
            self.logger.warning(
                f"Workout with ID {workout_id} not found after delete attempt for user {user_id}."
            )
            raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)

        self.logger.info(f"Workout with ID {workout_id} deleted successfully for user {user_id}.")
