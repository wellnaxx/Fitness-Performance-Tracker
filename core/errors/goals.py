from __future__ import annotations

from core.errors.base import ServiceError


class UserGoalsError(ServiceError):
    """Base error for user goals operations."""


class UserGoalNotFoundError(UserGoalsError):
    """Raised when a goal is not found or does not belong to the user."""

    @classmethod
    def not_found(cls, goal_id: int) -> UserGoalNotFoundError:
        return cls(f"Goal with ID {goal_id} not found.")

    @classmethod
    def no_active_goal(cls) -> UserGoalNotFoundError:
        return cls("No active goal found for the user.")


class UserGoalCreationError(UserGoalsError):
    """Raised when creating a user goal fails."""

    @classmethod
    def create_failed(cls) -> UserGoalCreationError:
        return cls("Failed to create goal.")


class UserGoalValidationError(UserGoalsError):
    """Raised when user goal business rules are violated."""

    @classmethod
    def end_date_before_start_date(cls) -> UserGoalValidationError:
        return cls("end_date cannot be earlier than start_date")
