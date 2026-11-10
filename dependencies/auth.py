"""
FastAPI dependencies for authentication and authorization.
"""

import logging

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from auth.jwt_handler import decode_token
from core.errors.user import InvalidAccessTokenError
from dependencies.providers import get_user_repository
from ports.repositories.user_repository import UserRepositoryPort
from schemas.user_schema import UserInternal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")
logger = logging.getLogger(__name__)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepositoryPort = Depends(get_user_repository),
) -> UserInternal:
    """
    Validate the JWT access token and return the authenticated user.

    Raises 401 for missing/invalid/expired tokens or deleted users.
    """
    payload = decode_token(token, expected_type="access")
    if payload is None:
        logger.warning("Access denied: invalid or expired token")
        raise InvalidAccessTokenError.invalid_or_expired()

    user_id_str = payload.sub
    if not user_id_str:
        logger.warning("Access denied: missing token subject")
        raise InvalidAccessTokenError.missing_subject()

    try:
        user_id = int(user_id_str)
    except ValueError as exc:
        logger.warning("Access denied: invalid token subject")
        raise InvalidAccessTokenError.invalid_subject() from exc

    user = user_repo.get_by_id(user_id)
    if user is None:
        logger.warning("Access denied: user missing | user_id=%s", user_id)
        raise InvalidAccessTokenError.user_not_found()

    token_version = payload.token_version
    if token_version != user.token_version:
        logger.warning("Access denied: revoked token | user_id=%s", user_id)
        raise InvalidAccessTokenError.revoked()

    return user
