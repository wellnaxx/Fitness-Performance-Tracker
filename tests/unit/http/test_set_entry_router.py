"""Set-entry HTTP contracts through the registered application and real validation.

Mock the service for transport tests; service/data suites cover ordering and
rollback. Provider tests below also exercise the actual service dependency graph.
No database server, network server, or HTTP client dependency is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.database import DatabaseError
from core.errors.repository import SetEntryRepositoryError, SetEntryRowError
from core.errors.set_entry import (
    SetEntryCreationError,
    SetEntryDeleteError,
    SetEntryNotFoundError,
    SetEntryValidationError,
)
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import WorkoutExerciseNotFoundError, WorkoutExerciseValidationError
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_set_entry_repository,
    get_set_entry_service,
    get_unit_of_work,
    get_user_repository,
    get_workout_exercise_repository,
    get_workout_repository,
)
from main import app
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort, UnitOfWorkSetEntryRepositoryPort
from schemas.set_entry_schema import SetEntryCreate, SetEntryUpdate
from services.set_entry_service import SetEntryService
from tests.fixtures import ENTRY_ID, SET_ENTRY_ID, USER_ID, WORKOUT_ID, entry, set_entry, user, workout
from tests.unit.http.test_exception_handlers import HttpResponse, request

if TYPE_CHECKING:
    from schemas.set_entry_schema import SetEntryPublic
    from schemas.user_schema import UserInternal


@dataclass(frozen=True)
class RouteCase:
    """A valid request and the service method it must reach."""

    method: str
    path: str
    service_method: str
    payload: dict[str, object] | None = None


class SetEntryRouterTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = user()
        self.record = set_entry()
        self.service = create_autospec(SetEntryService, instance=True, spec_set=True)
        self.service.create.return_value = self.record
        self.service.get_by_id.return_value = self.record
        self.service.list_by_workout_exercise.return_value = [self.record]
        self.service.update.return_value = self.record
        self.service.delete.return_value = None
        overrides = patch.dict(
            app.dependency_overrides,
            {get_current_user: lambda: self.user, get_set_entry_service: lambda: self.service},
            clear=True,
        )
        overrides.start()
        self.addCleanup(overrides.stop)

    def create_payload(self) -> dict[str, object]:
        return {"workout_exercise_id": ENTRY_ID, "set_number": 1, "reps": 5, "weight": 20}

    def routes(self) -> tuple[RouteCase, ...]:
        return (
            RouteCase("POST", "/sets/", "create", self.create_payload()),
            RouteCase("GET", f"/sets/{SET_ENTRY_ID}", "get_by_id"),
            RouteCase("GET", f"/sets/workout_exercise/{ENTRY_ID}", "list_by_workout_exercise"),
            RouteCase("PATCH", f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}", "update", {"reps": 0}),
            RouteCase("DELETE", f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}", "delete"),
        )

    def assert_validation_error(self, response: HttpResponse, location: tuple[str | int, ...]) -> None:
        """Require the framework's 422 shape and identify the rejected parameter."""
        self.assertEqual(response.status, 422)
        payload = cast("dict[str, list[dict[str, object]]]", response.payload)
        self.assertTrue(any(error["loc"] == list(location) for error in payload["detail"]), payload)
        self.assertEqual(self.service.mock_calls, [])

    async def test_all_operations_return_expected_status_body_and_service_arguments(self) -> None:
        expected_calls = (
            call.create(USER_ID, SetEntryCreate.model_validate(self.create_payload())),
            call.get_by_id(USER_ID, SET_ENTRY_ID),
            call.list_by_workout_exercise(USER_ID, ENTRY_ID),
            call.update(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(reps=0)),
            call.delete(USER_ID, ENTRY_ID, SET_ENTRY_ID),
        )
        for route, expected_call in zip(self.routes(), expected_calls, strict=True):
            with self.subTest(method=route.method, path=route.path):
                self.service.reset_mock()
                response = await request(app, route.path, route.method, route.payload)
                expected_status = 201 if route.method == "POST" else 204 if route.method == "DELETE" else 200
                self.assertEqual(response.status, expected_status)
                self.assertEqual(self.service.mock_calls, [expected_call])
                if route.method == "DELETE":
                    self.assertEqual(response.body, b"")
                    self.assertIsNone(response.payload)
                else:
                    expected = self.record.model_dump(mode="json")
                    self.assertEqual(
                        response.payload, [expected] if route.service_method.startswith("list") else expected
                    )
                    self.assertEqual(response.headers["content-type"], "application/json")
                    self.assertNotIn("password_hash", str(response.payload))

    async def test_list_returns_empty_array_and_keeps_service_order(self) -> None:
        records = [self.record.model_copy(update={"id": 42, "set_number": 1}), self.record]
        pages: tuple[list[SetEntryPublic], ...] = ([], records)
        for page in pages:
            with self.subTest(size=len(page)):
                self.service.reset_mock()
                self.service.list_by_workout_exercise.return_value = page
                response = await request(app, f"/sets/workout_exercise/{ENTRY_ID}")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [record.model_dump(mode="json") for record in page])
                self.service.list_by_workout_exercise.assert_called_once_with(USER_ID, ENTRY_ID)
                self.service.get_by_id.assert_not_called()

    async def test_create_accepts_defaults_zero_values_and_rpe_boundaries(self) -> None:
        variants: tuple[dict[str, object], ...] = (
            {},
            {"reps": 0, "weight": 0, "rpe": None, "is_warmup": False, "completed": False},
            {"rpe": 1, "is_warmup": True},
            {"rpe": 10},
        )
        for changes in variants:
            with self.subTest(changes=changes):
                self.service.reset_mock()
                payload = {**self.create_payload(), **changes}
                response = await request(app, "/sets/", "POST", payload)
                self.assertEqual(response.status, 201)
                data = SetEntryCreate.model_validate(payload)
                self.service.create.assert_called_once_with(USER_ID, data)
                if not changes:
                    self.assertIsNone(data.rpe)
                    self.assertFalse(data.is_warmup)
                    self.assertTrue(data.completed)

    async def test_patch_accepts_empty_null_partial_and_complete_changes(self) -> None:
        payloads: tuple[dict[str, object], ...] = (
            {},
            {
                "set_number": None,
                "reps": None,
                "weight": None,
                "rpe": None,
                "is_warmup": None,
                "completed": None,
            },
            {"reps": 0, "weight": 0, "is_warmup": False, "completed": False},
            {"rpe": 1},
            {"rpe": 10},
            {"set_number": 1, "reps": 10, "weight": 25.5, "rpe": 8, "is_warmup": True, "completed": True},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.service.reset_mock()
                response = await request(
                    app, f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}", "PATCH", payload
                )
                self.assertEqual(response.status, 200)
                self.service.update.assert_called_once_with(
                    USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate.model_validate(payload)
                )

    async def test_path_ids_accept_one_and_cannot_be_overridden_by_query_parameters(self) -> None:
        routes = (
            RouteCase("GET", "/sets/1?set_entry_id=999", "get_by_id"),
            RouteCase("GET", "/sets/workout_exercise/1?workout_exercise_id=999", "list_by_workout_exercise"),
            RouteCase("PATCH", "/sets/1?workout_exercise_id=1&set_entry_id=999", "update", {}),
            RouteCase("DELETE", "/sets/1?workout_exercise_id=1&set_entry_id=999", "delete"),
        )
        for route in routes:
            with self.subTest(method=route.method, path=route.path):
                self.service.reset_mock()
                response = await request(app, route.path, route.method, route.payload)
                self.assertIn(response.status, (200, 204))
                args = getattr(self.service, route.service_method).call_args.args
                self.assertEqual(args[:2], (USER_ID, 1))
                if route.method in ("PATCH", "DELETE"):
                    self.assertEqual(args[2], 1)

    async def test_invalid_path_ids_return_422_without_calling_service(self) -> None:
        for value in ("0", "-1", "abc", "1.5"):
            routes = (
                RouteCase("GET", f"/sets/{value}", "get_by_id"),
                RouteCase("GET", f"/sets/workout_exercise/{value}", "list_by_workout_exercise"),
                RouteCase("PATCH", f"/sets/{value}?workout_exercise_id={ENTRY_ID}", "update", {}),
                RouteCase("DELETE", f"/sets/{value}?workout_exercise_id={ENTRY_ID}", "delete"),
            )
            for route in routes:
                with self.subTest(value=value, method=route.method, path=route.path):
                    response = await request(app, route.path, route.method, route.payload)
                    field = "workout_exercise_id" if route.service_method.startswith("list") else "set_entry_id"
                    self.assert_validation_error(response, ("path", field))

    async def test_patch_and_delete_require_a_positive_parent_query_parameter(self) -> None:
        for method in ("PATCH", "DELETE"):
            for query in (
                "",
                "?workout_exercise_id=",
                "?workout_exercise_id=0",
                "?workout_exercise_id=-1",
                "?workout_exercise_id=abc",
                "?workout_exercise_id=1.5",
            ):
                with self.subTest(method=method, query=query):
                    response = await request(
                        app, f"/sets/{SET_ENTRY_ID}{query}", method, {} if method == "PATCH" else None
                    )
                    self.assert_validation_error(response, ("query", "workout_exercise_id"))

    async def test_create_rejects_each_missing_or_null_required_field(self) -> None:
        for field in self.create_payload():
            for null in (False, True):
                with self.subTest(field=field, null=null):
                    payload = self.create_payload()
                    if null:
                        payload[field] = None
                    else:
                        del payload[field]
                    response = await request(app, "/sets/", "POST", payload)
                    self.assert_validation_error(response, ("body", field))

    async def test_create_and_patch_reject_invalid_values_and_types(self) -> None:
        cases: tuple[tuple[str, object], ...] = (
            ("set_number", 0),
            ("set_number", -1),
            ("set_number", "bad"),
            ("set_number", 1.5),
            ("reps", -1),
            ("reps", "bad"),
            ("reps", 1.5),
            ("weight", -0.1),
            ("weight", "bad"),
            ("rpe", 0),
            ("rpe", 11),
            ("rpe", "bad"),
            ("rpe", 1.5),
            ("is_warmup", "bad"),
            ("completed", "bad"),
        )
        for method in ("POST", "PATCH"):
            for field, value in cases:
                with self.subTest(method=method, field=field, value=value):
                    payload: dict[str, object] = (
                        {**self.create_payload(), field: value} if method == "POST" else {field: value}
                    )
                    path = (
                        "/sets/" if method == "POST" else f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}"
                    )
                    response = await request(app, path, method, payload)
                    self.assert_validation_error(response, ("body", field))
        for value in ("bad", 1.5):
            response = await request(
                app, "/sets/", "POST", {**self.create_payload(), "workout_exercise_id": value}
            )
            self.assert_validation_error(response, ("body", "workout_exercise_id"))

    async def test_write_endpoints_reject_missing_malformed_and_nonobject_bodies(self) -> None:
        for method, path in (
            ("POST", "/sets/"),
            ("PATCH", f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}"),
        ):
            for body in (b"", b"null", b"{", b"[]", b'"text"', b"1"):
                with self.subTest(method=method, body=body):
                    response = await request(app, path, method, raw_body=body)
                    self.assertEqual(response.status, 422)
                    self.assertEqual(self.service.mock_calls, [])

    async def test_all_endpoints_require_bearer_authentication(self) -> None:
        del app.dependency_overrides[get_current_user]
        for route in self.routes():
            for headers in ({}, {"Authorization": "Basic credentials"}):
                with self.subTest(method=route.method, path=route.path, headers=headers):
                    response = await request(app, route.path, route.method, route.payload, headers)
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    self.assertEqual(self.service.mock_calls, [])

    async def test_invalid_expired_deleted_and_revoked_tokens_block_every_endpoint(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(
            sub=str(USER_ID), iat=0, exp=1, jti="test", type="access", username="test", token_version=2
        )
        cases: tuple[tuple[TokenPayload | None, UserInternal | None, str], ...] = (
            (None, self.user, "Invalid or expired token."),
            (token, None, "User not found. Account may have been deleted."),
            (token, self.user.model_copy(update={"token_version": 3}), "Token revoked. Please log in again."),
        )
        for decoded, current_user, detail in cases:
            for route in self.routes():
                with (
                    self.subTest(detail=detail, method=route.method),
                    patch("dependencies.auth.decode_token", return_value=decoded) as decode,
                ):
                    repo.get_by_id.return_value = current_user
                    response = await request(
                        app, route.path, route.method, route.payload, {"Authorization": "Bearer test-token"}
                    )
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.payload, {"detail": detail})
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    decode.assert_called_once_with("test-token", expected_type="access")
                    self.assertEqual(self.service.mock_calls, [])

    async def test_authenticated_user_id_comes_from_the_token_not_request_data(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        repo.get_by_id.return_value = self.user
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(
            sub=str(USER_ID), iat=0, exp=1, jti="test", type="access", username="test", token_version=2
        )
        with patch("dependencies.auth.decode_token", return_value=token):
            response = await request(
                app,
                "/sets/?user_id=999",
                "POST",
                {**self.create_payload(), "user_id": 999},
                {"Authorization": "Bearer valid-token"},
            )
        self.assertEqual(response.status, 201)
        repo.get_by_id.assert_called_once_with(USER_ID)
        self.service.create.assert_called_once_with(
            USER_ID, SetEntryCreate.model_validate(self.create_payload())
        )

    async def test_patch_cannot_override_parent_or_set_ids_through_the_body(self) -> None:
        response = await request(
            app,
            f"/sets/{SET_ENTRY_ID}?workout_exercise_id={ENTRY_ID}",
            "PATCH",
            {"id": 999, "workout_exercise_id": 999, "user_id": 999, "reps": 0},
        )
        self.assertEqual(response.status, 200)
        self.service.update.assert_called_once_with(USER_ID, ENTRY_ID, SET_ENTRY_ID, SetEntryUpdate(reps=0))

    async def test_missing_and_inaccessible_resources_use_registered_404_handlers(self) -> None:
        for route in self.routes():
            errors: list[Exception] = [
                WorkoutExerciseNotFoundError.not_found(ENTRY_ID),
                WorkoutNotFoundError.not_accessible(WORKOUT_ID),
            ]
            if route.service_method in ("get_by_id", "update", "delete"):
                errors.append(SetEntryNotFoundError.not_found(SET_ENTRY_ID))
            for error in errors:
                with self.subTest(method=route.method, error=type(error).__name__):
                    self.service.reset_mock(side_effect=True)
                    getattr(self.service, route.service_method).side_effect = error
                    response = await request(app, route.path, route.method, route.payload)
                    self.assertEqual(response.status, 404)
                    self.assertEqual(response.payload, {"detail": str(error)})
                    self.assertNotIn("www-authenticate", response.headers)

    async def test_ordering_and_parent_mismatch_errors_return_400(self) -> None:
        routes = self.routes()
        cases = (
            (routes[0], SetEntryValidationError.invalid_set_number(5, 3)),
            (routes[3], SetEntryValidationError.invalid_set_number(4, 3)),
            (routes[3], SetEntryValidationError.identical_set_number(3, 3)),
            (routes[3], WorkoutExerciseValidationError.mismatched_ids(ENTRY_ID, 99)),
            (routes[4], WorkoutExerciseValidationError.mismatched_ids(ENTRY_ID, 99)),
        )
        for route, error in cases:
            with self.subTest(method=route.method, error=str(error)):
                self.service.reset_mock(side_effect=True)
                getattr(self.service, route.service_method).side_effect = error
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 400)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_persistence_and_unexpected_failures_are_sanitized_on_every_endpoint(self) -> None:
        errors = (
            (DatabaseError("private database details"), "Database operation failed."),
            (SetEntryRepositoryError("private SQL"), "Database operation failed."),
            (SetEntryRowError("private row"), "Database operation failed."),
            (RuntimeError("private failure"), "Internal server error."),
        )
        for route in self.routes():
            for error, detail in errors:
                with (
                    self.subTest(method=route.method, error=type(error).__name__),
                    patch("core.exception_handlers.logger"),
                ):
                    self.service.reset_mock(side_effect=True)
                    getattr(self.service, route.service_method).side_effect = error
                    response = await request(app, route.path, route.method, route.payload)
                    self.assertEqual(response.status, 500)
                    self.assertEqual(response.payload, {"detail": detail})
                    self.assertNotIn("private", str(response.payload))

    async def test_creation_and_deletion_failures_keep_safe_public_messages(self) -> None:
        for route, error in (
            (self.routes()[0], SetEntryCreationError.create_failed()),
            (self.routes()[4], SetEntryDeleteError.delete_failed(SET_ENTRY_ID)),
        ):
            with self.subTest(method=route.method), patch("core.exception_handlers.logger"):
                self.service.reset_mock(side_effect=True)
                getattr(self.service, route.service_method).side_effect = error
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_invalid_service_responses_return_sanitized_500(self) -> None:
        for route in self.routes()[:-1]:
            with self.subTest(method=route.method, path=route.path), patch("core.exception_handlers.logger"):
                self.service.reset_mock()
                getattr(self.service, route.service_method).return_value = None
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": "Internal server error."})

    async def test_openapi_exposes_documented_routes_with_correct_parameter_locations(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        for method, path, status_code in (
            ("post", "/sets/", "201"),
            ("get", "/sets/{set_entry_id}", "200"),
            ("get", "/sets/workout_exercise/{workout_exercise_id}", "200"),
            ("patch", "/sets/{set_entry_id}", "200"),
            ("delete", "/sets/{set_entry_id}", "204"),
        ):
            with self.subTest(method=method, path=path):
                operation = paths[path][method]
                self.assertTrue(operation["description"])
                self.assertIn("401", cast("str", operation["description"]))
                self.assertTrue(operation["security"])
                responses = cast("dict[str, dict[str, object]]", operation["responses"])
                self.assertIn(status_code, responses)
                self.assertIn("422", responses)
                if status_code == "204":
                    self.assertNotIn("content", responses[status_code])
                parameters = cast("list[dict[str, object]]", operation.get("parameters", []))
                expected: dict[str, str] = (
                    {}
                    if method == "post"
                    else {"workout_exercise_id" if "workout_exercise/" in path else "set_entry_id": "path"}
                )
                if method in ("patch", "delete"):
                    expected["workout_exercise_id"] = "query"
                self.assertEqual({parameter["name"]: parameter["in"] for parameter in parameters}, expected)
                for parameter in parameters:
                    self.assertTrue(parameter["required"])
                    self.assertEqual(cast("dict[str, object]", parameter["schema"])["exclusiveMinimum"], 0)
                if method in ("post", "patch"):
                    self.assertTrue(cast("dict[str, object]", operation["requestBody"])["required"])

    async def test_service_provider_resolves_repositories_and_unit_of_work_for_creation(self) -> None:
        del app.dependency_overrides[get_set_entry_service]
        sets = create_autospec(SetEntryRepositoryPort, instance=True, spec_set=True)
        exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        tx = create_autospec(UnitOfWorkSetEntryRepositoryPort, instance=True, spec_set=True)
        exercises.get_by_id.return_value = entry()
        workouts.get_by_user_and_id.return_value = workout()
        uow.__enter__.return_value = uow
        uow.__exit__.return_value = None
        uow.set_entry = tx
        tx.lock_for_workout_exercise.return_value = True
        tx.list_by_workout_exercise.return_value = []
        tx.create.return_value = self.record
        app.dependency_overrides.update(
            {
                get_set_entry_repository: lambda: sets,
                get_workout_exercise_repository: lambda: exercises,
                get_workout_repository: lambda: workouts,
                get_unit_of_work: lambda: uow,
            }
        )
        response = await request(app, "/sets/", "POST", self.create_payload())
        self.assertEqual(response.status, 201)
        exercises.get_by_id.assert_called_once_with(ENTRY_ID)
        workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
        tx.lock_for_workout_exercise.assert_called_once_with(ENTRY_ID)
        tx.create.assert_called_once_with(SetEntryCreate.model_validate(self.create_payload()))
        uow.commit.assert_called_once_with()
        sets.create.assert_not_called()

    async def test_real_service_rejects_foreign_workouts_before_writes_or_parent_mismatch_errors(self) -> None:
        del app.dependency_overrides[get_set_entry_service]
        sets = create_autospec(SetEntryRepositoryPort, instance=True, spec_set=True)
        exercises = create_autospec(WorkoutExerciseRepositoryPort, instance=True, spec_set=True)
        workouts = create_autospec(WorkoutRepositoryPort, instance=True, spec_set=True)
        uow = create_autospec(UnitOfWorkPort, instance=True, spec_set=True)
        sets.get_by_id.return_value = self.record
        exercises.get_by_id.return_value = entry()
        workouts.get_by_user_and_id.return_value = None
        app.dependency_overrides.update(
            {
                get_set_entry_repository: lambda: sets,
                get_workout_exercise_repository: lambda: exercises,
                get_workout_repository: lambda: workouts,
                get_unit_of_work: lambda: uow,
            }
        )
        for route in self.routes():
            with self.subTest(method=route.method, path=route.path), patch("services.ownership.logger"):
                workouts.reset_mock()
                # An incorrect parent must not reveal a mismatch before ownership.
                path = route.path.replace(f"workout_exercise_id={ENTRY_ID}", "workout_exercise_id=999")
                response = await request(app, path, route.method, route.payload)
                self.assertEqual(response.status, 404)
                self.assertEqual(
                    response.payload, {"detail": str(WorkoutNotFoundError.not_accessible(WORKOUT_ID))}
                )
                workouts.get_by_user_and_id.assert_called_once_with(USER_ID, WORKOUT_ID)
                self.assertEqual(uow.mock_calls, [])
                sets.create.assert_not_called()
                sets.update_in_workout_exercise.assert_not_called()
                sets.delete_in_workout_exercise.assert_not_called()
                sets.list_by_workout_exercise.assert_not_called()
