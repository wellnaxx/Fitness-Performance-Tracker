class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class AppError(RuntimeError):
    """Base application error."""


class ServiceError(AppError):
    """Base service-layer error."""


class UserServiceError(ServiceError):
    """Base user-related service error."""


class UserGoalsError(ServiceError):
    """Base error for user goals operations."""


class ExerciseServiceError(ServiceError):
    """Base error for exercise-related operations."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when username already exists."""


class EmailAlreadyExistsError(UserServiceError):
    """Raised when email already exists."""


class InvalidCredentialsError(UserServiceError):
    """Raised when login credentials are invalid."""


class IdenticalPasswordsError(UserServiceError):
    """Raised when new password equals old password."""


class InvalidRefreshTokenError(UserServiceError):
    """Raised when refresh token is invalid."""


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""


class UserCreationError(UserServiceError):
    """Raised when user creation fails."""


class IncorrectOldPasswordError(UserServiceError):
    """Raised when old password is incorrect."""


class UserDeleteError(UserServiceError):
    """Raised when user deletion fails."""


class UserGoalNotFoundError(UserGoalsError):
    """Raised when a goal is not found or does not belong to the user."""


class UserGoalCreationError(UserGoalsError):
    """Raised when creating a user goal fails."""


class ExerciseNotFoundError(ExerciseServiceError):
    """Raised when an exercise is not found."""


class ExerciseCreationError(ExerciseServiceError):
    """Raised when creating an exercise fails."""


class ExerciseNameAlreadyExistsError(ExerciseServiceError):
    """Raised when an exercise with the same name already exists for the user."""


class ExerciseUpdateError(ExerciseServiceError):
    """Raised when updating an exercise fails."""


class ExerciseDeleteError(ExerciseServiceError):
    """Raised when deleting an exercise fails."""
