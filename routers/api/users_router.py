from fastapi import APIRouter, Depends, HTTPException, status

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
from utils.errors import (
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

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.post(
    "/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate, service: UserService = Depends(get_user_service)
) -> UserProfile:
    try:
        return service.register_user(user_data)
    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UserCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@users_router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    data: UserLogin, service: UserService = Depends(get_user_service)
) -> TokenPairResponse:
    try:
        return service.login_user(data)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@users_router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
)
def refresh(
    refresh_request: RefreshRequest, service: UserService = Depends(get_user_service)
) -> TokenPairResponse:
    try:
        return service.refresh_access_token(refresh_request)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@users_router.get("/me", response_model=UserProfile)
def my_profile(
    current_user: UserInternal = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Return the authenticated user's own private profile."""
    return service.get_my_profile(current_user)


@users_router.patch("/me", response_model=UserProfile)
def update_profile(
    updates: UserUpdate,
    current_user: UserInternal = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Update the authenticated user's profile."""
    try:
        return service.update_my_profile(current_user, updates)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@users_router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangeUserPassword,
    current_user: UserInternal = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Change the authenticated user's password."""
    try:
        service.change_password(current_user, data)
    except IncorrectOldPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except IdenticalPasswordsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@users_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: UserInternal = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Delete the authenticated user's account."""
    try:
        service.delete_my_account(current_user)
    except UserDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@users_router.patch("/me/avatar", response_model=UserProfile)
def update_profile_picture(
    data: ProfilePictureUpdate,
    current_user: UserInternal = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Set or clear the authenticated user's profile picture URL."""
    try:
        return service.update_profile_picture(
            current_user, str(data.profile_picture_url)
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
