"""Authenticated set-entry endpoints; ownership and ordering belong to the service."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.params import Path, Query

from dependencies.auth import get_current_user
from dependencies.providers import get_set_entry_service
from schemas.set_entry_schema import SetEntryCreate, SetEntryPublic, SetEntryUpdate
from schemas.user_schema import UserInternal
from services.set_entry_service import SetEntryService

set_entry_router = APIRouter(
    prefix="/sets",
    tags=[
        "set_entries",
        "sets",
    ],
)


@set_entry_router.post("/", status_code=status.HTTP_201_CREATED)
def create_set(
    set_entry_data: SetEntryCreate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[SetEntryService, Depends(get_set_entry_service)],
) -> SetEntryPublic:
    """Create a set in an owned workout exercise and return it with HTTP 201.

    Supply the parent workout_exercise_id in the body. Positions start at 1
    and may be at most N + 1 for N existing sets. Inserting shifts later sets;
    appending does not. Reps and weight may be zero; RPE is optional (1..10).

    Requires a Bearer access token (401 otherwise). Returns 404 for a missing
    parent or inaccessible workout, 400 for an out-of-range position, 422 for
    an invalid body, and 500 for a persistence failure.
    """
    return service.create(current_user.id, set_entry_data)


@set_entry_router.get("/{set_entry_id}", status_code=status.HTTP_200_OK)
def get_by_id(
    set_entry_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[SetEntryService, Depends(get_set_entry_service)],
) -> SetEntryPublic:
    """Return one set after verifying its parent exercise and workout ownership.

    The path ID must be a positive integer (422 otherwise). Requires a Bearer
    access token (401 otherwise). Missing sets, parents, and inaccessible
    workouts return 404. Persistence failures return a sanitized 500 response.
    """
    return service.get_by_id(current_user.id, set_entry_id)


@set_entry_router.get("/workout_exercise/{workout_exercise_id}", status_code=status.HTTP_200_OK)
def list_by_workout_exercise(
    workout_exercise_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[SetEntryService, Depends(get_set_entry_service)],
) -> list[SetEntryPublic]:
    """List an owned workout exercise's sets by set number, then ID.

    Use the workout exercise ID, rather than the exercise catalog ID. Returns
    all matching sets without pagination; an exercise without sets returns [].
    The path ID must be positive (422 otherwise). Requires a Bearer access
    token (401 otherwise). A missing parent or inaccessible workout returns
    404; persistence failures return a sanitized 500 response.
    """
    return service.list_by_workout_exercise(current_user.id, workout_exercise_id)


@set_entry_router.patch("/{set_entry_id}", status_code=status.HTTP_200_OK)
def update(
    workout_exercise_id: Annotated[int, Query(gt=0)],
    set_entry_id: Annotated[int, Path(gt=0)],
    update_data: SetEntryUpdate,
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[SetEntryService, Depends(get_set_entry_service)],
) -> SetEntryPublic:
    """Partially update a set, optionally moving it within its parent exercise.

    Supply the positive set_entry_id in the path and the expected positive
    workout_exercise_id as a required query parameter. Both identify the
    existing set; this operation cannot move a set to another exercise.

    Omitted or null fields keep their stored values, including RPE. An empty
    object is valid; zero reps/weight and False flags are applied. A new
    position must be within 1..N and differ from the current position. Omit
    set_number to keep it. Reordering and updates commit together.

    Requires a Bearer access token (401 otherwise). Missing or inaccessible
    resources return 404. Invalid moves or a parent mismatch after ownership
    verification return 400. Invalid IDs, missing query parameters, and invalid
    bodies return 422; persistence failures return a sanitized 500 response.
    """
    return service.update(current_user.id, workout_exercise_id, set_entry_id, update_data)


@set_entry_router.delete("/{set_entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    workout_exercise_id: Annotated[int, Query(gt=0)],
    set_entry_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[UserInternal, Depends(get_current_user)],
    service: Annotated[SetEntryService, Depends(get_set_entry_service)],
) -> None:
    """Delete an owned set and return HTTP 204 with an empty response body.

    Supply the positive set_entry_id in the path and the expected positive
    workout_exercise_id as a required query parameter. Deletion renumbers
    remaining sets from 1 in the same transaction; deleting the last set
    leaves an empty exercise.

    Requires a Bearer access token (401 otherwise). Missing or inaccessible
    resources return 404, including repeated deletion. A parent mismatch after
    ownership verification returns 400. Invalid IDs or a missing parent query
    parameter return 422. Failed deletion or persistence returns 500.
    """
    service.delete(current_user.id, workout_exercise_id, set_entry_id)
