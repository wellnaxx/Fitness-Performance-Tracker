"""Safe body-weight entry errors exposed by the shared HTTP exception handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.base import ServiceError

if TYPE_CHECKING:
    from datetime import date


class BodyWeightEntryCreationError(ServiceError):
    """Creation failed for a reason other than a duplicate date (HTTP 500)."""

    @classmethod
    def create_failed(cls) -> BodyWeightEntryCreationError:
        """Build a safe creation failure message.

        Returns:
            A creation error without persistence details.
        """
        return cls("Failed to create body weight entry.")


class BodyWeightEntryNotFoundError(ServiceError):
    """A requested body weight entry is missing or inaccessible (HTTP 404)."""

    @classmethod
    def not_found(cls, entry_id: int) -> BodyWeightEntryNotFoundError:
        """Build an ID-specific not-found error.

        Args:
            entry_id: Requested body weight entry ID.

        Returns:
            An error identifying the requested ID without exposing another user's data.
        """
        return cls(f"Body weight entry with ID {entry_id} not found.")

    @classmethod
    def not_found_by_date(cls, entry_date: date) -> BodyWeightEntryNotFoundError:
        """Build a date-specific not-found error.

        Args:
            entry_date: Date for which the authenticated user has no entry.

        Returns:
            An error identifying the requested date in ISO format.
        """
        return cls(f"Body weight entry for {entry_date.isoformat()} not found.")

    @classmethod
    def no_entries(cls, user_id: int) -> BodyWeightEntryNotFoundError:
        """Build the latest-entry error for an empty history.

        Args:
            user_id: Authenticated user with no body weight entries.

        Returns:
            An error describing the user's empty history.
        """
        return cls(f"User with ID {user_id} has no body weight entries.")

    @classmethod
    def not_accessible(cls, entry_id: int) -> BodyWeightEntryNotFoundError:
        """Build an error for a missing or unowned entry.

        Args:
            entry_id: Entry that is inaccessible or disappeared during a write.

        Returns:
            An error combining missing-entry and ownership rejection semantics.
        """
        return cls(f"Body weight entry with ID {entry_id} not found or does not belong to the user.")


class BodyWeightEntryUpdateError(ServiceError):
    """A repository-level update failure with a safe public message (HTTP 500)."""

    @classmethod
    def update_failed(cls, entry_id: int) -> BodyWeightEntryUpdateError:
        """Build a safe update failure message.

        Args:
            entry_id: Entry whose update failed.

        Returns:
            An error identifying the entry without exposing persistence details.
        """
        return cls(f"Failed to update body weight entry with ID {entry_id}.")


class BodyWeightEntryDateConflictError(ServiceError):
    """Another body weight entry for this user occupies the requested date (HTTP 409)."""

    @classmethod
    def already_exists(cls, entry_date: date) -> BodyWeightEntryDateConflictError:
        """Build a conflict error for an occupied body weight entry date.

        Args:
            entry_date: Date already occupied by another entry for the same user.

        Returns:
            An error identifying the date without exposing the conflicting entry's ID.
        """
        return cls(f"A body weight entry already exists for {entry_date.isoformat()}.")
