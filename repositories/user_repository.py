"""
User Repository - Data Access Layer for User operations.

This module handles all database interactions for the User entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from typing import Optional
from data.executor import fetch_all, fetch_one, execute_insert, execute_write
from schemas.user_schema import UserInternal, UserCreate


class UserRepository:
    """
    Repository for User database operations.

    Responsibilities:
    - Execute SQL queries related to users
    - Convert database row dicts to UserInternal models
    - Handle all user-related database logic
    """

    _BASE_SELECT = """
        SELECT id, username, first_name, last_name, date_of_birth, email, password_hash,
               profile_picture_url, token_version, created_at, updated_at
        FROM users
    """

    _PROFILE_UPDATE_WHITELIST = {
        "first_name",
        "last_name",
        "date_of_birth",
        "email",
        "profile_picture_url",
    }

    def create(self, user_data: UserCreate, password_hash: str) -> UserInternal:
        """
        Insert a new user into the database.

        Returns:
            UserInternal: Complete user data including generated ID.

        Raises:
            RuntimeError: If the inserted user cannot be retrieved.
        """
        sql = """
            INSERT INTO users
            (first_name, last_name, date_of_birth, email, username, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        user_id = execute_insert(sql, (
            user_data.first_name,
            user_data.last_name,
            user_data.date_of_birth,
            user_data.email,
            user_data.username,
            password_hash,
        ))
        user = self.get_by_id(user_id)
        if not user:
            raise RuntimeError(f"User {user_id} was inserted but could not be retrieved.")
        return user

    def username_exists(self, username: str) -> bool:
        return fetch_one("SELECT 1 FROM users WHERE username = %s LIMIT 1", (username,)) is not None

    def email_exists(self, email: str) -> bool:
        return fetch_one("SELECT 1 FROM users WHERE email = %s LIMIT 1", (email,)) is not None

    def get_by_id(self, user_id: int) -> Optional[UserInternal]:
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (user_id,))
        return self._row_to_user(row) if row else None

    def get_by_username(self, username: str) -> Optional[UserInternal]:
        row = fetch_one(f"{self._BASE_SELECT} WHERE username = %s", (username,))
        return self._row_to_user(row) if row else None

    def get_by_email(self, email: str) -> Optional[UserInternal]:
        row = fetch_one(f"{self._BASE_SELECT} WHERE email = %s", (email,))
        return self._row_to_user(row) if row else None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[UserInternal]:
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)
        rows = fetch_all(
            f"{self._BASE_SELECT} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return [self._row_to_user(row) for row in rows]

    def update(self, user_id: int, **updates: dict[str, object]) -> Optional[UserInternal]:
        """
        Patch-update allowed profile fields (whitelist-enforced).

        Unknown fields raise ValueError. None values are skipped.
        """
        if not updates:
            return self.get_by_id(user_id)

        unknown = set(updates.keys()) - self._PROFILE_UPDATE_WHITELIST
        if unknown:
            raise ValueError(f"Invalid fields for update: {', '.join(sorted(unknown))}")

        filtered = {k: v for k, v in updates.items() if v is not None}
        if not filtered:
            return self.get_by_id(user_id)

        set_clause = ", ".join(f"{field} = %s" for field in filtered)
        sql = f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        execute_write(sql, (*filtered.values(), user_id))

        user = self.get_by_id(user_id)
        if not user:
            raise RuntimeError(f"User {user_id} was updated but could not be retrieved.")
        return user

    def set_profile_picture_url(self, user_id: int, profile_picture_url: str | None) -> Optional[UserInternal]:
        """Set or clear a user's profile picture URL.

        This method intentionally allows setting the value to NULL (by passing None),
        which is not possible via the generic ``update`` method (it skips None values).
        """
        execute_write(
            "UPDATE users SET profile_picture_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (profile_picture_url, user_id),
        )
        return self.get_by_id(user_id)

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update password and bump token_version to invalidate existing sessions."""
        return execute_write(
            "UPDATE users SET password_hash = %s, token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_password_hash, user_id),
        ) > 0

    def bump_token_version(self, user_id: int) -> bool:
        return execute_write(
            "UPDATE users SET token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (user_id,),
        ) > 0

    def delete(self, user_id: int) -> bool:
        """
        Delete a user. Cascades to user goals, workouts, exercises, etc. via FK constraints.
        Callers should verify the user exists with get_by_id() before calling this.
        """
        return execute_write("DELETE FROM users WHERE id = %s", (user_id,)) > 0


    @staticmethod
    def _row_to_user(row: dict) -> UserInternal:
        """Convert a database row dict to a UserInternal model."""
        return UserInternal(
            id=row["id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            date_of_birth=row["date_of_birth"],
            email=row["email"],
            password_hash=row["password_hash"],
            profile_picture_url=row["profile_picture_url"],
            token_version=row["token_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
