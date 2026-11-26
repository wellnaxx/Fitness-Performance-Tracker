"""HTTP endpoints for users operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from dependencies.auth import get_current_user
from dependencies.providers import get_user_service
from schemas.token_schema import RefreshRequest, TokenPairResponse
from schemas.user_schema import (
    ChangeUserPassword,
    ProfilePictureUpdate,
    UserCreate,
    UserInternal,
    UserLogin,
    UserProfile,
    UserUpdate,
)
from services.user_service import UserService

users_router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={500: {"description": "Persistence failure; internal details are excluded from the response."}},
)


@users_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "If the username is already registered. If the email is already registered."}
    },
)
def register(user_data: UserCreate, service: Annotated[UserService, Depends(get_user_service)]) -> UserProfile:
    """Register a user account.

    Args:
        user_data: Validated registration fields and plaintext password; the service hashes the password.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The persisted record with its assigned ID (HTTP 201).

    Raises:
        UsernameAlreadyExistsError: HTTP 409. If the username is already registered.
        EmailAlreadyExistsError: HTTP 409. If the email is already registered.
        UserCreationError: HTTP 500. If registration fails.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.register_user(user_data)


@users_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "If credentials are invalid."}},
)
def login(data: UserLogin, service: Annotated[UserService, Depends(get_user_service)]) -> TokenPairResponse:
    """Exchange JSON credentials for access and refresh tokens.

    Args:
        data: Validated email and password.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An access and refresh token pair (HTTP 200).

    Raises:
        InvalidCredentialsError: HTTP 401. If credentials are invalid.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.login_user(data)


@users_router.post(
    "/token",
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "If credentials are invalid."}},
)
def oauth2_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenPairResponse:
    """OAuth2-compatible login endpoint for Swagger UI and password flow clients.

    Args:
        form_data: OAuth2 form fields; username is interpreted as the account email.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An access and refresh token pair (HTTP 200).

    Raises:
        InvalidCredentialsError: HTTP 401. If credentials are invalid.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.login_user(
        UserLogin(
            email=form_data.username,
            password=form_data.password,
        )
    )


@users_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "If the token is invalid, expired, revoked, or belongs to a deleted account."}
    },
)
def refresh(
    refresh_request: RefreshRequest, service: Annotated[UserService, Depends(get_user_service)]
) -> TokenPairResponse:
    """Validate a refresh token and issue a new token pair.

    Args:
        refresh_request: Refresh token to validate before issuing a new token pair.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An access and refresh token pair (HTTP 200).

    Raises:
        InvalidRefreshTokenError: HTTP 401. If the token is invalid, expired, revoked, or belongs to a
            deleted account.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.refresh_access_token(refresh_request)


@users_router.get(
    "/me", responses={401: {"description": "If Bearer authentication fails."}}, status_code=status.HTTP_200_OK
)
def my_profile(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Return the authenticated user's own private profile.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.get_my_profile(current_user)


@users_router.patch(
    "/me",
    responses={
        401: {"description": "If Bearer authentication fails."},
        409: {"description": "If another account uses the requested email."},
        404: {"description": "If the account disappears during persistence."},
    },
    status_code=status.HTTP_200_OK,
)
def update_profile(
    updates: UserUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Update the authenticated user's profile.

    Args:
        updates: Validated profile changes; omitted and null fields preserve stored values.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        EmailAlreadyExistsError: HTTP 409. If another account uses the requested email.
        UserNotFoundError: HTTP 404. If the account disappears during persistence.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update_my_profile(current_user, updates)


@users_router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "If Bearer authentication fails."},
        400: {"description": "If the old password is incorrect. If the requested password is unchanged."},
        404: {"description": "If the account disappears."},
    },
)
def change_password(
    data: ChangeUserPassword,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Change the authenticated user's password.

    Args:
        data: Validated old and new passwords.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        IncorrectOldPasswordError: HTTP 400. If the old password is incorrect.
        IdenticalPasswordsError: HTTP 400. If the requested password is unchanged.
        UserNotFoundError: HTTP 404. If the account disappears.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.change_password(current_user, data)


@users_router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "If Bearer authentication fails."},
        404: {"description": "If the account disappears."},
        400: {"description": "If account deletion cannot complete."},
    },
)
def delete_account(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Delete the authenticated user's account.

    Args:
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        An empty response after successful completion (HTTP 204).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the account disappears.
        UserDeleteError: HTTP 400. If account deletion cannot complete.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    service.delete_my_account(current_user)


@users_router.patch(
    "/me/avatar",
    responses={
        401: {"description": "If Bearer authentication fails."},
        404: {"description": "If the account disappears during persistence."},
    },
    status_code=status.HTTP_200_OK,
)
def update_profile_picture(
    data: ProfilePictureUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Set or clear the authenticated user's profile picture URL.

    Args:
        data: HTTP(S) avatar URL, or null to clear it.
        current_user: User resolved from the Bearer access token; determines ownership.
        service: Injected service containing business rules and ownership checks.

    Returns:
        The requested or updated record (HTTP 200).

    Raises:
        HTTPException: HTTP 401. If Bearer authentication fails.
        UserNotFoundError: HTTP 404. If the account disappears during persistence.
        RequestValidationError: HTTP 422. If path, query, form, or body values are invalid.
        DatabaseError: HTTP 500. If persistence or an authentication lookup fails; internal details are
            hidden.
    """
    return service.update_profile_picture(
        current_user,
        str(data.profile_picture_url) if data.profile_picture_url is not None else None,
    )
