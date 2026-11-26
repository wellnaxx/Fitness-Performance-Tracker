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
        """Create a new user account.

        Args:
            user_data: User creation payload.
            password_hash: Pre-hashed password to persist.

        Returns:
            The newly created internal user model.

        Raises:
            UserRepositoryError: If the inserted user cannot be retrieved afterwards.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def username_exists(self, username: str) -> bool:
        """Check whether a username already exists.

        Args:
            username: Username to look up.

        Returns:
            True if a matching user exists, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...

    def email_exists(self, email: str) -> bool:
        """Check whether an email address already exists.

        Args:
            email: Email address to look up.

        Returns:
            True if a matching user exists, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...

    def get_by_id(self, user_id: int) -> UserInternal | None:
        """Retrieve a user by database ID.

        Args:
            user_id: User ID.

        Returns:
            The user if found, otherwise None.

        This lookup does not authorize access; services must verify ownership or visibility.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def get_by_email(self, email: str) -> UserInternal | None:
        """Retrieve a user by email address.

        Args:
            email: Email value.

        Returns:
            The user if found, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update(self, user_id: int, **updates: object) -> UserInternal | None:
        """Patch-update allowed profile fields (whitelist-enforced).

        Unknown fields raise UserRepositoryError. None values are skipped.

        Args:
            user_id: User ID whose profile is being changed; caller must verify access.
            updates: Allowed changes; omitted and None-valued fields preserve stored values.

        Returns:
            The updated user, current values for an empty or all-None update, or None
            if the user is missing or disappears before readback.

        Raises:
            UserRepositoryError: If unsupported profile fields are supplied.
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def set_profile_picture_url(self, user_id: int, profile_picture_url: str | None) -> UserInternal | None:
        """Set or clear the profile picture URL for a user.

        Args:
            user_id: User ID.
            profile_picture_url: New URL value, or None to clear it.

        Returns:
            The updated user if found, otherwise None.

        Raises:
            DatabaseError: If the database operation fails.
            RowValidationError: If a stored row has invalid field types.
            ValidationError: If a stored row violates the public schema.
        """
        ...

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update the stored password hash and revoke existing tokens.

        Args:
            user_id: User ID.
            new_password_hash: New password hash.

        Returns:
            True if a row was updated, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...

    def delete(self, user_id: int) -> bool:
        """Delete a user by ID.

        Args:
            user_id: User ID.

        Returns:
            True if a row was deleted, otherwise False.

        Raises:
            DatabaseError: If the database operation fails.
        """
        ...
