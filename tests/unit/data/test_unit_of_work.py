"""Transaction lifecycle and atomic goal flows without a running PostgreSQL server."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from psycopg import OperationalError

from core.errors.database import DatabaseError
from core.errors.goals import UserGoalCreationError, UserGoalNotFoundError, UserGoalValidationError
from core.errors.repository import UserGoalRowError
from data.queries import QUERIES
from data.unit_of_work import PostgresUnitOfWork
from dependencies.providers import get_unit_of_work, get_user_goals_service
from repositories.user_goals_repository import UserGoalsRepository
from repositories.user_goals_unit_of_work_repository import UserGoalsUnitOfWorkRepository
from schemas.user_goals_schema import UserGoalCreate, UserGoalUpdate
from tests.fixtures import GOAL_ID, USER_ID, goal, user


class PostgresUnitOfWorkTests(TestCase):
    def setUp(self) -> None:
        self.conn = MagicMock(spec_set=("cursor", "commit", "rollback", "close"))
        self.cursor = MagicMock(
            spec_set=("execute", "fetchone", "fetchall", "rowcount", "description", "close")
        )
        self.conn.cursor.return_value = self.cursor
        self.connection_patch = patch("data.unit_of_work.get_connection", return_value=self.conn)
        self.connect = self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.uow = PostgresUnitOfWork()

    def assert_closed(self) -> None:
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()
        with self.assertRaises(DatabaseError):
            _ = self.uow.goals

    def test_provider_constructs_unit_of_work_without_opening_a_connection(self) -> None:
        self.assertIsInstance(get_unit_of_work(), PostgresUnitOfWork)
        self.connect.assert_not_called()

    def test_commit_is_explicit_and_closes_resources_without_rollback(self) -> None:
        with self.uow as uow:
            self.assertIs(uow, self.uow)
            self.assertIsInstance(uow.goals, UserGoalsUnitOfWorkRepository)
            self.conn.commit.assert_not_called()
            uow.commit()
        self.connect.assert_called_once_with()
        self.conn.cursor.assert_called_once_with()
        self.conn.commit.assert_called_once_with()
        self.conn.rollback.assert_not_called()
        self.assert_closed()

    def test_clean_exit_without_commit_rolls_back(self) -> None:
        with self.uow:
            pass
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_called_once_with()
        self.assert_closed()

    def test_explicit_rollback_never_commits(self) -> None:
        with self.uow as uow:
            uow.rollback()
            self.conn.rollback.assert_called_once_with()
        self.conn.commit.assert_not_called()
        self.assert_closed()

    def test_application_and_database_errors_roll_back_and_keep_their_identity(self) -> None:
        failures: tuple[BaseException, ...] = (
            UserGoalNotFoundError.not_found(GOAL_ID),
            UserGoalValidationError.end_date_before_start_date(),
            DatabaseError.missing_returning_id(),
            UserGoalRowError.invalid_type("id", "int"),
            KeyboardInterrupt(),
        )
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                self.conn.reset_mock()
                self.cursor.reset_mock()
                with self.assertRaises(type(failure)) as raised, self.uow:
                    raise failure
                self.assertIs(raised.exception, failure)
                self.conn.rollback.assert_called_once_with()
                self.conn.commit.assert_not_called()
                self.assert_closed()

    def test_driver_error_becomes_database_error_after_rollback(self) -> None:
        failure = OperationalError("statement failed")
        with (
            self.assertLogs("data.unit_of_work", level="ERROR"),
            self.assertRaises(DatabaseError) as raised,
            self.uow,
        ):
            raise failure
        self.assertIs(raised.exception.__cause__, failure)
        self.conn.rollback.assert_called_once_with()
        self.assert_closed()

    def test_failed_commit_rolls_back_and_preserves_the_cause(self) -> None:
        failure = OperationalError("commit failed")
        self.conn.commit.side_effect = failure
        with (
            self.assertLogs("data.unit_of_work", level="ERROR"),
            self.assertRaises(DatabaseError) as raised,
            self.uow as uow,
        ):
            uow.commit()
        self.assertIs(raised.exception.__cause__, failure)
        self.conn.rollback.assert_called_once_with()
        self.assert_closed()

    def test_existing_database_error_during_commit_or_rollback_is_not_wrapped(self) -> None:
        for method in ("commit", "rollback"):
            with self.subTest(method=method):
                self.conn.reset_mock(side_effect=True)
                self.cursor.reset_mock()
                failure = DatabaseError.missing_returning_id()
                getattr(self.conn, method).side_effect = failure
                with (
                    patch("data.unit_of_work.logger"),
                    self.assertRaises(DatabaseError) as raised,
                    self.uow as uow,
                ):
                    getattr(uow, method)()
                self.assertIs(raised.exception, failure)
                self.assert_closed()

    def test_rollback_failure_on_clean_exit_is_reported_after_cleanup(self) -> None:
        failure = OperationalError("rollback failed")
        self.conn.rollback.side_effect = failure
        with (
            self.assertLogs("data.unit_of_work", level="ERROR"),
            self.assertRaises(DatabaseError) as raised,
            self.uow,
        ):
            pass
        self.assertIs(raised.exception.__cause__, failure)
        self.assert_closed()

    def test_rollback_failure_does_not_replace_original_application_or_driver_error(self) -> None:
        failures = (UserGoalNotFoundError.not_found(GOAL_ID), OperationalError("statement failed"))
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                self.conn.reset_mock()
                self.cursor.reset_mock()
                self.conn.rollback.side_effect = OperationalError("rollback failed")
                expected = DatabaseError if isinstance(failure, OperationalError) else type(failure)
                with (
                    self.assertLogs("data.unit_of_work", level="ERROR"),
                    self.assertRaises(expected) as raised,
                    self.uow,
                ):
                    raise failure
                if isinstance(failure, OperationalError):
                    self.assertIs(raised.exception.__cause__, failure)
                else:
                    self.assertIs(raised.exception, failure)
                self.assert_closed()

    def test_connection_open_failure_leaves_no_active_repository(self) -> None:
        for failure in (OperationalError("connection failed"), DatabaseError.missing_returning_id()):
            with self.subTest(error=type(failure).__name__):
                self.connect.side_effect = failure
                with patch("data.unit_of_work.logger"), self.assertRaises(DatabaseError) as raised:
                    self.uow.__enter__()
                if isinstance(failure, DatabaseError):
                    self.assertIs(raised.exception, failure)
                else:
                    self.assertIs(raised.exception.__cause__, failure)
                self.conn.close.assert_not_called()
                with self.assertRaises(DatabaseError):
                    _ = self.uow.goals

    def test_cursor_open_failure_closes_connection(self) -> None:
        failure = OperationalError("cursor failed")
        self.conn.cursor.side_effect = failure
        with self.assertLogs("data.unit_of_work", level="ERROR"), self.assertRaises(DatabaseError) as raised:
            self.uow.__enter__()
        self.assertIs(raised.exception.__cause__, failure)
        self.conn.close.assert_called_once_with()
        self.cursor.close.assert_not_called()

    def test_repository_setup_failure_closes_both_resources(self) -> None:
        failure = RuntimeError("repository setup failed")
        with (
            patch("data.unit_of_work.UserGoalsUnitOfWorkRepository", side_effect=failure),
            self.assertLogs("data.unit_of_work", level="ERROR"),
            self.assertRaises(DatabaseError) as raised,
        ):
            self.uow.__enter__()
        self.assertIs(raised.exception.__cause__, failure)
        self.assert_closed()

    def test_close_failures_are_logged_and_connection_close_is_still_attempted(self) -> None:
        self.cursor.close.side_effect = OperationalError("cursor close failed")
        self.conn.close.side_effect = OperationalError("connection close failed")
        failure = UserGoalNotFoundError.not_found(GOAL_ID)
        with (
            self.assertLogs("data.unit_of_work", level="ERROR") as logs,
            self.assertRaises(UserGoalNotFoundError) as raised,
            self.uow,
        ):
            raise failure
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(logs.records), 2)
        self.assert_closed()

    def test_commit_rollback_and_repository_access_require_active_context(self) -> None:
        for operation in (self.uow.commit, self.uow.rollback, lambda: self.uow.goals):
            with self.subTest(operation=operation), self.assertRaises(DatabaseError):
                operation()
        self.connect.assert_not_called()

    def test_nested_entry_is_rejected_without_replacing_outer_transaction(self) -> None:
        with self.uow as uow:
            repository = uow.goals
            with self.assertRaises(DatabaseError):
                self.uow.__enter__()
            self.assertIs(uow.goals, repository)
            self.connect.assert_called_once_with()
            uow.commit()
        self.assert_closed()

    def test_reuse_opens_fresh_resources_and_resets_commit_state(self) -> None:
        second_conn = MagicMock(spec_set=("cursor", "commit", "rollback", "close"))
        second_cursor = MagicMock(spec_set=("close",))
        second_conn.cursor.return_value = second_cursor
        self.connect.side_effect = (self.conn, second_conn)
        with self.uow as uow:
            first_repository = uow.goals
            uow.commit()
        with self.uow as uow:
            self.assertIsNot(uow.goals, first_repository)
        self.conn.rollback.assert_not_called()
        second_conn.rollback.assert_called_once_with()
        second_cursor.close.assert_called_once_with()
        second_conn.close.assert_called_once_with()


class AtomicGoalOperationTests(TestCase):
    def setUp(self) -> None:
        self.conn = MagicMock(spec_set=("cursor", "commit", "rollback", "close"))
        self.cursor = MagicMock(
            spec_set=("execute", "fetchone", "fetchall", "rowcount", "description", "close")
        )
        self.conn.cursor.return_value = self.cursor
        self.cursor.rowcount = 1
        self.goal = goal()
        self.data = UserGoalCreate.model_validate(self.goal.model_dump())
        self.cursor.description = [SimpleNamespace(name=name) for name in self.goal.model_dump()]
        self.row = tuple(self.goal.model_dump().values())
        self.previous = self.goal.model_copy(update={"id": 99})
        self.previous_row = tuple(self.previous.model_dump().values())
        self.inactive_row = tuple(self.previous.model_copy(update={"is_active": False}).model_dump().values())
        self.uow = PostgresUnitOfWork()
        self.service = get_user_goals_service(UserGoalsRepository(), self.uow)
        connection_patch = patch("data.unit_of_work.get_connection", return_value=self.conn)
        self.connect = connection_patch.start()
        self.addCleanup(connection_patch.stop)

    def assert_rolled_back(self) -> None:
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_called_once_with()
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_create_replacement_goal_uses_one_cursor_and_commits_after_readback(self) -> None:
        self.cursor.fetchone.side_effect = [
            (USER_ID,), self.previous_row, self.inactive_row, (GOAL_ID,), self.row
        ]
        self.conn.commit.side_effect = lambda: self.assertEqual(self.cursor.fetchone.call_count, 5)
        self.assertEqual(self.service.create_goal(user(), self.data), self.goal)
        self.connect.assert_called_once_with()
        self.conn.cursor.assert_called_once_with()
        self.conn.commit.assert_called_once_with()
        self.conn.rollback.assert_not_called()
        executions = self.cursor.execute.call_args_list
        self.assertEqual(executions[0], call(QUERIES.user_goals.lock_for_user, (USER_ID,)))
        self.assertIn("FOR UPDATE", executions[0].args[0])
        self.assertEqual(executions[2], call(QUERIES.user_goals.deactivate_goal, (99,)))
        self.assertEqual(executions[-1], call(QUERIES.user_goals.get_by_id, (GOAL_ID,)))
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_failed_insert_rolls_back_previous_goal_deactivation(self) -> None:
        self.cursor.fetchone.side_effect = [(USER_ID,), self.previous_row, self.inactive_row]
        failure = OperationalError("insert failed")
        self.cursor.execute.side_effect = [None, None, None, None, failure]
        with self.assertLogs("data.unit_of_work", level="ERROR"), self.assertRaises(DatabaseError) as raised:
            self.service.create_goal(user(), self.data)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertEqual(
            self.cursor.execute.call_args_list[2], call(QUERIES.user_goals.deactivate_goal, (99,))
        )
        self.assert_rolled_back()

    def test_insert_without_id_or_missing_readback_rolls_back(self) -> None:
        cases: tuple[tuple[list[tuple[object, ...] | None], type[Exception]], ...] = (
            ([(USER_ID,), self.previous_row, self.inactive_row, None], DatabaseError),
            ([(USER_ID,), self.previous_row, self.inactive_row, (GOAL_ID,), None], UserGoalCreationError),
        )
        for returned_rows, expected in cases:
            with self.subTest(error=expected.__name__):
                self.conn.reset_mock()
                self.cursor.reset_mock()
                self.cursor.fetchone.side_effect = returned_rows
                with self.assertRaises(expected):
                    self.service.create_goal(user(), self.data)
                self.assert_rolled_back()

    def test_invalid_result_mapping_rolls_back_insert_and_deactivation(self) -> None:
        invalid = self.goal.model_dump()
        invalid["target_body_weight"] = "invalid"
        self.cursor.fetchone.side_effect = [
            (USER_ID,), self.previous_row, self.inactive_row, (GOAL_ID,), tuple(invalid.values())
        ]
        with self.assertRaises(UserGoalRowError):
            self.service.create_goal(user(), self.data)
        self.assert_rolled_back()

    def test_update_activation_commits_deactivation_and_update_together(self) -> None:
        self.cursor.fetchone.side_effect = [
            (USER_ID,), self.row, self.previous_row, self.inactive_row, self.row
        ]
        self.assertEqual(self.service.update_goal(user(), GOAL_ID, UserGoalUpdate(is_active=True)), self.goal)
        self.conn.cursor.assert_called_once_with()
        self.conn.commit.assert_called_once_with()
        self.conn.rollback.assert_not_called()
        executions = self.cursor.execute.call_args_list
        self.assertEqual(executions[0], call(QUERIES.user_goals.lock_for_user, (USER_ID,)))
        self.assertEqual(executions[3], call(QUERIES.user_goals.deactivate_goal, (99,)))
        self.assertEqual(executions[-2].args[1], (True, GOAL_ID))

    def test_missing_updated_goal_rolls_back_deactivation(self) -> None:
        self.cursor.fetchone.side_effect = [(USER_ID,), self.row, self.previous_row, self.inactive_row, None]
        with self.assertRaises(UserGoalNotFoundError):
            self.service.update_goal(user(), GOAL_ID, UserGoalUpdate(is_active=True))
        self.assert_rolled_back()

    def test_activate_and_deactivate_read_back_inside_the_transaction(self) -> None:
        for method in ("activate_goal", "deactivate_goal"):
            with self.subTest(operation=method):
                self.conn.reset_mock()
                self.cursor.reset_mock()
                self.cursor.fetchone.side_effect = [(USER_ID,), self.row, self.row]
                self.assertEqual(getattr(self.service, method)(user(), GOAL_ID), self.goal)
                self.conn.cursor.assert_called_once_with()
                self.conn.commit.assert_called_once_with()
                self.conn.rollback.assert_not_called()
                self.assertEqual(
                    self.cursor.execute.call_args_list[-1], call(QUERIES.user_goals.get_by_id, (GOAL_ID,))
                )

    def test_transaction_repository_history_uses_shared_cursor_and_bounds(self) -> None:
        self.cursor.fetchall.return_value = [self.row]
        with self.uow as uow:
            self.assertEqual(uow.goals.get_all(USER_ID, limit=5000, offset=-1), [self.goal])
            self.assertEqual(
                self.cursor.execute.call_args, call(QUERIES.user_goals.get_all, (USER_ID, 1000, 0))
            )
        self.conn.rollback.assert_called_once_with()
        self.conn.commit.assert_not_called()
