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
from ports.repositories.workout_repository import WorkoutRepositoryPort
from schemas.workout_schema import WorkoutCreate, WorkoutPublic, WorkoutUpdate
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET


class WorkoutService:
    def __init__(self, workout_repository: WorkoutRepositoryPort) -> None:
        """
        Initialize WorkoutService with repository dependency.

        Args:
            workout_repository: WorkoutRepositoryPort instance for database operations
        """
        self.workout_repository = workout_repository
        self.logger = logging.getLogger(__name__)

    def create(self, user_id: int, workout_data: WorkoutCreate) -> WorkoutPublic:
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
            self.logger.exception("Failed to create workout for user %s!", user_id)
            raise WorkoutCreationError.create_failed() from exc

        self.logger.info("Workout created successfully for user %s with workout ID %s", user_id, workout.id)
        return workout

    def get_by_id(self, user_id: int, workout_id: int) -> WorkoutPublic:
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

        workout = self.workout_repository.get_visible_by_id(user_id, workout_id)
        if workout is None:
            self.logger.warning("Workout with ID %s not found or not visible to user %s.", workout_id, user_id)
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        self.logger.debug("Workout with ID %s retrieved successfully for user %s.", workout_id, user_id)
        return workout

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
        search: str | None = None,
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
        self.logger.debug(
            "Listed %s workouts for user %s with limit %s and offset %s.", len(workouts), user_id, limit, offset
        )
        return workouts

    def update(self, user_id: int, workout_id: int, workout_data: WorkoutUpdate) -> WorkoutPublic:
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
                "Workout with ID %s not found or not visible to user %s for update.", workout_id, user_id
            )
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        try:
            updated_workout = self.workout_repository.update_owned(user_id, workout_id, workout_data)
        except WorkoutRepositoryError as exc:
            self.logger.exception("Failed to update workout with ID %s for user %s.", workout_id, user_id)
            raise WorkoutUpdateError.update_failed(workout_id=workout_id) from exc

        if updated_workout is None:
            self.logger.warning(
                "Workout with ID %s not found after update attempt for user %s.", workout_id, user_id
            )
            raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)

        self.logger.info("Workout with ID %s updated successfully for user %s.", workout_id, user_id)

        return updated_workout

    def delete(self, user_id: int, workout_id: int) -> None:
        """Delete a workout by ID if it belongs to the user.

        Args:
            workout_id: ID of the workout to delete
            user_id: ID of the user requesting the deletion

        Raises:
            WorkoutNotFoundError: If the workout is not found or not visible to the user
            WorkoutDeleteError: If the delete operation fails

        Returns:
            None after successful completion.
        """
        existing_workout = self.workout_repository.get_by_user_and_id(user_id, workout_id)
        if existing_workout is None:
            self.logger.warning(
                "Workout with ID %s not found or not visible to user %s for deletion.", workout_id, user_id
            )
            raise WorkoutNotFoundError.not_found(workout_id=workout_id)

        try:
            deleted = self.workout_repository.delete_owned(user_id, workout_id)
        except WorkoutRepositoryError as exc:
            self.logger.exception("Failed to delete workout with ID %s for user %s.", workout_id, user_id)
            raise WorkoutDeleteError.delete_failed(workout_id=workout_id) from exc

        if not deleted:
            self.logger.warning(
                "Workout with ID %s not found after delete attempt for user %s.", workout_id, user_id
            )
            raise WorkoutNotFoundError.not_accessible(workout_id=workout_id)

        self.logger.info("Workout with ID %s deleted successfully for user %s.", workout_id, user_id)
