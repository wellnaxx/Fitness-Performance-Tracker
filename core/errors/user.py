from __future__ import annotations

from core.errors.base import ServiceError


class UserServiceError(ServiceError):
    """Base user-related service error."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when username already exists."""

    @classmethod
    def already_taken(cls, username: str) -> UsernameAlreadyExistsError:
        return cls(f"Username '{username}' already taken! Please choose a different username.")


class EmailAlreadyExistsError(UserServiceError):
    """Raised when email already exists."""

    @classmethod
    def already_registered(cls, email: str) -> EmailAlreadyExistsError:
        return cls(f"Email '{email}' already registered! Please use a different email or login.")

    @classmethod
    def already_in_use(cls, email: str) -> EmailAlreadyExistsError:
        return cls(f"Email '{email}' already in use by another account!")


class InvalidCredentialsError(UserServiceError):
    """Raised when login credentials are invalid."""

    @classmethod
    def invalid_login(cls) -> InvalidCredentialsError:
        return cls("Invalid email or password.")


class IdenticalPasswordsError(UserServiceError):
    """Raised when new password equals old password."""

    @classmethod
    def must_differ(cls) -> IdenticalPasswordsError:
        return cls("New password must be different from current password.")


class InvalidRefreshTokenError(UserServiceError):
    """Raised when refresh token is invalid."""

    @classmethod
    def invalid_or_expired(cls) -> InvalidRefreshTokenError:
        return cls("Invalid or expired refresh token.")

    @classmethod
    def invalid_payload(cls) -> InvalidRefreshTokenError:
        return cls("Invalid refresh token payload.")

    @classmethod
    def revoked(cls) -> InvalidRefreshTokenError:
        return cls("Refresh token has been revoked.")


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""

    @classmethod
    def not_found(cls, user_id: int) -> UserNotFoundError:
        return cls(f"User with ID {user_id} not found.")


class UserCreationError(UserServiceError):
    """Raised when user creation fails."""

    @classmethod
    def create_failed(cls, exc: Exception | None = None) -> UserCreationError:
        if exc is None:
            return cls("Failed to create user.")
        return cls(str(exc))


class IncorrectOldPasswordError(UserServiceError):
    """Raised when old password is incorrect."""

    @classmethod
    def incorrect(cls) -> IncorrectOldPasswordError:
        return cls("Current password is incorrect!")


class UserDeleteError(UserServiceError):
    """Raised when user deletion fails."""

    @classmethod
    def blocked_by_related_records(cls) -> UserDeleteError:
        return cls("Cannot delete account. You may have workouts or exercises that need to be removed first.")
