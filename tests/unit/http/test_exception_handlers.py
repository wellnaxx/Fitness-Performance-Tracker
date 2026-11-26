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
from core.errors.body_measurement import (
    BodyMeasurementCreationError,
    BodyMeasurementDateConflictError,
    BodyMeasurementNotFoundError,
    BodyMeasurementUpdateError,
)
from core.errors.body_weight_entry import (
    BodyWeightEntryCreationError,
    BodyWeightEntryDateConflictError,
    BodyWeightEntryNotFoundError,
    BodyWeightEntryUpdateError,
)
from core.errors.database import DatabaseError
from core.errors.exercise import (
    ExerciseCreationError,
    ExerciseDeleteError,
    ExerciseNameAlreadyExistsError,
    ExerciseNotFoundError,
    ExerciseUpdateError,
    ExerciseValidationError,
)
from core.errors.goals import UserGoalCreationError, UserGoalNotFoundError, UserGoalValidationError
from core.errors.meal import MealCreationError, MealDeleteError, MealNotFoundError, MealUpdateError
from core.errors.meal_item import (
    MealItemCreationError,
    MealItemDeleteError,
    MealItemNotFoundError,
    MealItemUpdateError,
)
from core.errors.progress_photo import (
    ProgressPhotoCreationError,
    ProgressPhotoDeleteError,
    ProgressPhotoNotFoundError,
    ProgressPhotoUpdateError,
)
from core.errors.repository import BodyWeightEntryDateConflictRepositoryError
from core.errors.set_entry import (
    SetEntryCreationError,
    SetEntryDeleteError,
    SetEntryNotFoundError,
    SetEntryValidationError,
)
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
from ports.repositories.user_repository import UserRepositoryPort
from schemas.user_schema import UserInternal
from services.user_service import UserService
from tests.fixtures import MEASUREMENT_ID, TODAY, USER_ID

if TYPE_CHECKING:
    from starlette.types import Message, Scope


@dataclass
class HttpResponse:
    """Captured status, headers, decoded JSON, and exact ASGI response bytes."""

    status: int
    headers: dict[str, str]
    payload: object
    body: bytes = b""


