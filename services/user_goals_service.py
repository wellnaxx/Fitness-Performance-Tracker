from core.errors.goals import (
    UserGoalCreationError,
    UserGoalNotFoundError,
    UserGoalValidationError,
)
from core.errors.repository import UserGoalsRepositoryError
from repositories.user_goals_repository import UserGoalsRepository
from schemas.user_goals_schema import (
    UserGoalCreate,
    UserGoalPublic,
    UserGoalUpdate,
)
from schemas.user_schema import UserInternal


class UserGoalsService:
    """
    Business logic for user goal operations.

    Responsibilities:
    - Enforce one active goal per user
    - Ensure users only access their own goals
    - Coordinate repository operations
    """

    def __init__(self, goals_repo: UserGoalsRepository) -> None:
        self.goals_repo = goals_repo

    def create_goal(
        self,
        current_user: UserInternal,
        goal_data: UserGoalCreate,
    ) -> UserGoalPublic:
        """
        Create a new goal for the authenticated user.

        Business Rules:
        - If the new goal is active, any existing active goal is deactivated first.
        """

        if goal_data.is_active:
            current_active = self.goals_repo.get_active_goal(current_user.id)
            if current_active is not None:
                self.goals_repo.deactivate_goal(current_active.id)

        try:
            return self.goals_repo.create(current_user.id, goal_data)
        except UserGoalsRepositoryError as exc:
            raise UserGoalCreationError.create_failed() from exc

    def get_current_goal(self, current_user: UserInternal) -> UserGoalPublic | None:
        """
        Return the currently active goal for the authenticated user.
        """
        return self.goals_repo.get_active_goal(current_user.id)

    def get_goal_history(
        self,
        current_user: UserInternal,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserGoalPublic]:
        """
        Return the authenticated user's full goal history with pagination.
        """
        return self.goals_repo.get_all(current_user.id, limit, offset)

    def get_goal_by_id(
        self,
        current_user: UserInternal,
        goal_id: int,
    ) -> UserGoalPublic:
        """
        Return one goal by ID if it belongs to the authenticated user.

        Raises:
            UserGoalNotFoundError: If the goal does not exist or does not belong to the user.
        """
        goal = self.goals_repo.get_by_user_and_id(current_user.id, goal_id)
        if goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)
        return goal

    def update_goal(
        self,
        current_user: UserInternal,
        goal_id: int,
        update_data: UserGoalUpdate,
    ) -> UserGoalPublic:
        """
        Update one of the authenticated user's goals.

        Business Rules:
        - Goal must belong to the current user.
        - If the goal is being activated, any existing active goal is deactivated first.
        """

        existing_goal = self.goals_repo.get_by_user_and_id(current_user.id, goal_id)
        if existing_goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        next_start_date = (
            update_data.start_date if update_data.start_date is not None else existing_goal.start_date
        )
        next_end_date = update_data.end_date if update_data.end_date is not None else existing_goal.end_date
        if next_end_date is not None and next_end_date < next_start_date:
            raise UserGoalValidationError.end_date_before_start_date()

        if update_data.is_active is True:
            current_active = self.goals_repo.get_active_goal(current_user.id)
            if current_active is not None and current_active.id != goal_id:
                self.goals_repo.deactivate_goal(current_active.id)

        updated_goal = self.goals_repo.update(goal_id, update_data)
        if updated_goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        return updated_goal

    def activate_goal(
        self,
        current_user: UserInternal,
        goal_id: int,
    ) -> UserGoalPublic:
        """
        Mark one of the user's goals as the active one.

        Business Rules:
        - Goal must belong to the current user.
        - Only one goal may be active at a time.
        """
        goal = self.goals_repo.get_by_user_and_id(current_user.id, goal_id)
        if goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        activated_goal = self.goals_repo.activate_goal(current_user.id, goal_id)
        if activated_goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        return activated_goal

    def deactivate_goal(
        self,
        current_user: UserInternal,
        goal_id: int,
    ) -> UserGoalPublic:
        """
        Mark one of the user's goals as inactive.
        """
        goal = self.goals_repo.get_by_user_and_id(current_user.id, goal_id)
        if goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        updated_goal = self.goals_repo.deactivate_goal(goal_id)
        if updated_goal is None:
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)

        return updated_goal
