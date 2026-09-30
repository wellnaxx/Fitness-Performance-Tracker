"""Application-wide translation of exceptions into HTTP responses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import status
from fastapi.responses import JSONResponse

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

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

# None means the exception's message is intended for the client. Explicit text
# hides internal details for persistence failures and other unexpected errors.
_ERROR_RESPONSES: dict[type[Exception], tuple[int, str | None]] = {
    InvalidCredentialsError: (status.HTTP_401_UNAUTHORIZED, None),
    InvalidAccessTokenError: (status.HTTP_401_UNAUTHORIZED, None),
    InvalidRefreshTokenError: (status.HTTP_401_UNAUTHORIZED, None),
    UsernameAlreadyExistsError: (status.HTTP_409_CONFLICT, None),
    EmailAlreadyExistsError: (status.HTTP_409_CONFLICT, None),
    ExerciseNameAlreadyExistsError: (status.HTTP_409_CONFLICT, None),
    UserNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    UserGoalNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    ExerciseNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    WorkoutNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    WorkoutExerciseNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    MealNotFoundError: (status.HTTP_404_NOT_FOUND, None),
    IncorrectOldPasswordError: (status.HTTP_400_BAD_REQUEST, None),
    IdenticalPasswordsError: (status.HTTP_400_BAD_REQUEST, None),
    UserDeleteError: (status.HTTP_400_BAD_REQUEST, None),
    UserGoalValidationError: (status.HTTP_400_BAD_REQUEST, None),
    ExerciseUpdateError: (status.HTTP_400_BAD_REQUEST, None),
    ExerciseDeleteError: (status.HTTP_400_BAD_REQUEST, None),
    WorkoutExerciseValidationError: (status.HTTP_400_BAD_REQUEST, None),
    InputValidationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
    UserCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create user."),
    UserGoalCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    ExerciseCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutUpdateError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutDeleteError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutExerciseCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutExerciseUpdateError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    WorkoutExerciseDeleteError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    MealCreationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    MealUpdateError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    MealDeleteError: (status.HTTP_500_INTERNAL_SERVER_ERROR, None),
    DatabaseError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database operation failed."),
    RepositoryError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database operation failed."),
    RowValidationError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database operation failed."),
    AppError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error."),
    Exception: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error."),
}


async def application_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return the most specific error response and log server-side failures."""
    status_code, public_detail = _ERROR_RESPONSES[Exception]
    for error_type in type(exc).__mro__:
        if error_type in _ERROR_RESPONSES:
            status_code, public_detail = _ERROR_RESPONSES[error_type]
            break

    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Request failed: %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc) if public_detail is None else public_detail},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install application handlers alongside FastAPI's built-in HTTP and validation handlers."""
    for error_type in _ERROR_RESPONSES:
        app.add_exception_handler(error_type, application_exception_handler)
