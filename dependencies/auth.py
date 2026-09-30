"""
FastAPI dependencies for authentication and authorization.
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from auth.jwt_handler import decode_token
from core.errors.user import InvalidAccessTokenError
from dependencies.providers import get_user_repository
from repositories.user_repository import UserRepository
from schemas.user_schema import UserInternal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserInternal:
    """
    Validate the JWT access token and return the authenticated user.

    Raises 401 for missing/invalid/expired tokens or deleted users.
    """
    payload = decode_token(token, expected_type="access")
    if payload is None:
        raise InvalidAccessTokenError.invalid_or_expired()

    user_id_str = payload.sub
    if not user_id_str:
        raise InvalidAccessTokenError.missing_subject()

    try:
        user_id = int(user_id_str)
    except ValueError as exc:
        raise InvalidAccessTokenError.invalid_subject() from exc

    user = user_repo.get_by_id(user_id)
    if user is None:
        raise InvalidAccessTokenError.user_not_found()

    token_version = payload.token_version
    if token_version != user.token_version:
        raise InvalidAccessTokenError.revoked()

    return user
