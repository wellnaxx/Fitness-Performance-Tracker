"""
Set Entry Repository

This module handles all database interactions for the SetEntry entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Final, TypedDict

from core.errors.repository import SetEntryRepositoryError, SetEntryRowError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.set_entry_schema import SetEntryCreate, SetEntryPublic, SetEntryUpdate


class SetEntryRow(TypedDict):
    id: int
    workout_exercise_id: int
    set_number: int
    reps: int
    weight: Decimal
    rpe: int | None
    is_warmup: bool
    completed: bool
    created_at: datetime


class SetEntryRepository:
    """
    Repository for SetEntry database operations.

    Responsibilities:
    - Execute SQL queries related to set entries
    - Convert database row dicts to SetEntryPublic models
    - Handle all set-entry-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, workout_exercise_id, set_number, reps, weight, rpe,
               is_warmup, completed, created_at
        FROM set_entries
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
        sql = """
            INSERT INTO set_entries
            (workout_exercise_id, set_number, reps, weight, rpe, is_warmup, completed)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
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
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (set_entry_id,))
        if row is None:
            return None
        return self._row_to_set_entry(row)

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
            f"{self._BASE_SELECT} WHERE workout_exercise_id = %s AND id = %s",
            (workout_exercise_id, set_entry_id),
        )
        if row is None:
            return None
        return self._row_to_set_entry(row)

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
            f"{self._BASE_SELECT} WHERE workout_exercise_id = %s ORDER BY set_number ASC, id ASC",
            (workout_exercise_id,),
        )
        return [self._row_to_set_entry(row) for row in rows]

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
        sql = f"UPDATE set_entries SET {set_clause} WHERE workout_exercise_id = %s AND id = %s"
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
                "DELETE FROM set_entries WHERE workout_exercise_id = %s AND id = %s",
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
            """
            UPDATE set_entries
            SET set_number = set_number + %s
            WHERE workout_exercise_id = %s AND set_number >= %s
            """,
            (delta, workout_exercise_id, from_set_number),
        )

    def normalize_set_numbers(self, workout_exercise_id: int) -> None:
        """
        Renumber set entries sequentially starting at 1 for a workout exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
        """
        execute_write(
            """
            WITH ordered_entries AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY set_number ASC, id ASC) AS new_set_number
                FROM set_entries
                WHERE workout_exercise_id = %s
            )
            UPDATE set_entries AS se
            SET set_number = ordered_entries.new_set_number
            FROM ordered_entries
            WHERE se.id = ordered_entries.id
            """,
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

    @staticmethod
    def _parse_set_entry_row(row: dict[str, object]) -> SetEntryRow:
        """Validate and normalize a raw database row into a typed SetEntryRow."""
        id_value = row.get("id")
        workout_exercise_id = row.get("workout_exercise_id")
        set_number = row.get("set_number")
        reps = row.get("reps")
        weight = row.get("weight")
        rpe = row.get("rpe")
        is_warmup = row.get("is_warmup")
        completed = row.get("completed")
        created_at = row.get("created_at")

        if not isinstance(id_value, int):
            raise SetEntryRowError.invalid_type("id", "int")
        if not isinstance(workout_exercise_id, int):
            raise SetEntryRowError.invalid_type("workout_exercise_id", "int")
        if not isinstance(set_number, int):
            raise SetEntryRowError.invalid_type("set_number", "int")
        if not isinstance(reps, int):
            raise SetEntryRowError.invalid_type("reps", "int")
        if not isinstance(weight, (Decimal, int, float)):
            raise SetEntryRowError.invalid_type("weight", "numeric")
        if rpe is not None and not isinstance(rpe, int):
            raise SetEntryRowError.invalid_type("rpe", "int | None")
        if not isinstance(is_warmup, bool):
            raise SetEntryRowError.invalid_type("is_warmup", "bool")
        if not isinstance(completed, bool):
            raise SetEntryRowError.invalid_type("completed", "bool")
        if not isinstance(created_at, datetime):
            raise SetEntryRowError.invalid_type("created_at", "datetime")

        return SetEntryRow(
            id=id_value,
            workout_exercise_id=workout_exercise_id,
            set_number=set_number,
            reps=reps,
            weight=Decimal(str(weight)),
            rpe=rpe,
            is_warmup=is_warmup,
            completed=completed,
            created_at=created_at,
        )

    @classmethod
    def _row_to_set_entry(cls, row: dict[str, object]) -> SetEntryPublic:
        """Convert a raw database row into a validated SetEntryPublic model."""
        set_entry_row = cls._parse_set_entry_row(row)
        return SetEntryPublic.model_validate(set_entry_row)
