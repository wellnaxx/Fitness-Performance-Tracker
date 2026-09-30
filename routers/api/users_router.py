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

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserCreate, service: Annotated[UserService, Depends(get_user_service)]) -> UserProfile:
    return service.register_user(user_data)


@users_router.post(
    "/login",
    status_code=status.HTTP_200_OK,
)
def login(data: UserLogin, service: Annotated[UserService, Depends(get_user_service)]) -> TokenPairResponse:
    return service.login_user(data)


@users_router.post(
    "/token",
    status_code=status.HTTP_200_OK,
)
def oauth2_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenPairResponse:
    """OAuth2-compatible login endpoint for Swagger UI and password flow clients."""
    return service.login_user(
        UserLogin(
            email=form_data.username,
            password=form_data.password,
        )
    )


@users_router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
)
def refresh(
    refresh_request: RefreshRequest, service: Annotated[UserService, Depends(get_user_service)]
) -> TokenPairResponse:
    return service.refresh_access_token(refresh_request)


@users_router.get("/me")
def my_profile(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Return the authenticated user's own private profile."""
    return service.get_my_profile(current_user)


@users_router.patch("/me")
def update_profile(
    updates: UserUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Update the authenticated user's profile."""
    return service.update_my_profile(current_user, updates)


@users_router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangeUserPassword,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Change the authenticated user's password."""
    service.change_password(current_user, data)


@users_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Delete the authenticated user's account."""
    service.delete_my_account(current_user)


@users_router.patch("/me/avatar")
def update_profile_picture(
    data: ProfilePictureUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Set or clear the authenticated user's profile picture URL."""
    return service.update_profile_picture(
        current_user,
        str(data.profile_picture_url) if data.profile_picture_url is not None else None,
    )
