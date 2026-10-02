"""Goal ownership, activation transitions, and merged date validation."""

import unittest
from datetime import date
from unittest.mock import call, create_autospec

from core.errors.goals import UserGoalCreationError, UserGoalNotFoundError, UserGoalValidationError
from core.errors.repository import UserGoalsRepositoryError
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from schemas.user_goals_schema import UserGoalCreate, UserGoalUpdate
from services.user_goals_service import UserGoalsService
from tests.fixtures import GOAL_ID, TODAY, USER_ID, goal, user


class UserGoalsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(UserGoalsRepositoryPort, instance=True, spec_set=True)
        self.service = UserGoalsService(self.repo)
        self.user = user()
        self.goal = goal()
        self.data = UserGoalCreate.model_validate(self.goal.model_dump())
        self.repo.get_active_goal.return_value = None
        self.repo.get_by_user_and_id.return_value = self.goal
        self.repo.create.return_value = self.goal
        self.repo.update.return_value = self.goal
        self.repo.activate_goal.return_value = self.goal
        self.repo.deactivate_goal.return_value = self.goal.model_copy(update={"is_active": False})

    def test_create_first_active_goal(self) -> None:
        self.assertIs(self.service.create_goal(self.user, self.data), self.goal)
        self.repo.get_active_goal.assert_called_once_with(USER_ID)
        self.repo.deactivate_goal.assert_not_called()
        self.repo.create.assert_called_once_with(USER_ID, self.data)

    def test_create_active_goal_deactivates_previous_goal_before_creation(self) -> None:
        self.repo.get_active_goal.return_value = self.goal.model_copy(update={"id": 99})
        self.service.create_goal(self.user, self.data)
        self.assertEqual(
            self.repo.mock_calls,
            [
                call.get_active_goal(USER_ID),
                call.deactivate_goal(99),
                call.create(USER_ID, self.data),
            ],
        )

    def test_create_inactive_goal_leaves_active_goal_untouched(self) -> None:
        self.data.is_active = False
        self.service.create_goal(self.user, self.data)
        self.repo.get_active_goal.assert_not_called()
        self.repo.deactivate_goal.assert_not_called()
        self.repo.create.assert_called_once_with(USER_ID, self.data)

    def test_creation_failure_preserves_repository_cause(self) -> None:
        failure = UserGoalsRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        with self.assertRaises(UserGoalCreationError) as raised:
            self.service.create_goal(self.user, self.data)
        self.assertIs(raised.exception.__cause__, failure)

    def test_current_goal_can_be_present_or_absent(self) -> None:
        for active in (self.goal, None):
            with self.subTest(active=active):
                self.repo.get_active_goal.reset_mock()
                self.repo.get_active_goal.return_value = active
                self.assertIs(self.service.get_current_goal(self.user), active)
                self.repo.get_active_goal.assert_called_once_with(USER_ID)

    def test_history_is_scoped_and_paginated_including_empty_result(self) -> None:
        for results in ([self.goal], []):
            with self.subTest(results=results):
                self.repo.get_all.reset_mock()
                self.repo.get_all.return_value = results
                self.assertEqual(self.service.get_goal_history(self.user, limit=2, offset=3), results)
                self.repo.get_all.assert_called_once_with(USER_ID, 2, 3)

    def test_get_owned_goal(self) -> None:
        self.assertIs(self.service.get_goal_by_id(self.user, GOAL_ID), self.goal)
        self.repo.get_by_user_and_id.assert_called_once_with(USER_ID, GOAL_ID)

    def test_missing_or_foreign_goal_blocks_every_operation(self) -> None:
        operations = {
            "get": lambda: self.service.get_goal_by_id(self.user, GOAL_ID),
            "update": lambda: self.service.update_goal(self.user, GOAL_ID, UserGoalUpdate(is_active=True)),
            "activate": lambda: self.service.activate_goal(self.user, GOAL_ID),
            "deactivate": lambda: self.service.deactivate_goal(self.user, GOAL_ID),
        }
        self.repo.get_by_user_and_id.return_value = None
        for name, operation in operations.items():
            with self.subTest(operation=name):
                self.repo.reset_mock()
                with self.assertRaises(UserGoalNotFoundError):
                    operation()
                self.assertEqual(self.repo.mock_calls, [call.get_by_user_and_id(USER_ID, GOAL_ID)])

    def test_partial_date_changes_are_checked_against_stored_dates(self) -> None:
        for updates in (
            UserGoalUpdate(start_date=date(2026, 11, 1), is_active=True),
            UserGoalUpdate(end_date=date(2026, 9, 30), is_active=True),
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(UserGoalValidationError):
                    self.service.update_goal(self.user, GOAL_ID, updates)
                self.repo.get_active_goal.assert_not_called()
                self.repo.deactivate_goal.assert_not_called()
                self.repo.update.assert_not_called()

    def test_equal_dates_open_ended_goals_and_non_date_updates_are_allowed(self) -> None:
        cases = (
            (self.goal, UserGoalUpdate(end_date=TODAY)),
            (self.goal, UserGoalUpdate(start_date=date(2026, 10, 31))),
            (self.goal, UserGoalUpdate(protein_target=0, is_active=False)),
            (self.goal, UserGoalUpdate()),
            (self.goal.model_copy(update={"end_date": None}), UserGoalUpdate(start_date=date(2026, 11, 1))),
        )
        for existing, updates in cases:
            with self.subTest(existing=existing, updates=updates):
                self.repo.reset_mock()
                self.repo.get_by_user_and_id.return_value = existing
                self.assertIs(self.service.update_goal(self.user, GOAL_ID, updates), self.goal)
                self.repo.update.assert_called_once_with(GOAL_ID, updates)
                self.repo.get_active_goal.assert_not_called()
                self.repo.deactivate_goal.assert_not_called()

    def test_update_activation_deactivates_only_a_different_active_goal(self) -> None:
        updates = UserGoalUpdate(is_active=True)
        for active in (None, self.goal, self.goal.model_copy(update={"id": 99})):
            with self.subTest(active=active):
                self.repo.reset_mock()
                self.repo.get_active_goal.return_value = active
                self.service.update_goal(self.user, GOAL_ID, updates)
                expected = [call.get_by_user_and_id(USER_ID, GOAL_ID), call.get_active_goal(USER_ID)]
                if active is not None and active.id != GOAL_ID:
                    expected.append(call.deactivate_goal(99))
                expected.append(call.update(GOAL_ID, updates))
                self.assertEqual(self.repo.mock_calls, expected)

    def test_activate_owned_goal_uses_user_scoped_repository_operation(self) -> None:
        self.assertIs(self.service.activate_goal(self.user, GOAL_ID), self.goal)
        self.repo.activate_goal.assert_called_once_with(USER_ID, GOAL_ID)

    def test_deactivate_owned_goal(self) -> None:
        result = self.service.deactivate_goal(self.user, GOAL_ID)
        self.assertFalse(result.is_active)
        self.repo.deactivate_goal.assert_called_once_with(GOAL_ID)

    def test_goal_disappearing_during_write_raises_not_found(self) -> None:
        self.repo.update.return_value = None
        self.repo.activate_goal.return_value = None
        self.repo.deactivate_goal.return_value = None
        operations = {
            "update": lambda: self.service.update_goal(self.user, GOAL_ID, UserGoalUpdate(protein_target=0)),
            "activate": lambda: self.service.activate_goal(self.user, GOAL_ID),
            "deactivate": lambda: self.service.deactivate_goal(self.user, GOAL_ID),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name), self.assertRaises(UserGoalNotFoundError):
                operation()
