"""Logging preserves transaction truth and omits request contents and credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import Mock, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.database import DatabaseError
from core.errors.user import InvalidAccessTokenError, InvalidCredentialsError
from dependencies.auth import get_current_user
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import (
    UnitOfWorkPort,
    UnitOfWorkSetEntryRepositoryPort,
    UnitOfWorkUserGoalsRepositoryPort,
)
from schemas.set_entry_schema import SetEntryCreate, SetEntryUpdate
from schemas.user_goals_schema import UserGoalCreate, UserGoalUpdate
from schemas.user_schema import UserLogin
from services.exercise_service import ExerciseService
from services.set_entry_service import SetEntryService
from services.user_goals_service import UserGoalsService
from services.user_service import UserService
from tests.fixtures import ENTRY_ID, GOAL_ID, SET_ENTRY_ID, USER_ID, entry, goal, set_entry, user, workout

if TYPE_CHECKING:
    from collections.abc import Callable

    from schemas.user_schema import UserInternal


class TransactionOutcomeLoggingTests(TestCase):
    def setUp(self) -> None:
        self.uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        self.uow.__enter__.return_value = self.uow
        self.uow.__exit__.return_value = None
        sets = create_autospec(SetEntryRepositoryPort, instance=True, spec_set=True)
        exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        self.tx_sets = create_autospec(UnitOfWorkSetEntryRepositoryPort, instance=True, spec_set=True)
        self.tx_goals = create_autospec(UnitOfWorkUserGoalsRepositoryPort, instance=True, spec_set=True)
        self.read_goals = create_autospec(UserGoalsRepositoryPort, instance=True, spec_set=True)
        self.uow.set_entry = self.tx_sets
        self.uow.goals = self.tx_goals
        self.user = user()
        self.record = set_entry()
        self.goal = goal()
        sets.get_by_id.return_value = self.record
        sets.list_by_workout_exercise.return_value = []
        exercises.get_by_id.return_value = entry()
        workouts.get_by_user_and_id.return_value = workout()
        self.tx_sets.lock_for_workout_exercise.return_value = True
        self.tx_sets.list_by_workout_exercise.return_value = [self.record] * 3
        self.tx_sets.get_by_workout_exercise_and_id.return_value = self.record
        self.tx_sets.create.return_value = self.record
        self.tx_sets.update_in_workout_exercise.return_value = self.record
        self.tx_sets.delete_in_workout_exercise.return_value = True
        self.tx_goals.lock_for_user.return_value = True
        self.tx_goals.get_active_goal.return_value = None
        self.tx_goals.get_by_user_and_id.return_value = self.goal
        self.tx_goals.create.return_value = self.goal
        self.tx_goals.update.return_value = self.goal
        self.tx_goals.activate_goal.return_value = self.goal
        self.tx_goals.deactivate_goal.return_value = self.goal
        self.sets = SetEntryService(sets, exercises, workouts, self.uow)
        self.goals = UserGoalsService(self.read_goals, self.uow)

    def mutations(self) -> tuple[tuple[str, Callable[[], object]], ...]:
        return (
            (
                "services.set_entry_service",
                lambda: self.sets.create(USER_ID, SetEntryCreate.model_validate(self.record.model_dump())),
            ),
            (
                "services.set_entry_service",
                lambda: self.sets.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(reps=0)),
            ),
            ("services.set_entry_service", lambda: self.sets.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID)),
            (
                "services.user_goals_service",
                lambda: self.goals.create_goal(
                    self.user, UserGoalCreate.model_validate(self.goal.model_dump())
                ),
            ),
            (
                "services.user_goals_service",
                lambda: self.goals.update_goal(self.user, GOAL_ID, UserGoalUpdate()),
            ),
            ("services.user_goals_service", lambda: self.goals.activate_goal(self.user, GOAL_ID)),
            ("services.user_goals_service", lambda: self.goals.deactivate_goal(self.user, GOAL_ID)),
        )

    def test_success_is_logged_only_after_commit_and_context_exit(self) -> None:
        for module, operation in self.mutations():
            with self.subTest(operation=operation), patch(f"{module}.logger") as logger:
                events = Mock()
                events.attach_mock(self.uow.commit, "commit")
                events.attach_mock(self.uow.__exit__, "exit")
                events.attach_mock(logger.info, "success")
                operation()
                self.assertEqual([event[0] for event in events.mock_calls], ["commit", "exit", "success"])
                logger.info.assert_called_once()
                self.assertIn(USER_ID, logger.info.call_args.args)

    def test_commit_and_context_exit_failures_never_log_success(self) -> None:
        for failing_step in ("commit", "__exit__"):
            for module, operation in self.mutations():
                failure = DatabaseError("injected failure")
                with (
                    self.subTest(step=failing_step, operation=operation),
                    patch.object(self.uow, failing_step, side_effect=failure),
                    patch(f"{module}.logger") as logger,
                    self.assertRaises(DatabaseError) as raised,
                ):
                    operation()
                self.assertIs(raised.exception, failure)
                logger.info.assert_not_called()

    def test_empty_read_results_are_debug_events_without_payload_values(self) -> None:
        self.read_goals.get_active_goal.return_value = None
        self.read_goals.get_all.return_value = []
        exercises = create_autospec(ExerciseRepositoryPort, instance=True, spec_set=True)
        exercises.list_visible.return_value = []
        exercise_service = ExerciseService(exercises)
        operations: tuple[tuple[str, Callable[[], object]], ...] = (
            ("services.set_entry_service", lambda: self.sets.list_by_workout_exercise(USER_ID, ENTRY_ID)),
            ("services.user_goals_service", lambda: self.goals.get_current_goal(self.user)),
            ("services.user_goals_service", lambda: self.goals.get_goal_history(self.user)),
            (
                "services.exercise_service",
                lambda: exercise_service.list_visible_by_user(USER_ID, search="private search"),
            ),
        )
        for module, operation in operations:
            with self.subTest(operation=operation), self.assertLogs(module, level="DEBUG") as logs:
                operation()
            self.assertTrue(all(record.levelname == "DEBUG" for record in logs.records))
            self.assertNotIn("private search", " ".join(logs.output))


class AuthenticationLoggingTests(TestCase):
    def test_login_rejection_does_not_reveal_email_password_or_account_existence(self) -> None:
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        service = UserService(repo)
        outputs: list[list[str]] = []
        for found in (None, user()):
            repo.get_by_email.return_value = found
            with (
                patch("services.user_service.verify_password", return_value=False),
                self.assertLogs("services.user_service", level="WARNING") as logs,
                self.assertRaises(InvalidCredentialsError),
            ):
                service.login_user(UserLogin(email="private@example.com", password="private-password"))
            outputs.append(logs.output)
            self.assertNotIn("private", " ".join(logs.output))
        self.assertEqual(outputs[0], outputs[1])

    def test_access_rejections_log_reasons_without_raw_token_or_untrusted_subject(self) -> None:
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        token = TokenPayload(str(USER_ID), 0, 1, "private-jti", "access", "private-name", 2)
        cases: tuple[tuple[TokenPayload | None, UserInternal | None], ...] = (
            (None, user()),
            (TokenPayload("", 0, 1, "jti", "access", "name", 2), user()),
            (TokenPayload("private-subject", 0, 1, "jti", "access", "name", 2), user()),
            (token, None),
            (token, user().model_copy(update={"token_version": 3})),
        )
        for payload, found in cases:
            repo.get_by_id.return_value = found
            with (
                self.subTest(payload=payload),
                patch("dependencies.auth.decode_token", return_value=payload),
                self.assertLogs("dependencies.auth", level="WARNING") as logs,
                self.assertRaises(InvalidAccessTokenError),
            ):
                get_current_user("private-token", repo)
            self.assertEqual(len(logs.records), 1)
            self.assertNotIn("private", " ".join(logs.output))
            self.assertIsNone(logs.records[0].exc_info)
