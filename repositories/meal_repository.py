"""
Meal Repository

This module handles all database interactions for the Meal entity.
It delegates database row validation and conversion to the dedicated mapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.repository import MealRepositoryError
from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from data.mappers.meal import map_meal
from data.queries import QUERIES

if TYPE_CHECKING:
    from datetime import date

    from schemas.meal_schema import MealCreate, MealPublic, MealUpdate


class MealRepository:
    """
    Repository for Meal database operations.

    Responsibilities:
    - Execute SQL queries related to meals
    - Convert database row dicts to MealPublic models
    - Handle all meal-related database logic
    """

    _MEAL_UPDATE_WHITELIST: Final[set[str]] = {
        "name",
        "description",
        "eaten_at",
        "meal_type",
        "notes",
    }

    def create(self, user_id: int, meal_data: MealCreate) -> MealPublic:
        """
        Create a new meal for a specific user.

        Args:
            user_id: ID of the user who owns the meal.
            meal_data: Meal creation payload.

        Returns:
            The newly created meal.

        Raises:
            MealRepositoryError: If the inserted meal cannot be retrieved afterwards.
        """
        sql = QUERIES.meals.create
        meal_id = execute_insert(
            sql,
            (
                user_id,
                meal_data.name,
                meal_data.description,
                meal_data.eaten_at,
                meal_data.meal_type,
                meal_data.notes,
            ),
        )

        meal = self.get_by_id(meal_id)
        if meal is None:
            raise MealRepositoryError.inserted_missing(meal_id)
        return meal

    def get_by_id(self, meal_id: int) -> MealPublic | None:
        """
        Retrieve a meal by its database ID.

        Args:
            meal_id: Meal ID.

        Returns:
            The meal if found, otherwise None.
        """
        row = fetch_one(QUERIES.meals.get_by_id, (meal_id,))
        if row is None:
            return None
        return map_meal(row)

    def get_by_user_and_id(self, user_id: int, meal_id: int) -> MealPublic | None:
        """
        Retrieve a meal by ID only if it belongs to the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.

        Returns:
            The meal if found and owned by the user, otherwise None.
        """
        row = fetch_one(
            QUERIES.meals.get_by_user_and_id,
            (user_id, meal_id),
        )
        if row is None:
            return None
        return map_meal(row)

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
        meal_type: str | None = None,
    ) -> list[MealPublic]:
        """
        List meals for a user with pagination and optional filters.

        Args:
            user_id: Owner user ID.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            date_from: Optional inclusive lower bound for `eaten_at`.
            date_to: Optional inclusive upper bound for `eaten_at`.
            meal_type: Optional meal type filter.

        Returns:
            A list of meals ordered from newest to oldest.
        """
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        filters: list[str] = []
        params: list[object] = [user_id]

        if date_from is not None:
            filters.append(QUERIES.meals.filter_date_from)
            params.append(date_from)

        if date_to is not None:
            filters.append(QUERIES.meals.filter_date_to)
            params.append(date_to)

        if meal_type is not None:
            filters.append(QUERIES.meals.filter_meal_type)
            params.append(meal_type)

        sql = QUERIES.meals.list_by_user.format(filters=" ".join(filters))
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [map_meal(row) for row in rows]

    def update_owned(
        self,
        user_id: int,
        meal_id: int,
        update_data: MealUpdate,
    ) -> MealPublic | None:
        """
        Partially update a meal owned by the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.
            update_data: Partial update payload.

        Returns:
            The updated meal if it exists and belongs to the user, otherwise None.

        Raises:
            MealRepositoryError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, meal_id)

        unknown = set(fields) - self._MEAL_UPDATE_WHITELIST
        if unknown:
            raise MealRepositoryError.invalid_update_fields(unknown)

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = QUERIES.meals.update_owned.format(set_clause=set_clause)
        execute_write(sql, (*fields.values(), user_id, meal_id))
        return self.get_by_user_and_id(user_id, meal_id)

    def delete_owned(self, user_id: int, meal_id: int) -> bool:
        """
        Delete a meal owned by the specified user.

        Args:
            user_id: Owner user ID.
            meal_id: Meal ID.

        Returns:
            True if a row was deleted, otherwise False.
        """
        return (
            execute_write(
                QUERIES.meals.delete_owned,
                (user_id, meal_id),
            )
            > 0
        )
