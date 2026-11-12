"""Safe body-measurement errors exposed by the shared HTTP exception handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.base import ServiceError

if TYPE_CHECKING:
    from datetime import date


class BodyMeasurementCreationError(ServiceError):
    """Creation failed for a reason other than a duplicate date (HTTP 500)."""

    @classmethod
    def create_failed(cls) -> BodyMeasurementCreationError:
        """Build a safe creation failure message.

        Returns:
            A creation error without persistence details.
        """
        return cls("Failed to create body measurement entry.")


class BodyMeasurementNotFoundError(ServiceError):
    """A requested entry is missing or inaccessible to the caller (HTTP 404)."""

    @classmethod
    def not_found(cls, entry_id: int) -> BodyMeasurementNotFoundError:
        """Build an ID-specific not-found error.

        Args:
            entry_id: Requested body measurement entry ID.

        Returns:
            An error identifying the requested ID without exposing another user's data.
        """
        return cls(f"Body measurement entry with ID {entry_id} not found.")

    @classmethod
    def not_found_by_date(cls, entry_date: date) -> BodyMeasurementNotFoundError:
        """Build a date-specific not-found error.

        Args:
            entry_date: Date for which the authenticated user has no entry.

        Returns:
            An error identifying the requested date in ISO format.
        """
        return cls(f"Body measurement for {entry_date.isoformat()} not found.")

    @classmethod
    def no_entries(cls, user_id: int) -> BodyMeasurementNotFoundError:
        """Build the latest-entry error for an empty history.

        Args:
            user_id: Authenticated user with no body measurement entries.

        Returns:
            An error describing the user's empty history.
        """
        return cls(f"User with ID {user_id} has no body measurement entries.")

    @classmethod
    def not_accessible(cls, entry_id: int) -> BodyMeasurementNotFoundError:
        """Build an error for a missing or unowned entry.

        Args:
            entry_id: Entry that is inaccessible or disappeared during a write.

        Returns:
            An error combining missing-entry and ownership rejection semantics.
        """
        return cls(f"Body measurement entry with ID {entry_id} not found or does not belong to the user.")


class BodyMeasurementUpdateError(ServiceError):
    """A repository-level update failure with a safe public message (HTTP 500)."""

    @classmethod
    def update_failed(cls, entry_id: int) -> BodyMeasurementUpdateError:
        """Build a safe update failure message.

        Args:
            entry_id: Entry whose update failed.

        Returns:
            An error identifying the entry without exposing persistence details.
        """
        return cls(f"Failed to update body measurement entry with ID {entry_id}.")


class BodyMeasurementDateConflictError(ServiceError):
    """Another entry for the same user already occupies the requested date (HTTP 409)."""

    @classmethod
    def already_exists(cls, entry_date: date) -> BodyMeasurementDateConflictError:
        """Build a conflict error for an occupied measurement date.

        Args:
            entry_date: Date already occupied by another entry for the same user.

        Returns:
            An error identifying the date without exposing the conflicting entry's ID.
        """
        return cls(f"A body measurement entry already exists for {entry_date.isoformat()}.")
