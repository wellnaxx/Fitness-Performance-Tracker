"""Persistence contract for workout exercise set entries."""

from typing import Protocol

from schemas.set_entry_schema import SetEntryCreate, SetEntryPublic, SetEntryUpdate


class SetEntryRepositoryPort(Protocol):
    """Store and retrieve validated set entries within their parent exercise.

    Parent-scoped operations require both IDs to match; they do not verify the
    authenticated user's ownership of the workout. Services enforce that rule
    and coordinate shifting or normalization when changing set order. CRUD
    operations do not automatically reorder other entries.

    Implementations propagate existing database, row-validation, and repository
    errors for persistence failures. Missing entries use the documented None or
    False result rather than a service-level not-found exception.
    """

    def create(self, set_entry_data: SetEntryCreate) -> SetEntryPublic:
        """Create a set entry without shifting existing set numbers.

        Args:
            set_entry_data: Values including the parent workout exercise ID
                and the desired set number.

        Returns:
            The persisted set entry with its assigned ID and creation timestamp.

        Raises:
            SetEntryRepositoryError: If the inserted entry cannot be retrieved.
        """
        ...

    def get_by_id(self, set_entry_id: int) -> SetEntryPublic | None:
        """Retrieve an entry by ID without restricting its parent exercise.

        Args:
            set_entry_id: Set entry ID.

        Returns:
            The matching entry, or None if it does not exist.
        """
        ...

    def get_by_workout_exercise_and_id(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> SetEntryPublic | None:
        """Retrieve an entry only when it belongs to the specified exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.

        Returns:
            The entry, or None if absent or associated with another exercise.
        """
        ...

    def list_by_workout_exercise(
        self,
        workout_exercise_id: int,
    ) -> list[SetEntryPublic]:
        """List entries for one exercise in ascending set-number and ID order.

        Args:
            workout_exercise_id: Parent workout exercise ID.

        Returns:
            All matching entries, or an empty list when there are none.
        """
        ...

    def update_in_workout_exercise(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
        update_data: SetEntryUpdate,
    ) -> SetEntryPublic | None:
        """Partially update an entry belonging to the specified exercise.

        None-valued fields are ignored, so nullable fields cannot be cleared
        through this operation. An empty update returns the existing entry.
        Changing set_number does not shift or normalize other entries.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.
            update_data: Fields to update from the set-entry update whitelist.

        Returns:
            The resulting entry, or None if absent or under another exercise.

        Raises:
            SetEntryRepositoryError: If an update contains unsupported fields.
        """
        ...

    def delete_in_workout_exercise(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> bool:
        """Delete an entry within an exercise without normalizing set numbers.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            set_entry_id: Set entry ID.

        Returns:
            True if deleted; False if absent or under another exercise.
        """
        ...

    def shift_set_numbers(
        self,
        workout_exercise_id: int,
        from_set_number: int,
        delta: int,
    ) -> None:
        """Add delta to each matching set number within one exercise.

        Args:
            workout_exercise_id: Parent workout exercise ID.
            from_set_number: Inclusive lower bound of the set numbers to shift.
            delta: Signed amount to add to every matching set number.

        Returns:
            None. No matching entries is a no-op.
        """
        ...

    def normalize_set_numbers(self, workout_exercise_id: int) -> None:
        """Renumber an exercise's entries consecutively starting at 1.

        Preserve the order defined by ascending set number, then entry ID.

        Args:
            workout_exercise_id: Parent workout exercise ID.

        Returns:
            None. An exercise without entries is a no-op.
        """
        ...

    def get_by_workout_exercise_id_and_id(
        self,
        workout_exercise_id: int,
        set_entry_id: int,
    ) -> SetEntryPublic | None:
        """Compatibility alias for get_by_workout_exercise_and_id.

        Preserve its parent-first parameter order and missing-entry behavior.
        """
        ...

    def list_by_workout_exercise_id(
        self,
        workout_exercise_id: int,
    ) -> list[SetEntryPublic]:
        """Compatibility alias for list_by_workout_exercise, with identical ordering."""
        ...

    def update(
        self,
        set_entry_id: int,
        workout_exercise_id: int,
        update_data: SetEntryUpdate,
    ) -> SetEntryPublic | None:
        """Compatibility alias for update_in_workout_exercise.

        Accept the entry ID before the parent ID; preserve partial-update and
        missing-entry behavior.
        """
        ...

    def delete(self, set_entry_id: int, workout_exercise_id: int) -> bool:
        """Compatibility alias for delete_in_workout_exercise.

        Accept the entry ID before the parent ID and return whether it was deleted.
        """
        ...
