"""
FastAPI repository/service providers.

Centralising all Depends() providers here means each router simply imports the
provider function it needs — no service is ever instantiated manually in a router.
"""

from fastapi import Depends

from data.unit_of_work import PostgresUnitOfWork
from ports.repositories.body_measurement_repository import BodyMeasurementRepositoryPort
from ports.repositories.body_weight_entry_repository import BodyWeightEntryRepositoryPort
from ports.repositories.exercise_repository import ExerciseRepositoryPort
from ports.repositories.meal_item_repository import MealItemRepositoryPort
from ports.repositories.meal_repository import MealRepositoryPort
from ports.repositories.progress_photo_repository import ProgressPhotoRepositoryPort
from ports.repositories.set_entry_repository import SetEntryRepositoryPort
from ports.repositories.user_goals_repository import UserGoalsRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from ports.repositories.workout_exercise_repository import WorkoutExerciseRepositoryPort
from ports.repositories.workout_repository import WorkoutRepositoryPort
from ports.unit_of_work import UnitOfWorkPort
from repositories.body_measurement_repository import BodyMeasurementRepository
from repositories.body_weight_entry_repository import BodyWeightEntryRepository
from repositories.exercise_repository import ExerciseRepository
from repositories.meal_item_repository import MealItemRepository
from repositories.meal_repository import MealRepository
from repositories.progress_photo_repository import ProgressPhotoRepository
from repositories.set_entry_repository import SetEntryRepository
from repositories.user_goals_repository import UserGoalsRepository
from repositories.user_repository import UserRepository
from repositories.workout_exercise_repository import WorkoutExerciseRepository
from repositories.workout_repository import WorkoutRepository
from services.body_measurement_service import BodyMeasurementService
from services.body_weight_entry_service import BodyWeightEntryService
from services.exercise_service import ExerciseService
from services.meal_item_service import MealItemService
from services.meal_service import MealService
from services.progress_photo_service import ProgressPhotoService
from services.set_entry_service import SetEntryService
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
    unit_of_work: UnitOfWorkPort = Depends(get_unit_of_work),
) -> WorkoutExerciseService:
    return WorkoutExerciseService(workout_exercise_repo, workout_repo, unit_of_work)


def get_set_entry_repository() -> SetEntryRepositoryPort:
    return SetEntryRepository()


def get_set_entry_service(
    set_entry_repo: SetEntryRepositoryPort = Depends(get_set_entry_repository),
    workout_exercise_repo: WorkoutExerciseRepositoryPort = Depends(get_workout_exercise_repository),
    workout_repo: WorkoutRepositoryPort = Depends(get_workout_repository),
    unit_of_work: UnitOfWorkPort = Depends(get_unit_of_work),
) -> SetEntryService:
    return SetEntryService(set_entry_repo, workout_exercise_repo, workout_repo, unit_of_work)


def get_body_measurement_repository() -> BodyMeasurementRepositoryPort:
    """Provide body measurement persistence without opening a database connection.

    Returns:
        A repository implementing the body measurement port.
    """
    return BodyMeasurementRepository()


def get_body_measurement_service(
    body_measurement_repo: BodyMeasurementRepositoryPort = Depends(get_body_measurement_repository),
) -> BodyMeasurementService:
    """Construct the body measurement service with its repository dependency.

    Args:
        body_measurement_repo: Injected body measurement repository port.

    Returns:
        The service used by body measurement routes.
    """
    return BodyMeasurementService(body_measurement_repo)


def get_body_weight_entry_repository() -> BodyWeightEntryRepositoryPort:
    """Provide body weight persistence without opening a database connection.

    Returns:
        A repository implementing the body weight entry port.
    """
    return BodyWeightEntryRepository()


def get_body_weight_entry_service(
    body_weight_entry_repo: BodyWeightEntryRepositoryPort = Depends(get_body_weight_entry_repository),
) -> BodyWeightEntryService:
    """Construct the body weight entry service with its repository dependency.

    Args:
        body_weight_entry_repo: Injected body weight entry repository port.

    Returns:
        The service used by body weight entry routes.
    """
    return BodyWeightEntryService(body_weight_entry_repo)


def get_meal_item_repository() -> MealItemRepositoryPort:
    """Provide meal-item persistence without opening a database connection.

    Returns:
        A repository implementing the meal-item port.
    """
    return MealItemRepository()


def get_meal_item_service(
    meal_repo: MealRepositoryPort = Depends(get_meal_repository),
    meal_item_repo: MealItemRepositoryPort = Depends(get_meal_item_repository),
) -> MealItemService:
    """Construct the meal-item service with parent and item repository dependencies.

    Args:
        meal_repo: Injected repository used to verify parent meal ownership.
        meal_item_repo: Injected repository for meal-scoped item operations.

    Returns:
        The service used by meal-item routes.
    """
    return MealItemService(meal_repo, meal_item_repo)


def get_progress_photo_repository() -> ProgressPhotoRepositoryPort:
    """Provide progress-photo persistence without opening a database connection.

    Returns:
        A repository implementing the progress-photo port.
    """
    return ProgressPhotoRepository()


def get_progress_photo_service(
    progress_photo_repo: ProgressPhotoRepositoryPort = Depends(get_progress_photo_repository),
) -> ProgressPhotoService:
    """Construct the progress-photo service with its persistence dependency.

    Args:
        progress_photo_repo: Injected progress-photo repository port.

    Returns:
        The service used by progress-photo routes.
    """
    return ProgressPhotoService(progress_photo_repo)
