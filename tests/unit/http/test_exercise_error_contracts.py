"""Exercise business validation, not-found, conflict, and persistence status codes."""

from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import call, create_autospec, patch

from core.errors.repository import ExerciseRepositoryError
from dependencies.auth import get_current_user
from dependencies.providers import get_exercise_repository
from main import app
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from tests.fixtures import EXERCISE_ID, USER_ID, exercise, user
from tests.unit.http.test_exception_handlers import request


class ExerciseErrorContractTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(ExerciseRepositoryPort, instance=True, spec_set=True)
        self.repo.get_visible_by_id.return_value = exercise()
        self.repo.name_exists_visible.return_value = False
        self.repo.update_owned.return_value = exercise()
        self.repo.delete_owned.return_value = True
        self.path = f"/exercises/{EXERCISE_ID}"
        self.enterContext(
            patch.dict(
                app.dependency_overrides,
                {
                    get_current_user: user,
                    get_exercise_repository: lambda: self.repo,
                },
                clear=True,
            )
        )
        self.enterContext(patch("services.exercise_service.logging.getLogger"))
        self.enterContext(patch("core.exception_handlers.logger"))

    async def test_missing_or_unowned_update_is_404_before_duplicate_validation(self) -> None:
        self.repo.name_exists_visible.return_value = True
        for existing in (None, exercise().model_copy(update={"created_by": None, "is_custom": False})):
            with self.subTest(existing=existing):
                self.repo.reset_mock()
                self.repo.get_visible_by_id.return_value = existing
                response = await request(app, self.path, "PATCH", {"name": "Taken"})
                self.assertEqual(response.status, 404)
                self.assertEqual(self.repo.mock_calls, [call.get_visible_by_id(USER_ID, EXERCISE_ID)])

    async def test_owned_duplicate_rename_is_409_and_does_not_write(self) -> None:
        self.repo.name_exists_visible.return_value = True
        response = await request(app, self.path, "PATCH", {"name": "Taken"})
        self.assertEqual(response.status, 409)
        self.assertEqual(response.payload, {"detail": "An exercise with the name 'Taken' already exists."})
        self.repo.update_owned.assert_not_called()

    async def test_predefined_delete_is_400_and_does_not_write(self) -> None:
        self.repo.get_visible_by_id.return_value = exercise().model_copy(
            update={"created_by": None, "is_custom": False}
        )
        response = await request(app, self.path, "DELETE")
        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload, {"detail": "Only custom exercises can be deleted."})
        self.repo.delete_owned.assert_not_called()

    async def test_repository_write_failures_are_safe_500_errors(self) -> None:
        for method, operation, detail in (
            ("PATCH", "update_owned", "Failed to update exercise."),
            ("DELETE", "delete_owned", f"Failed to delete exercise with ID {EXERCISE_ID}."),
        ):
            with (
                self.subTest(method=method),
                patch.object(
                    self.repo, operation, side_effect=ExerciseRepositoryError("private SQL credentials")
                ),
            ):
                response = await request(app, self.path, method, {} if method == "PATCH" else None)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": detail})

    async def test_disappearing_update_and_delete_are_404(self) -> None:
        self.repo.update_owned.return_value = None
        self.repo.delete_owned.return_value = False
        for method in ("PATCH", "DELETE"):
            response = await request(app, self.path, method, {} if method == "PATCH" else None)
            self.assertEqual(response.status, 404)

    async def test_missing_delete_is_404_without_mutation(self) -> None:
        self.repo.get_visible_by_id.return_value = None
        response = await request(app, self.path, "DELETE")
        self.assertEqual(response.status, 404)
        self.repo.delete_owned.assert_not_called()
