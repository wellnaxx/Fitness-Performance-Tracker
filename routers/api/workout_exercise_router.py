from typing import Annotated

from fastapi import APIRouter, Depends, status

from dependencies.auth import get_current_user
from dependencies.providers import get_workout_exercise_service
from schemas.user_schema import UserInternal
from schemas.workout_exercises_schema import (
    WorkoutExerciseCreate,
    WorkoutExercisePublic,
    WorkoutExerciseUpdate,
)
from services.workout_exercise_service import WorkoutExerciseService

workout_exercise_router = APIRouter(prefix="/workouts/{workout_id}/exercises", tags=["workout-exercises"])


@workout_exercise_router.post("/", status_code=status.HTTP_201_CREATED)
def create_workout_exercise(
    workout_id: int,
    workout_exercise_data: WorkoutExerciseCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """
    Add a new exercise to a workout."""
    return service.create_workout_exercise(current_user.id, workout_id, workout_exercise_data)


@workout_exercise_router.get("/{workout_exercise_id}", status_code=status.HTTP_200_OK)
def get_workout_exercise_by_id(
    workout_id: int,
    workout_exercise_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """
    Retrieve a workout exercise by ID, ensuring it's visible to the user.
    """
    return service.get_workout_exercise(current_user.id, workout_id, workout_exercise_id)


@workout_exercise_router.get("/", status_code=status.HTTP_200_OK)
def list_workout_exercises(
    workout_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> list[WorkoutExercisePublic]:
    """
    List exercises in a workout that are visible to the user.
    """
    return service.list_workout_exercises(current_user.id, workout_id)


@workout_exercise_router.patch("/{workout_exercise_id}", status_code=status.HTTP_200_OK)
def update_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
    update_data: WorkoutExerciseUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> WorkoutExercisePublic:
    """
    Update a workout exercise, ensuring it's visible to the user.
    """
    return service.update_workout_exercise(current_user.id, workout_id, workout_exercise_id, update_data)


@workout_exercise_router.delete("/{workout_exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout_exercise(
    workout_id: int,
    workout_exercise_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> None:
    """
    Delete a workout exercise, ensuring it's visible to the user.
    """
    service.delete_workout_exercise(current_user.id, workout_id, workout_exercise_id)
