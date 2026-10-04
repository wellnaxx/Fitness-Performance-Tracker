"""Pagination values and bounds shared by every listing layer."""

from dataclasses import dataclass
from typing import Final

DEFAULT_LIMIT: Final = 100
DEFAULT_OFFSET: Final = 0
MIN_LIMIT: Final = 1
MAX_LIMIT: Final = 1000
MIN_OFFSET: Final = 0


@dataclass(frozen=True, slots=True)
class PaginationParams:
    """Limit and offset for a list request."""

    limit: int = DEFAULT_LIMIT
    offset: int = DEFAULT_OFFSET


def normalize_pagination(
    limit: int = DEFAULT_LIMIT,
    offset: int = DEFAULT_OFFSET,
) -> PaginationParams:
    """Preserve repository clamping for callers outside the validated HTTP API."""
    return PaginationParams(
        limit=max(MIN_LIMIT, min(limit, MAX_LIMIT)),
        offset=max(MIN_OFFSET, offset),
    )
