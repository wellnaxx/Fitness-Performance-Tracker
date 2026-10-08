"""
FastAPI repository/service providers.

Centralising all Depends() providers here means each router simply imports the
provider function it needs — no service is ever instantiated manually in a router.
"""

from fastapi import Depends

from data.unit_of_work import PostgresUnitOfWork
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from ports.repositories.meal_repository import MealRepositoryPort
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort
from repositories.exercise_repository import ExerciseRepository
from repositories.meal_repository import MealRepository
from repositories.user_goals_repository import UserGoalsRepository
from repositories.user_repository import UserRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from repositories.workout_repository import WorkoutRepository
from services.exercise_service import ExerciseService
from services.meal_service import MealService
from services.user_goals_service import UserGoalsService
from services.user_service import UserService
from services.workout_exercise_service import WorkoutExerciseService
from services.workout_service import WorkoutService


def get_user_repository() -> UserRepositoryPort:
    return UserRepository()


def get_user_service(
    repo: UserRepositoryPort = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_user_goals_repository() -> UserGoalsRepositoryPort:
    return UserGoalsRepository()


def get_unit_of_work() -> UnitOfWorkPort:
    return PostgresUnitOfWork()


def get_user_goals_service(
    repo: UserGoalsRepositoryPort = Depends(get_user_goals_repository),
    unit_of_work: UnitOfWorkPort = Depends(get_unit_of_work),
) -> UserGoalsService:
    return UserGoalsService(repo, unit_of_work)


def get_exercise_repository() -> ExerciseRepositoryPort:
    return ExerciseRepository()


def get_exercise_service(
    repo: ExerciseRepositoryPort = Depends(get_exercise_repository),
) -> ExerciseService:
    return ExerciseService(repo)


def get_workout_repository() -> WorkoutRepositoryPort:
    return WorkoutRepository()


def get_workout_service(
    repo: WorkoutRepositoryPort = Depends(get_workout_repository),
) -> WorkoutService:
    return WorkoutService(repo)


def get_meal_repository() -> MealRepositoryPort:
    return MealRepository()


def get_meal_service(
    repo: MealRepositoryPort = Depends(get_meal_repository),
) -> MealService:
    return MealService(repo)


def get_workout_exercise_repository() -> WorkoutExerciseRepositoryPort:
    return WorkoutExerciseRepository()


def get_workout_exercise_service(
    workout_exercise_repo: WorkoutExerciseRepositoryPort = Depends(get_workout_exercise_repository),
    workout_repo: WorkoutRepositoryPort = Depends(get_workout_repository),
    exercise_repo: ExerciseRepositoryPort = Depends(get_exercise_repository),
) -> WorkoutExerciseService:
    return WorkoutExerciseService(workout_exercise_repo, workout_repo, exercise_repo)
