"""
Set Entry Repository

This module handles all database interactions for the SetEntry entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import SetEntryRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.set_entry import map_set_entry
from data.queries import QUERIES

if TYPE_CHECKING:
    from schemas.set_entry_schema import SetEntryCreate, SetEntryPublic, SetEntryUpdate


class SetEntryRepository:
    """
    Repository for SetEntry database operations.

    Responsibilities:
    - Execute SQL queries related to set entries
    - Convert database row dicts to SetEntryPublic models
    - Handle all set-entry-related database logic
    """

    _SET_ENTRY_UPDATE_WHITELIST: Final[set[str]] = {
        "set_number",
        "reps",
        "weight",
        "rpe",
        "is_warmup",
        "completed",
    }

    def create(self, set_entry_data: SetEntryCreate) -> SetEntryPublic:
        """
        Create a new set entry for a workout exercise.

        Args:
            set_entry_data: Set entry creation payload.

        Returns:
            The newly created set entry.

        Raises:
            SetEntryRepositoryError: If the inserted row cannot be retrieved afterwards.
        """
        sql = QUERIES.set_entries.create
        set_entry_id = execute_insert(
            sql,
            (
                set_entry_data.workout_exercise_id,
                set_entry_data.set_number,
                set_entry_data.reps,
                set_entry_data.weight,
                set_entry_data.rpe,
                set_entry_data.is_warmup,
                set_entry_data.completed,
            ),
        )

        set_entry = self.get_by_id(set_entry_id)
        if set_entry is None:
            raise SetEntryRepositoryError.inserted_missing(set_entry_id)
        return set_entry

    def get_by_id(self, set_entry_id: int) -> SetEntryPublic | None:
        """
        Retrieve a set entry by its database ID.

        Args:
            set_entry_id: Set entry ID.

        Returns:
            The set entry if found, otherwise None.
        """
        row = fetch_one(QUERIES.set_entries.get_by_id, (set_entry_id,))
        if row is None:
            return None
        return map_set_entry(row)

    def get_by_workout_exercise_and_id(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> SetEntryPublic | None:
        """
        Retrieve a set entry by ID only if it belongs to the workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.

        Returns:
            The set entry if found, otherwise None.
        """
        row = fetch_one(
            QUERIES.set_entries.get_by_workout_exercise_and_id,
            (workout_exercise_id, set_entry_id),
        )
        if row is None:
            return None
        return map_set_entry(row)

    def list_by_workout_exercise(
        self,
        workout_exercise_id: int,
    ) -> list[SetEntryPublic]:
        """
        List set entries for a workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.

        Returns:
            Set entries ordered by set number.
        """
        rows = fetch_all(
            QUERIES.set_entries.list_by_workout_exercise,
            (workout_exercise_id,),
        )
        return [map_set_entry(row) for row in rows]

    def update_in_workout_exercise(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
        update_data: SetEntryUpdate,
    ) -> SetEntryPublic | None:
        """
        Partially update a set entry within a workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.
            update_data: Partial update payload.

        Returns:
            The updated set entry if found, otherwise None.

        Raises:
            SetEntryRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_workout_exercise_and_id(workout_exercise_id, set_entry_id)

        unknown = set(fields) - self._SET_ENTRY_UPDATE_WHITELIST
        if unknown:
            raise SetEntryRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.set_entries.update_in_workout_exercise.format(set_clause=set_clause)
        execute_write(sql, (*fields.values(), workout_exercise_id, set_entry_id))
        return self.get_by_workout_exercise_and_id(workout_exercise_id, set_entry_id)

    def delete_in_workout_exercise(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> bool:
        """
        Delete a set entry from a workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                QUERIES.set_entries.delete_in_workout_exercise,
                (workout_exercise_id, set_entry_id),
            )
            > 0
        )

    def shift_set_numbers(
        self,
        workout_exercise_id: int,
        from_set_number: int,
        delta: int,
    ) -> None:
        """
        Shift set numbers at or after a given position for one workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            from_set_number: Inclusive set number to start shifting from.
            delta: Signed amount to add to each matching set number.
        """
        execute_write(
            QUERIES.set_entries.shift_set_numbers,
            (delta, workout_exercise_id, from_set_number),
        )

    def normalize_set_numbers(self, workout_exercise_id: int) -> None:
        """
        Renumber set entries sequentially starting at 1 for a workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
        """
        execute_write(
            QUERIES.set_entries.normalize_set_numbers,
            (workout_exercise_id,),
        )

    def get_by_workout_exercise_id_and_id(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> SetEntryPublic | None:
        """Compatibility wrapper for `get_by_workout_exercise_and_id`."""
        return self.get_by_workout_exercise_and_id(workout_exercise_id, set_entry_id)

    def list_by_workout_exercise_id(
        self,
        workout_exercise_id: int,
    ) -> list[SetEntryPublic]:
        """Compatibility wrapper for `list_by_workout_exercise`."""
        return self.list_by_workout_exercise(workout_exercise_id)

    def update(
        self,
        set_entry_id: int,
        workout_exercise_id: int,
        update_data: SetEntryUpdate,
    ) -> SetEntryPublic | None:
        """Compatibility wrapper for `update_in_workout_exercise`."""
        return self.update_in_workout_exercise(workout_exercise_id, set_entry_id, update_data)

    def delete(self, set_entry_id: int, workout_exercise_id: int) -> bool:
        """Compatibility wrapper for `delete_in_workout_exercise`."""
        return self.delete_in_workout_exercise(workout_exercise_id, set_entry_id)
