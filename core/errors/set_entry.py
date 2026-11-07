"""Public set-entry service errors translated by the shared HTTP handlers."""

from __future__ import annotations

from core.errors.base import ServiceError


class SetEntryCreationError(ServiceError):
    """Creation failed; the public message does not expose repository details (HTTP 500)."""

    @classmethod
    def create_failed(cls) -> SetEntryCreationError:
        """Build the public creation error; retain the repository error as its cause."""
        return cls("Failed to create set entry.")


class SetEntryValidationError(ServiceError):
    """A requested position violates the service's ordering rules (HTTP 400)."""

    @classmethod
    def invalid_set_number(cls, set_number: int, count: int) -> SetEntryValidationError:
        """Describe a position beyond the allowed range, given the existing set count.

        Creation permits 1..count + 1; updates permit 1..count. Request schemas
        enforce positive set numbers before the service is called.
        """
        return cls(f"Set number out of range: {set_number}. This set has {count} sets.")

    @classmethod
    def identical_set_number(cls, old_set_number: int, new_set_number: int) -> SetEntryValidationError:
        """Reject an explicit request to keep the current position, even with other updates."""
        return cls(
            f"You cannot update the set number to the same value. "
            f"Old value: {old_set_number}, new value: {new_set_number}. "
        )


class SetEntryNotFoundError(ServiceError):
    """A required set is absent, including one disappearing during a write (HTTP 404)."""

    @classmethod
    def not_found(cls, set_entry_id: int) -> SetEntryNotFoundError:
        """Describe the inaccessible or missing set entry without returning its data."""
        return cls(f"Set entry with ID {set_entry_id} not found or does not belong to the user.")


class SetEntryDeleteError(ServiceError):
    """Deletion affected no row after the locked existence check (HTTP 500)."""

    @classmethod
    def delete_failed(cls, set_entry_id: int) -> SetEntryDeleteError:
        """Identify the set whose deletion failed without exposing database details."""
        return cls(f"Failed to delete set with ID {set_entry_id}.")
