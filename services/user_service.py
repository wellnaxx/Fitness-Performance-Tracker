"""
User Service - Business Logic Layer for User operations.

This module handles all business logic for user operations including:
- Registration and authentication
- Profile management
- Password changes
"""

import logging

from auth.hashing import hash_password, verify_password
from auth.jwt_handler import (
    TokenInput,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from core.errors.repository import UserRepositoryError
from core.errors.user import (
    EmailAlreadyExistsError,
    IdenticalPasswordsError,
    IncorrectOldPasswordError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserCreationError,
    UserDeleteError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from repositories.user_repository import UserRepository
from schemas.token_schema import RefreshRequest, TokenPairResponse
from schemas.user_schema import (
    ChangeUserPassword,
    UserCreate,
    UserInternal,
    UserLogin,
    UserProfile,
    UserUpdate,
)


class UserService:
    """
    Business logic for user operations.

    Responsibilities:
    - Validate business rules
    - Check permissions
    - Orchestrate repository calls
    - Transform between model types
    """

    def __init__(self, user_repo: UserRepository) -> None:
        """
        Initialize UserService with repository dependency.

        Args:
            user_repo: UserRepository instance for database operations
        """
        self.user_repo = user_repo
        self._log = logging.getLogger(__name__)

    def register_user(self, user_data: UserCreate) -> UserProfile:
        """
        Register a new user account.

        Business Rules:
        - Username must be unique
        - Email must be unique
        - Password must meet complexity requirements (validated by Pydantic)

        Args:
            user_data: User registration data from request

        Returns:
            UserProfile: Newly created user (public view)

        Raises:
            UsernameAlreadyExists
            EmailAlreadyExists
            UserNotFoundError: Database operation failed
        """
        if self.user_repo.username_exists(user_data.username):
            raise UsernameAlreadyExistsError.already_taken(username=user_data.username)

        if self.user_repo.email_exists(user_data.email):
            raise EmailAlreadyExistsError.already_registered(email=user_data.email)

        password_hash = hash_password(user_data.password)

        try:
            user_internal = self.user_repo.create(user_data, password_hash)
        except UserRepositoryError as exc:
            raise UserCreationError.create_failed(exc) from exc

        self._log.info(
            "User registered: id=%d username=%s",
            user_internal.id,
            user_internal.username,
        )
        return UserProfile(**user_internal.model_dump())

    def login_user(self, data: UserLogin) -> TokenPairResponse:
        """
        Authenticate a user and return a new access/refresh token pair.

        Business Rules:
        - Email must exist
        - Password must match the stored password hash
        - Error message should not reveal whether email or password was wrong

        Args:
            data: Login credentials

        Returns:
            TokenPairResponse: New JWT access/refresh token pair

        Raises:
            InvalidCredentialsError: If email does not exist or password is incorrect
        """
        user = self.user_repo.get_by_email(data.email)

        if not user or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError.invalid_login()

        token_data: TokenInput = {
            "user_id": user.id,
            "username": user.username,
            "token_version": user.token_version,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        self._log.info("User logged in: id=%d username=%s", user.id, user.username)

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def get_my_profile(self, current_user: UserInternal) -> UserProfile:
        """
        Get authenticated user's own profile.

        Shows information that the user themselves should see.

        Args:
            current_user: Currently authenticated user

        Returns:
            UserProfile: User's profile data
        """
        return UserProfile(**current_user.model_dump())

    def update_my_profile(self, current_user: UserInternal, updates: UserUpdate) -> UserProfile:
        """
        Update authenticated user's own profile.

        Business Rules:
        - Email must remain unique if changed

        Args:
            current_user: Currently authenticated user
            updates: Fields to update

        Returns:
            UserProfile: Updated user profile

        Raises:
            EmailAlreadyExistsError
            UserNotFoundError (shouldn't happen)
        """

        if updates.email and updates.email != current_user.email and self.user_repo.email_exists(updates.email):
            raise EmailAlreadyExistsError.already_in_use(email=updates.email)

        update_dict = updates.model_dump(exclude_none=True)

        updated_user = self.user_repo.update(current_user.id, **update_dict)

        if not updated_user:
            raise UserNotFoundError.not_found(user_id=current_user.id)

        return UserProfile(**updated_user.model_dump())

    def change_password(self, current_user: UserInternal, data: ChangeUserPassword) -> None:
        """
        Change user's password.

        Business Rules:
        - Must provide correct old password
        - New password must meet complexity requirements

        Args:
            current_user: Currently authenticated user
            old_password: Current password (for verification)
            new_password: New password to set

        Returns:
            True if password changed successfully

        Raises:
            IncorrectOldPasswordError
            IdenticalPasswordsError
            UserNotFoundError: User not found (shouldn't happen)
        """

        if not verify_password(data.old_password, current_user.password_hash):
            # Idempotent behavior: if the user already has the requested new password,
            # treat this as success (useful for retries / reruns).
            if verify_password(data.new_password, current_user.password_hash):
                return
            raise IncorrectOldPasswordError.incorrect()

        if data.new_password == data.old_password:
            raise IdenticalPasswordsError.must_differ()

        new_password_hash = hash_password(data.new_password)

        updated = self.user_repo.update_password(current_user.id, new_password_hash)

        if not updated:
            raise UserNotFoundError.not_found(user_id=current_user.id)

        return

    def delete_my_account(self, current_user: UserInternal) -> None:
        """
        Delete authenticated user's own account.

        WARNING: This is irreversible. All user data will be deleted.

        Business Rules:
        - Users can delete their own account
        - May fail if user has content (workouts/exercises) due to foreign keys

        Args:
            current_user: Currently authenticated user

        Raises:
            UserDeleteError: User has content that prevents deletion
            UserNotFoundError: User not found (shouldn't happen)
        """
        if not self.user_repo.get_by_id(current_user.id):
            raise UserNotFoundError.not_found(user_id=current_user.id)

        deleted = self.user_repo.delete(current_user.id)
        if not deleted:
            raise UserDeleteError.blocked_by_related_records()

    def update_profile_picture(
        self,
        current_user: UserInternal,
        profile_picture_url: str | None,
    ) -> UserProfile:
        """Set or clear the authenticated user's profile picture URL."""

        url_value = str(profile_picture_url) if profile_picture_url is not None else None
        updated_user = self.user_repo.set_profile_picture_url(current_user.id, url_value)
        if not updated_user:
            raise UserNotFoundError.not_found(user_id=current_user.id)

        return UserProfile(**updated_user.model_dump())

    def refresh_access_token(self, data: RefreshRequest) -> TokenPairResponse:
        """
        Validate a refresh token and issue a new access/refresh token pair.

        Business Rules:
        - Refresh token must be valid and unexpired
        - Refresh token must be of type "refresh"
        - User from token must still exist
        - Token version in JWT must match the current user's token_version

        Args:
            data: Request containing the refresh token

        Returns:
            TokenPairResponse: New JWT access/refresh token pair

        Raises:
            InvalidRefreshTokenError: If token is invalid, expired, malformed, or revoked
            UserNotFoundError: If the user no longer exists
        """
        payload = decode_token(data.refresh_token, expected_type="refresh")
        if payload is None:
            raise InvalidRefreshTokenError.invalid_or_expired()

        user_id_raw = payload.sub
        token_version = payload.token_version

        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError) as exc:
            raise InvalidRefreshTokenError.invalid_payload() from exc

        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError.not_found(user_id=user_id)

        if user.token_version != token_version:
            raise InvalidRefreshTokenError.revoked()

        token_data: TokenInput = {
            "user_id": user.id,
            "username": user.username,
            "token_version": user.token_version,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        self._log.info("Tokens refreshed: id=%d username=%s", user.id, user.username)

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )
