"""
FastAPI repository/service providers.

Centralising all Depends() providers here means each router simply imports the
provider function it needs — no service is ever instantiated manually in a router.
"""

from fastapi import Depends

from repositories.user_goals_repository import UserGoalsRepository
from repositories.user_repository import UserRepository
from services.user_goals_service import UserGoalsService
from services.user_service import UserService


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_user_goals_repository() -> UserGoalsRepository:
    return UserGoalsRepository()


def get_user_goals_service(
    repo: UserGoalsRepository = Depends(get_user_goals_repository),
) -> UserGoalsService:
    return UserGoalsService(repo)
