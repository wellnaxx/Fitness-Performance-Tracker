"""HTTP error contracts tested through FastAPI's ASGI application."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException

from auth.jwt_handler import TokenPayload
from core.errors.base import AppError, RepositoryError, RowValidationError
from core.errors.database import DatabaseError
from core.errors.exercise import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
)
from core.errors.goals import UserGoalCreationError, UserGoalNotFoundError, UserGoalValidationError
from core.errors.meal import MealCreationError, MealDeleteError, MealNotFoundError, MealUpdateError
from core.errors.user import (
    EmailAlreadyExistsError,
    IdenticalPasswordsError,
    IncorrectOldPasswordError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserCreationError,
    UserDeleteError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from core.errors.validation import InputValidationError
from core.errors.workout import (
    WorkoutCreationError,
    WorkoutDeleteError,
    WorkoutNotFoundError,
    WorkoutUpdateError,
)
from core.errors.workout_exercise import (
    WorkoutExerciseCreationError,
    WorkoutExerciseDeleteError,
    WorkoutExerciseNotFoundError,
    WorkoutExerciseUpdateError,
    WorkoutExerciseValidationError,
)
from core.exception_handlers import register_exception_handlers
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_exercise_service,
    get_meal_service,
    get_user_goals_service,
    get_user_repository,
    get_user_service,
    get_workout_exercise_service,
    get_workout_service,
)
from main import app
from repositories.user_repository import UserRepository
from schemas.user_schema import UserInternal
from services.user_service import UserService

if TYPE_CHECKING:
    from starlette.types import Message, Scope


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    payload: object


async def request(
    application: FastAPI,
    path: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    """Exercise the ASGI stack without a network server or extra HTTP client dependency."""
    url = urlsplit(path)
    body = json.dumps(payload).encode() if payload is not None else b""
    request_headers = {"content-type": "application/json", **(headers or {})}
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "path": url.path,
        "raw_path": url.path.encode(),
        "root_path": "",
        "query_string": url.query.encode(),
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
        "headers": [(key.lower().encode(), value.encode()) for key, value in request_headers.items()],
    }
    response = HttpResponse(0, {}, None)
    chunks = bytearray()
    received = False

    async def receive() -> Message:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            response.status = message["status"]
            response.headers.update((key.decode(), value.decode()) for key, value in message["headers"])
        elif message["type"] == "http.response.body":
            chunks.extend(message.get("body", b""))

    try:
        await application(scope, receive, send)
    except Exception:
        # Starlette re-raises unexpected exceptions after sending the handled 500.
        if response.status != 500 or not chunks:
            raise
    response.payload = json.loads(chunks) if chunks else None
    return response


class ExceptionHandlerTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.error: Exception = RuntimeError()

        async def fail() -> None:
            raise self.error

        self.app.add_api_route("/error", fail, methods=["GET"])

    async def test_existing_service_status_codes_and_messages_are_preserved(self) -> None:
        cases: tuple[tuple[Exception, int], ...] = (
            (InvalidCredentialsError.invalid_login(), 401),
            (InvalidAccessTokenError.revoked(), 401),
            (InvalidRefreshTokenError.invalid_or_expired(), 401),
            (UsernameAlreadyExistsError.already_taken("tester"), 409),
            (EmailAlreadyExistsError.already_registered("test@example.com"), 409),
            (ExerciseNameAlreadyExistsError.already_exists("Squat"), 409),
            (UserNotFoundError.not_found(7), 404),
            (UserGoalNotFoundError.not_found(7), 404),
            (ExerciseNotFoundError.not_found(7), 404),
            (WorkoutNotFoundError.not_found(7), 404),
            (WorkoutExerciseNotFoundError.not_found(7), 404),
            (MealNotFoundError.not_found(7), 404),
            (IncorrectOldPasswordError.incorrect(), 400),
            (IdenticalPasswordsError.must_differ(), 400),
            (UserDeleteError.blocked_by_related_records(), 400),
            (UserGoalValidationError.end_date_before_start_date(), 400),
            (ExerciseUpdateError.duplicate_name("Squat"), 400),
            (ExerciseDeleteError.custom_only(), 400),
            (WorkoutExerciseValidationError.invalid_create_order_index(9), 400),
            (InputValidationError.invalid_meal_type({"lunch"}), 422),
            (UserCreationError.create_failed(), 500),
            (UserGoalCreationError.create_failed(), 500),
            (ExerciseCreationError.create_failed(), 500),
            (WorkoutCreationError.create_failed(), 500),
            (WorkoutUpdateError.update_failed(7), 500),
            (WorkoutDeleteError.delete_failed(7), 500),
            (WorkoutExerciseCreationError.create_failed(), 500),
            (WorkoutExerciseUpdateError.update_failed(7), 500),
            (WorkoutExerciseDeleteError.delete_failed(7), 500),
            (MealCreationError.create_failed(), 500),
            (MealUpdateError.update_failed(7), 500),
            (MealDeleteError.delete_failed(7), 500),
        )
        for error, expected_status in cases:
            with self.subTest(error=type(error).__name__), patch("core.exception_handlers.logger") as logger:
                self.error = error
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": str(error)})
                self.assertEqual(
                    response.headers.get("www-authenticate"), "Bearer" if expected_status == 401 else None
                )
                self.assertEqual(logger.error.call_count, int(expected_status == 500))

    async def test_internal_errors_are_sanitized_and_logged_with_exception_info(self) -> None:
        cases: tuple[tuple[Exception, str], ...] = (
            (DatabaseError("private connection details"), "Database operation failed."),
            (RepositoryError("private query details"), "Database operation failed."),
            (RowValidationError("private row details"), "Database operation failed."),
            (UserCreationError.create_failed(RuntimeError("private insert details")), "Failed to create user."),
            (AppError("private application details"), "Internal server error."),
            (ValueError("private programming error"), "Internal server error."),
            (RuntimeError("private runtime details"), "Internal server error."),
        )
        for error, public_detail in cases:
            with self.subTest(error=type(error).__name__), patch("core.exception_handlers.logger") as logger:
                self.error = error
                response = await request(self.app, "/error")
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": public_detail})
                logger.error.assert_called_once()
                self.assertIs(logger.error.call_args.kwargs["exc_info"][1], error)

    async def test_subclasses_use_the_nearest_registered_parent(self) -> None:
        class SpecificMealNotFoundError(MealNotFoundError):
            pass

        self.error = SpecificMealNotFoundError.not_found(7)
        response = await request(self.app, "/error")
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload, {"detail": str(self.error)})

    async def test_framework_http_exceptions_keep_their_detail_and_headers(self) -> None:
        self.error = HTTPException(429, detail={"message": "Slow down"}, headers={"Retry-After": "10"})
        response = await request(self.app, "/error")
        self.assertEqual(response.status, 429)
        self.assertEqual(response.payload, {"detail": {"message": "Slow down"}})
        self.assertEqual(response.headers["retry-after"], "10")


class ApplicationErrorTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = UserInternal.model_construct(id=7, token_version=2)
        self.service = Mock()
        overrides = patch.dict(
            app.dependency_overrides,
            {
                get_current_user: lambda: self.user,
                get_user_service: lambda: self.service,
                get_user_goals_service: lambda: self.service,
                get_exercise_service: lambda: self.service,
                get_workout_service: lambda: self.service,
                get_workout_exercise_service: lambda: self.service,
                get_meal_service: lambda: self.service,
            },
            clear=True,
        )
        overrides.start()
        self.addCleanup(overrides.stop)

    async def test_each_router_uses_global_not_found_handling(self) -> None:
        cases: tuple[tuple[str, str, Exception], ...] = (
            ("/goals/17", "get_goal_by_id", UserGoalNotFoundError.not_found(17)),
            ("/exercises/17", "get_visible_by_user", ExerciseNotFoundError.not_found(17)),
            ("/workouts/17", "get_visible_by_user", WorkoutNotFoundError.not_found(17)),
            ("/workouts/11/exercises/17", "get_workout_exercise", WorkoutExerciseNotFoundError.not_found(17)),
            ("/meals/17", "get_visible_by_user", MealNotFoundError.not_found(17)),
        )
        for path, method, error in cases:
            with self.subTest(path=path):
                getattr(self.service, method).side_effect = error
                response = await request(app, path)
                self.assertEqual(response.status, 404)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_profile_missing_user_is_404(self) -> None:
        self.service.update_my_profile.side_effect = UserNotFoundError.not_found(7)
        response = await request(app, "/users/me", "PATCH", {"first_name": "Test"})
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload, {"detail": "User with ID 7 not found."})

    async def test_refresh_deleted_user_remains_401_with_bearer_header(self) -> None:
        repo = Mock(spec=UserRepository)
        repo.get_by_id.return_value = None
        service = UserService(repo)
        app.dependency_overrides[get_user_service] = lambda: service
        token = TokenPayload(
            sub="7", iat=0, exp=1, jti="test", type="refresh", username="tester", token_version=2
        )
        with patch("services.user_service.decode_token", return_value=token):
            response = await request(app, "/users/refresh", "POST", {"refresh_token": "test-token"})
        self.assertEqual(response.status, 401)
        self.assertEqual(response.payload, {"detail": "User with ID 7 not found."})
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    async def test_missing_current_goal_uses_existing_message(self) -> None:
        self.service.get_current_goal.return_value = None
        response = await request(app, "/goals/current")
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload, {"detail": "No active goal found for the user."})

    async def test_login_failure_retains_bearer_header(self) -> None:
        self.service.login_user.side_effect = InvalidCredentialsError.invalid_login()
        response = await request(
            app, "/users/login", "POST", {"email": "test@example.com", "password": "wrong"}
        )
        self.assertEqual(response.status, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    async def test_invalid_meal_filter_is_422_and_does_not_call_service(self) -> None:
        response = await request(app, "/meals/?meal_type=invalid")
        self.assertEqual(response.status, 422)
        self.service.list_visible_by_user.assert_not_called()

    async def test_request_validation_still_uses_fastapi_response_shape(self) -> None:
        response = await request(app, "/users/login", "POST", {})
        self.assertEqual(response.status, 422)
        self.assertIsInstance(response.payload, dict)
        payload = cast("dict[str, object]", response.payload)
        self.assertIsInstance(payload["detail"], list)
        self.service.login_user.assert_not_called()

    async def test_successful_delete_remains_an_empty_204(self) -> None:
        response = await request(app, "/users/me", "DELETE")
        self.assertEqual(response.status, 204)
        self.assertIsNone(response.payload)
        self.service.delete_my_account.assert_called_once_with(self.user)

    async def test_access_token_failures_are_401_with_bearer_header(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = Mock(spec=UserRepository)
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(
            sub="7", iat=0, exp=1, jti="test", type="access", username="tester", token_version=2
        )
        cases: tuple[tuple[TokenPayload | None, UserInternal | None, str], ...] = (
            (None, self.user, "Invalid or expired token."),
            (
                TokenPayload(
                    sub="", iat=0, exp=1, jti="test", type="access", username="tester", token_version=2
                ),
                self.user,
                "Invalid token payload: missing subject (sub) claim.",
            ),
            (
                TokenPayload(
                    sub="bad", iat=0, exp=1, jti="test", type="access", username="tester", token_version=2
                ),
                self.user,
                "Invalid token payload: subject must be a valid user ID.",
            ),
            (token, None, "User not found. Account may have been deleted."),
            (token, UserInternal.model_construct(id=7, token_version=3), "Token revoked. Please log in again."),
        )
        for decoded, user, detail in cases:
            with self.subTest(detail=detail), patch("dependencies.auth.decode_token", return_value=decoded):
                repo.get_by_id.return_value = user
                response = await request(app, "/users/me", headers={"Authorization": "Bearer test-token"})
                self.assertEqual(response.status, 401)
                self.assertEqual(response.payload, {"detail": detail})
                self.assertEqual(response.headers["www-authenticate"], "Bearer")

    async def test_missing_authorization_keeps_framework_401(self) -> None:
        del app.dependency_overrides[get_current_user]
        response = await request(app, "/users/me")
        self.assertEqual(response.status, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")
