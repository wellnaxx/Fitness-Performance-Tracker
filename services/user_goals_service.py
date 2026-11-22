import logging
from collections.abc import Generator
from contextlib import contextmanager

from core.errors.goals import (
    UserGoalCreationError,
    UserGoalNotFoundError,
    UserGoalValidationError,
)
from core.errors.repository import UserGoalsRepositoryError
from core.errors.user import UserNotFoundError
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from ports.unit_of_work import UnitOfWorkPort
from schemas.user_goals_schema import (
    UserGoalCreate,
    UserGoalPublic,
    UserGoalUpdate,
)
from utils.pagination import DEFAULT_LIMIT, DEFAULT_OFFSET

logger = logging.getLogger(__name__)


class UserGoalsService:
    """
    Business logic for user goal operations.

    Responsibilities:
    - Enforce one active goal per user
    - Ensure users only access their own goals
    - Coordinate repository operations
    """

    def __init__(self, goals_repo: UserGoalsRepositoryPort, unit_of_work: UnitOfWorkPort) -> None:
        """Initialize the operation's persistence dependencies.

        Args:
            goals_repo: Repository contract for goal queries.
            unit_of_work: Transaction contract for related writes and locking.
        """
        self.goals_repo = goals_repo
        self.unit_of_work = unit_of_work

    @contextmanager
    def _goal_transaction(self, user_id: int) -> Generator[UnitOfWorkPort]:
        """Open a unit of work and lock the goal owner until transaction completion.

        Args:
            user_id: Authenticated owner ID.

        Returns:
            A context manager yielding the active unit of work; callers explicitly commit.

        Raises:
            UserNotFoundError: If the owner does not exist when locking begins.
            DatabaseError: If the transaction or lock query fails.
        """
        with self.unit_of_work as uow:
            if not uow.goals.lock_for_user(user_id):
                logger.warning("Goal transaction rejected: user missing | user_id=%s", user_id)
                raise UserNotFoundError.not_found(user_id)
            yield uow

    def create(
        self,
        user_id: int,
        goal_data: UserGoalCreate,
    ) -> UserGoalPublic:
        """Create a goal while locking the user and deactivating any previous active goal.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            goal_data: Validated goal values, including dates and the initial active state.

        Returns:
            The persisted goal after the transaction commits.

        Raises:
            UserNotFoundError: If the owner disappears before the transaction acquires its lock.
            UserGoalCreationError: If creation fails; preceding active-goal changes are rolled back.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """

        with self._goal_transaction(user_id) as uow:
            if goal_data.is_active:
                current_active = uow.goals.get_active_goal(user_id)
                if current_active is not None:
                    uow.goals.deactivate_goal(current_active.id)

            try:
                goal = uow.goals.create(user_id, goal_data)
            except UserGoalsRepositoryError as exc:
                logger.exception("Goal creation failed | user_id=%s", user_id)
                raise UserGoalCreationError.create_failed() from exc
            uow.commit()
        logger.info("Goal created | user_id=%s goal_id=%s", user_id, goal.id)
        return goal

    def get_current(self, user_id: int) -> UserGoalPublic | None:
        """Retrieve the authenticated user's active goal.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.

        Returns:
            The active goal, or None when the user has no active goal.

        Raises:
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        goal = self.goals_repo.get_active_goal(user_id)
        logger.debug("Current goal retrieved | user_id=%s found=%s", user_id, goal is not None)
        return goal

    def list_by_user(
        self,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
    ) -> list[UserGoalPublic]:
        """List the authenticated user's goal history with shared pagination.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            limit: Maximum records to return, using the shared pagination default and bounds.
            offset: Records to skip, using the shared pagination default and bounds.

        Returns:
            Owned goals in repository order, or an empty list when none match.

        Raises:
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        goals = self.goals_repo.get_all(user_id, limit, offset)
        logger.debug(
            "Goal history listed | user_id=%s count=%s limit=%s offset=%s",
            user_id,
            len(goals),
            limit,
            offset,
        )
        return goals

    def get_by_id(
        self,
        user_id: int,
        goal_id: int,
    ) -> UserGoalPublic:
        """Retrieve a goal through a user-scoped lookup.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            goal_id: Requested goal ID.

        Returns:
            The goal belonging to the authenticated user.

        Raises:
            UserGoalNotFoundError: If the goal is missing or owned by another user.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        goal = self.goals_repo.get_by_user_and_id(user_id, goal_id)
        if goal is None:
            logger.warning("Goal not found or inaccessible | user_id=%s goal_id=%s", user_id, goal_id)
            raise UserGoalNotFoundError.not_found(goal_id=goal_id)
        logger.debug("Goal retrieved | user_id=%s goal_id=%s", user_id, goal_id)
        return goal

    def update(
        self,
        user_id: int,
        goal_id: int,
        update_data: UserGoalUpdate,
    ) -> UserGoalPublic:
        """Update an owned goal and validate the combined dates within one transaction.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            goal_id: Requested goal ID.
            update_data: Validated partial changes; omitted and None-valued fields preserve stored values.

        Returns:
            The updated goal after commit; an activation also deactivates any other active goal.

        Raises:
            UserNotFoundError: If the owner no longer exists when locking begins.
            UserGoalNotFoundError: If the goal is missing, unowned, or disappears during the update.
            UserGoalValidationError: If the resulting end date precedes the start date.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """

        with self._goal_transaction(user_id) as uow:
            existing_goal = uow.goals.get_by_user_and_id(user_id, goal_id)
            if existing_goal is None:
                logger.warning("Goal not found during update | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            next_start_date = (
                update_data.start_date if update_data.start_date is not None else existing_goal.start_date
            )
            next_end_date = update_data.end_date if update_data.end_date is not None else existing_goal.end_date
            if next_end_date is not None and next_end_date < next_start_date:
                logger.warning(
                    "Goal update rejected: invalid date range | user_id=%s goal_id=%s", user_id, goal_id
                )
                raise UserGoalValidationError.end_date_before_start_date()

            if update_data.is_active is True:
                current_active = uow.goals.get_active_goal(user_id)
                if current_active is not None and current_active.id != goal_id:
                    uow.goals.deactivate_goal(current_active.id)

            updated_goal = uow.goals.update(goal_id, update_data)
            if updated_goal is None:
                logger.warning("Goal disappeared during update | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            uow.commit()
        logger.info("Goal updated | user_id=%s goal_id=%s", user_id, goal_id)
        return updated_goal

    def activate_goal(
        self,
        user_id: int,
        goal_id: int,
    ) -> UserGoalPublic:
        """Activate an owned goal and deactivate any other active goal atomically.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            goal_id: Requested goal ID.

        Returns:
            The active goal after the transaction commits.

        Raises:
            UserNotFoundError: If the owner no longer exists when locking begins.
            UserGoalNotFoundError: If the goal is missing, unowned, or disappears during activation.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        with self._goal_transaction(user_id) as uow:
            goal = uow.goals.get_by_user_and_id(user_id, goal_id)
            if goal is None:
                logger.warning("Goal not found during activation | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            activated_goal = uow.goals.activate_goal(user_id, goal_id)
            if activated_goal is None:
                logger.warning("Goal disappeared during activation | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            uow.commit()
        logger.info("Goal activated | user_id=%s goal_id=%s", user_id, goal_id)
        return activated_goal

    def deactivate_goal(
        self,
        user_id: int,
        goal_id: int,
    ) -> UserGoalPublic:
        """Deactivate an owned goal within the user's locked transaction.

        Args:
            user_id: Authenticated user ID; determines ownership or visibility.
            goal_id: Requested goal ID.

        Returns:
            The inactive goal after the transaction commits.

        Raises:
            UserNotFoundError: If the owner no longer exists when locking begins.
            UserGoalNotFoundError: If the goal is missing, unowned, or disappears during deactivation.
            DatabaseError: If persistence fails.
            RowValidationError: If a stored row cannot be mapped.
            RepositoryError: If an unhandled repository operation fails.
        """
        with self._goal_transaction(user_id) as uow:
            goal = uow.goals.get_by_user_and_id(user_id, goal_id)
            if goal is None:
                logger.warning("Goal not found during deactivation | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            updated_goal = uow.goals.deactivate_goal(goal_id)
            if updated_goal is None:
                logger.warning("Goal disappeared during deactivation | user_id=%s goal_id=%s", user_id, goal_id)
                raise UserGoalNotFoundError.not_found(goal_id=goal_id)

            uow.commit()
        logger.info("Goal deactivated | user_id=%s goal_id=%s", user_id, goal_id)
        return updated_goal
