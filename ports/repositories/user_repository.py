"""Repository contract for User."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from schemas.user_schema import UserCreate, UserInternal


class UserRepositoryPort(Protocol):
    """Persistence operations required by application consumers.

    Implementations preserve the documented ownership and filtering semantics
    and use the existing repository errors for persistence failures.
    """

    def create(self, user_data: UserCreate, password_hash: str) -> UserInternal:
        """Create a new user account."""
        ...

    def username_exists(self, username: str) -> bool:
        """Check whether a username already exists."""
        ...

    def email_exists(self, email: str) -> bool:
        """Check whether an email address already exists."""
        ...

    def get_by_id(self, user_id: int) -> UserInternal | None:
        """Retrieve a user by database ID."""
        ...

    def get_by_email(self, email: str) -> UserInternal | None:
        """Retrieve a user by email address."""
        ...

    def update(self, user_id: int, **updates: object) -> UserInternal | None:
        """Patch-update allowed profile fields (whitelist-enforced)."""
        ...

    def set_profile_picture_url(self, user_id: int, profile_picture_url: str | None) -> UserInternal | None:
        """Set or clear the profile picture URL for a user."""
        ...

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update the stored password hash and revoke existing tokens."""
        ...

    def delete(self, user_id: int) -> bool:
        """Delete a user by ID."""
        ...