async def request(
    application: FastAPI,
    path: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    *,
    raw_body: bytes | None = None,
) -> HttpResponse:
    """Exercise ASGI without a server or HTTP client; raw_body overrides JSON encoding.

    Use raw_body for malformed JSON and non-object bodies. The returned body
    preserves the exact bytes, including empty responses such as HTTP 204.
    """
    url = urlsplit(path)
    body = raw_body if raw_body is not None else json.dumps(payload).encode() if payload is not None else b""
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
    response.body = bytes(chunks)
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
            (BodyMeasurementDateConflictError.already_exists(TODAY), 409),
            (BodyMeasurementNotFoundError.not_found(MEASUREMENT_ID), 404),
            (BodyMeasurementNotFoundError.not_found_by_date(TODAY), 404),
            (BodyMeasurementNotFoundError.no_entries(USER_ID), 404),
            (BodyMeasurementNotFoundError.not_accessible(MEASUREMENT_ID), 404),
            (UserNotFoundError.not_found(7), 404),
            (UserGoalNotFoundError.not_found(7), 404),
            (ExerciseNotFoundError.not_found(7), 404),
            (WorkoutNotFoundError.not_found(7), 404),
            (WorkoutExerciseNotFoundError.not_found(7), 404),
            (MealNotFoundError.not_found(7), 404),
            (SetEntryNotFoundError.not_found(31), 404),
            (IncorrectOldPasswordError.incorrect(), 400),
            (IdenticalPasswordsError.must_differ(), 400),
            (UserDeleteError.blocked_by_related_records(), 400),
            (UserGoalValidationError.end_date_before_start_date(), 400),
            (ExerciseValidationError.custom_only(), 400),
            (WorkoutExerciseValidationError.invalid_create_order_index(9), 400),
            (WorkoutExerciseValidationError.mismatched_ids(17, 99), 400),
            (SetEntryValidationError.invalid_set_number(7, 5), 400),
            (SetEntryValidationError.identical_set_number(3, 3), 400),
            (InputValidationError.invalid_meal_type({"lunch"}), 422),
            (UserCreationError.create_failed(), 500),
            (UserGoalCreationError.create_failed(), 500),
            (ExerciseCreationError.create_failed(), 500),
            (ExerciseUpdateError.update_failed(), 500),
            (ExerciseDeleteError.delete_failed(13), 500),
            (WorkoutCreationError.create_failed(), 500),
            (WorkoutUpdateError.update_failed(7), 500),
            (WorkoutDeleteError.delete_failed(7), 500),
            (WorkoutExerciseCreationError.create_failed(), 500),
            (WorkoutExerciseUpdateError.update_failed(7), 500),
            (WorkoutExerciseDeleteError.delete_failed(7), 500),
            (MealCreationError.create_failed(), 500),
            (MealUpdateError.update_failed(7), 500),
            (MealDeleteError.delete_failed(7), 500),
            (SetEntryCreationError.create_failed(), 500),
            (SetEntryDeleteError.delete_failed(31), 500),
            (BodyMeasurementCreationError.create_failed(), 500),
            (BodyMeasurementUpdateError.update_failed(MEASUREMENT_ID), 500),
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

    async def test_meal_item_errors_have_expected_messages_and_http_statuses(self) -> None:
        cases: tuple[tuple[Exception, int, str], ...] = (
            (MealItemCreationError.create_failed(), 500, "Failed to create meal item."),
            (
                MealItemNotFoundError.not_found(17),
                404,
                "Meal item with ID 17 not found or does not belong to the user.",
            ),
            (
                MealItemNotFoundError.not_accessible(17),
                404,
                "Meal item with ID 17 not accessible or does not belong to the user.",
            ),
            (
                MealItemNotFoundError.not_in_meal(17, 11),
                404,
                "Meal item with ID 17 was not found in meal 11.",
            ),
            (MealItemUpdateError.update_failed(17), 500, "Failed to update meal item with ID 17."),
            (MealItemDeleteError.delete_failed(17), 500, "Failed to delete meal item with ID 17."),
        )
        for error, expected_status, expected_detail in cases:
            with (
                self.subTest(error=type(error).__name__, detail=expected_detail),
                patch("core.exception_handlers.logger") as logger,
            ):
                self.error = error
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": expected_detail})
                self.assertEqual(logger.error.call_count, int(expected_status == 500))

    async def test_progress_photo_errors_have_expected_messages_and_http_statuses(self) -> None:
        cases: tuple[tuple[Exception, int, str], ...] = (
            (ProgressPhotoCreationError.create_failed(), 500, "Failed to create progress photo."),
            (
                ProgressPhotoNotFoundError.not_found(47),
                404,
                "Progress photo with ID 47 not found or does not belong to the user.",
            ),
            (
                ProgressPhotoNotFoundError.not_accessible(47),
                404,
                "Progress photo with ID 47 not accessible or does not belong to the user.",
            ),
            (ProgressPhotoUpdateError.update_failed(47), 500, "Failed to update progress photo with ID 47."),
            (ProgressPhotoDeleteError.delete_failed(47), 500, "Failed to delete progress photo with ID 47."),
        )
        for error, expected_status, expected_detail in cases:
            with (
                self.subTest(error=type(error).__name__, detail=expected_detail),
                patch("core.exception_handlers.logger") as logger,
            ):
                self.error = error
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": expected_detail})
                self.assertEqual(logger.error.call_count, int(expected_status == 500))

    async def test_internal_errors_are_sanitized_and_logged_with_exception_info(self) -> None:
        cases: tuple[tuple[Exception, str], ...] = (
            (DatabaseError("private connection details"), "Database operation failed."),
            (RepositoryError("private query details"), "Database operation failed."),
            (RowValidationError("private row details"), "Database operation failed."),
            (UserCreationError("private insert details"), "Failed to create user."),
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

    async def test_wrapped_set_creation_failure_hides_repository_details(self) -> None:
        error = SetEntryCreationError.create_failed()
        error.__cause__ = RepositoryError("private SQL parameters")
        self.error = error
        with patch("core.exception_handlers.logger") as logger:
            response = await request(self.app, "/error")
        self.assertEqual(response.status, 500)
        self.assertEqual(response.payload, {"detail": "Failed to create set entry."})
        self.assertNotIn("private", str(response.payload))
        logger.error.assert_called_once()
        self.assertIs(logger.error.call_args.kwargs["exc_info"][1].__cause__, error.__cause__)

    async def test_body_measurement_failures_hide_causes_and_log_only_server_errors(self) -> None:
        for error, expected_status in (
            (BodyMeasurementCreationError.create_failed(), 500),
            (BodyMeasurementUpdateError.update_failed(MEASUREMENT_ID), 500),
            (BodyMeasurementDateConflictError.already_exists(TODAY), 409),
        ):
            error.__cause__ = RepositoryError("private SQL and measurements")
            self.error = error
            with self.subTest(error=type(error).__name__), patch("core.exception_handlers.logger") as logger:
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": str(error)})
                self.assertNotIn("private", str(response.payload))
                self.assertNotIn("www-authenticate", response.headers)
                self.assertEqual(logger.error.call_count, int(expected_status == 500))
                if expected_status == 500:
                    self.assertIs(logger.error.call_args.kwargs["exc_info"][1], error)

    async def test_body_weight_entry_errors_have_expected_statuses_and_public_messages(self) -> None:
        cases: tuple[tuple[Exception, int, str], ...] = (
            (BodyWeightEntryCreationError.create_failed(), 500, "Failed to create body weight entry."),
            (
                BodyWeightEntryUpdateError.update_failed(41),
                500,
                "Failed to update body weight entry with ID 41.",
            ),
            (
                BodyWeightEntryDateConflictError.already_exists(TODAY),
                409,
                f"A body weight entry already exists for {TODAY.isoformat()}.",
            ),
            (BodyWeightEntryNotFoundError.not_found(41), 404, "Body weight entry with ID 41 not found."),
            (
                BodyWeightEntryNotFoundError.not_found_by_date(TODAY),
                404,
                f"Body weight entry for {TODAY.isoformat()} not found.",
            ),
            (
                BodyWeightEntryNotFoundError.no_entries(USER_ID),
                404,
                f"User with ID {USER_ID} has no body weight entries.",
            ),
            (
                BodyWeightEntryNotFoundError.not_accessible(41),
                404,
                "Body weight entry with ID 41 not found or does not belong to the user.",
            ),
        )
        for error, expected_status, message in cases:
            self.error = error
            with (
                self.subTest(error=type(error).__name__, message=message),
                patch("core.exception_handlers.logger") as logger,
            ):
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": message})
                self.assertNotIn("www-authenticate", response.headers)
                self.assertEqual(logger.error.call_count, int(expected_status == 500))

    async def test_body_weight_entry_error_causes_stay_private(self) -> None:
        conflict = BodyWeightEntryDateConflictRepositoryError(TODAY)
        self.assertEqual(conflict.entry_date, TODAY)
        conflict.__cause__ = RuntimeError("private SQL parameters and body weight")
        cases: tuple[tuple[Exception, int, str], ...] = (
            (BodyWeightEntryCreationError.create_failed(), 500, "Failed to create body weight entry."),
            (
                BodyWeightEntryUpdateError.update_failed(41),
                500,
                "Failed to update body weight entry with ID 41.",
            ),
            (
                BodyWeightEntryDateConflictError.already_exists(TODAY),
                409,
                f"A body weight entry already exists for {TODAY.isoformat()}.",
            ),
            (conflict, 500, "Database operation failed."),
        )
        for error, expected_status, message in cases:
            if error is not conflict:
                error.__cause__ = conflict
            self.error = error
            with self.subTest(error=type(error).__name__), patch("core.exception_handlers.logger") as logger:
                response = await request(self.app, "/error")
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.payload, {"detail": message})
                self.assertNotIn("private", str(response.payload))
                self.assertEqual(logger.error.call_count, int(expected_status == 500))
                if expected_status == 500:
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
            ("/goals/17", "get_by_id", UserGoalNotFoundError.not_found(17)),
            ("/exercises/17", "get_by_id", ExerciseNotFoundError.not_found(17)),
            ("/workouts/17", "get_by_id", WorkoutNotFoundError.not_found(17)),
            ("/workouts/11/exercises/17", "get_by_id", WorkoutExerciseNotFoundError.not_found(17)),
            ("/meals/17", "get_by_id", MealNotFoundError.not_found(17)),
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
        repo = Mock(spec=UserRepositoryPort)
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
        self.service.get_current.return_value = None
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
        self.service.list_by_user.assert_not_called()

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
        repo = Mock(spec=UserRepositoryPort)
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
