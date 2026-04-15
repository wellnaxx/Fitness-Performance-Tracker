from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from core.errors.exercise import ExerciseNotFoundError
from core.errors.workout import WorkoutNotFoundError
from core.errors.workout_exercise import (
    WorkoutExerciseCreationError,
    WorkoutExerciseDeleteError,
    WorkoutExerciseNotFoundError,
    WorkoutExerciseUpdateError,
    WorkoutExerciseValidationError,
)
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
    try:
        return service.create_workout_exercise(current_user.id, workout_id, workout_exercise_data)
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutExerciseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WorkoutExerciseCreationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    

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
    try:
        return service.get_workout_exercise(current_user.id, workout_id, workout_exercise_id)
    except WorkoutExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    
@workout_exercise_router.get("/", status_code=status.HTTP_200_OK)
def list_workout_exercises(
    workout_id: int,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[WorkoutExerciseService, Depends(get_workout_exercise_service)],
) -> list[WorkoutExercisePublic]:
    """
    List exercises in a workout that are visible to the user.
    """
    try:
        return service.list_workout_exercises(current_user.id, workout_id)
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    
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
    try:
        return service.update_workout_exercise(current_user.id, workout_id, workout_exercise_id, update_data)
    except WorkoutExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutExerciseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WorkoutExerciseUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    
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
    try:
        service.delete_workout_exercise(current_user.id, workout_id, workout_exercise_id)
    except WorkoutExerciseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WorkoutExerciseDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc