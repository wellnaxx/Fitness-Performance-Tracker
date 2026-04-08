"""
Meal Repository

This module handles all database interactions for the Meal entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.meal_schema import MealCreate, MealPublic, MealUpdate


class MealRow(TypedDict):
    id: int
    user_id: int
    name: str
    description: str | None
    eaten_at: datetime
    meal_type: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class MealRepository:
    """
    Repository for Meal database operations.

    Responsibilities:
    - Execute SQL queries related to meals
    - Convert database row dicts to MealPublic models
    - Handle all meal-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, user_id, name, description, eaten_at, meal_type,
               notes, created_at, updated_at
        FROM meals
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
            RuntimeError: If the inserted meal cannot be retrieved afterwards.
        """
        sql = """
            INSERT INTO meals
            (user_id, name, description, eaten_at, meal_type, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
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
            raise RuntimeError(f"Meal {meal_id} was inserted but could not be retrieved.")
        return meal

    def get_by_id(self, meal_id: int) -> MealPublic | None:
        """
        Retrieve a meal by its database ID.

        Args:
            meal_id: Meal ID.

        Returns:
            The meal if found, otherwise None.
        """
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (meal_id,))
        if row is None:
            return None
        return self._row_to_meal(row)

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
            f"{self._BASE_SELECT} WHERE user_id = %s AND id = %s",
            (user_id, meal_id),
        )
        if row is None:
            return None
        return self._row_to_meal(row)

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

        sql = f"{self._BASE_SELECT} WHERE user_id = %s"
        params: list[object] = [user_id]

        if date_from is not None:
            sql += " AND eaten_at::date >= %s"
            params.append(date_from)

        if date_to is not None:
            sql += " AND eaten_at::date <= %s"
            params.append(date_to)

        if meal_type is not None:
            sql += " AND meal_type = %s"
            params.append(meal_type)

        sql += " ORDER BY eaten_at DESC, id DESC LIMIT %s OFFSET %s"
        params.extend([safe_limit, safe_offset])

        rows = fetch_all(sql, tuple(params))
        return [self._row_to_meal(row) for row in rows]

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
            ValueError: If any provided fields are not allowed to be updated.
        """
        fields = update_data.model_dump(exclude_none=True)
        if not fields:
            return self.get_by_user_and_id(user_id, meal_id)

        unknown = set(fields) - self._MEAL_UPDATE_WHITELIST
        if unknown:
            raise ValueError(f"Invalid fields for update: {', '.join(sorted(unknown))}")

        set_clause = ", ".join(f"{field} = %s" for field in fields)
        sql = (
            f"UPDATE meals SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND id = %s"
        )
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
                "DELETE FROM meals WHERE user_id = %s AND id = %s",
                (user_id, meal_id),
            )
            > 0
        )

    @staticmethod
    def _parse_meal_row(row: dict[str, object]) -> MealRow:
        """Validate and normalize a raw database row into a typed MealRow."""
        id_value = row.get("id")
        user_id = row.get("user_id")
        name = row.get("name")
        description = row.get("description")
        eaten_at = row.get("eaten_at")
        meal_type = row.get("meal_type")
        notes = row.get("notes")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        if not isinstance(id_value, int):
            raise ValueError("Invalid meal row: 'id' must be int")
        if not isinstance(user_id, int):
            raise ValueError("Invalid meal row: 'user_id' must be int")
        if not isinstance(name, str):
            raise ValueError("Invalid meal row: 'name' must be str")
        if description is not None and not isinstance(description, str):
            raise ValueError("Invalid meal row: 'description' must be str | None")
        if not isinstance(eaten_at, datetime):
            raise ValueError("Invalid meal row: 'eaten_at' must be datetime")
        if not isinstance(meal_type, str):
            raise ValueError("Invalid meal row: 'meal_type' must be str")
        if notes is not None and not isinstance(notes, str):
            raise ValueError("Invalid meal row: 'notes' must be str | None")
        if not isinstance(created_at, datetime):
            raise ValueError("Invalid meal row: 'created_at' must be datetime")
        if not isinstance(updated_at, datetime):
            raise ValueError("Invalid meal row: 'updated_at' must be datetime")

        return MealRow(
            id=id_value,
            user_id=user_id,
            name=name,
            description=description,
            eaten_at=eaten_at,
            meal_type=meal_type,
            notes=notes,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _row_to_meal(cls, row: dict[str, object]) -> MealPublic:
        """Convert a raw database row into a validated MealPublic model."""
        meal_row = cls._parse_meal_row(row)
        return MealPublic.model_validate(meal_row)
