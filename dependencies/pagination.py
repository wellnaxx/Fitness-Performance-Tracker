"""Shared HTTP query validation for paginated list routes."""

from typing import Annotated

from fastapi import Query

from utils.pagination import (
    DEFAULT_LIMIT,
    DEFAULT_OFFSET,
    MAX_LIMIT,
    MIN_LIMIT,
    MIN_OFFSET,
    PaginationParams,
)


def get_pagination(
    limit: Annotated[
        int, Query(ge=MIN_LIMIT, le=MAX_LIMIT, description="Maximum number of items to return.")
    ] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=MIN_OFFSET, description="Number of items to skip.")] = DEFAULT_OFFSET,
) -> PaginationParams:
    """Keep limit/offset as query parameters and reject invalid values with HTTP 422."""
    return PaginationParams(limit=limit, offset=offset)
