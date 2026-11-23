"""Public progress-photo service errors translated by the shared HTTP handlers."""

from __future__ import annotations

from core.errors.base import ServiceError


class ProgressPhotoCreationError(ServiceError):
    """Creating a progress photo record failed (HTTP 500)."""

    @classmethod
    def create_failed(cls) -> ProgressPhotoCreationError:
        """Build a creation failure without exposing persistence details.

        Returns:
            A safe public creation error.
        """
        return cls("Failed to create progress photo.")


class ProgressPhotoNotFoundError(ServiceError):
    """A requested progress photo record is missing or inaccessible (HTTP 404)."""

    @classmethod
    def not_found(cls, photo_id: int) -> ProgressPhotoNotFoundError:
        """Build an error for a missing or unowned progress photo.

        Args:
            photo_id: Requested progress photo record ID.

        Returns:
            An error that does not distinguish missing records from another user's records.
        """
        return cls(f"Progress photo with ID {photo_id} not found or does not belong to the user.")

    @classmethod
    def not_accessible(cls, photo_id: int) -> ProgressPhotoNotFoundError:
        """Build an error for a record inaccessible during an operation.

        Args:
            photo_id: Record that is inaccessible or disappeared during a write.

        Returns:
            An error combining missing-record and ownership rejection semantics.
        """
        return cls(f"Progress photo with ID {photo_id} not accessible or does not belong to the user.")


class ProgressPhotoUpdateError(ServiceError):
    """Updating a progress photo record failed (HTTP 500)."""

    @classmethod
    def update_failed(cls, photo_id: int) -> ProgressPhotoUpdateError:
        """Build an update failure without exposing persistence details.

        Args:
            photo_id: Progress photo record whose update failed.

        Returns:
            A safe public update error identifying the record.
        """
        return cls(f"Failed to update progress photo with ID {photo_id}.")


class ProgressPhotoDeleteError(ServiceError):
    """Deleting a progress photo record failed (HTTP 500)."""

    @classmethod
    def delete_failed(cls, photo_id: int) -> ProgressPhotoDeleteError:
        """Build a deletion failure without exposing persistence details.

        Args:
            photo_id: Progress photo record whose deletion failed.

        Returns:
            A safe public deletion error identifying the record.
        """
        return cls(f"Failed to delete progress photo with ID {photo_id}.")
