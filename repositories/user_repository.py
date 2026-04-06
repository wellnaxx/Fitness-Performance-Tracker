"""
User Repository - Data Access Layer for User operations.

This module handles all database interactions for the User entity.
It translates between database rows (now dicts) and Pydantic models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final, TypedDict

from data.executor import execute_insert, execute_write, fetch_all, fetch_one
from schemas.user_schema import UserCreate, UserInternal


class UserRow(TypedDict):
    id: int
    username: str
    first_name: str
    last_name: str
    date_of_birth: date
    email: str
    password_hash: str
    profile_picture_url: str | None
    token_version: int
    created_at: datetime
    updated_at: datetime


class UserRepository:
    """
    Repository for User database operations.

    Responsibilities:
    - Execute SQL queries related to users
    - Convert database row dicts to UserInternal models
    - Handle all user-related database logic
    """

    _BASE_SELECT: Final[str] = """
        SELECT id, username, first_name, last_name, date_of_birth, email, password_hash,
               profile_picture_url, token_version, created_at, updated_at
        FROM users
    """

    _PROFILE_UPDATE_WHITELIST: Final[set[str]] = {
        "first_name",
        "last_name",
        "date_of_birth",
        "email",
        "profile_picture_url",
    }

    def create(self, user_data: UserCreate, password_hash: str) -> UserInternal:
        sql = """
            INSERT INTO users
            (first_name, last_name, date_of_birth, email, username, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        user_id = execute_insert(
            sql,
            (
                user_data.first_name,
                user_data.last_name,
                user_data.date_of_birth,
                user_data.email,
                user_data.username,
                password_hash,
            ),
        )

        user = self.get_by_id(user_id)
        if user is None:
            raise RuntimeError(
                f"User {user_id} was inserted but could not be retrieved."
            )
        return user

    def username_exists(self, username: str) -> bool:
        return (
            fetch_one(
                "SELECT 1 FROM users WHERE username = %s LIMIT 1",
                (username,),
            )
            is not None
        )

    def email_exists(self, email: str) -> bool:
        return (
            fetch_one(
                "SELECT 1 FROM users WHERE email = %s LIMIT 1",
                (email,),
            )
            is not None
        )

    def get_by_id(self, user_id: int) -> UserInternal | None:
        row = fetch_one(f"{self._BASE_SELECT} WHERE id = %s", (user_id,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_username(self, username: str) -> UserInternal | None:
        row = fetch_one(f"{self._BASE_SELECT} WHERE username = %s", (username,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_email(self, email: str) -> UserInternal | None:
        row = fetch_one(f"{self._BASE_SELECT} WHERE email = %s", (email,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[UserInternal]:
        safe_limit = max(1, min(limit, 1000))
        safe_offset = max(0, offset)

        rows = fetch_all(
            f"{self._BASE_SELECT} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (safe_limit, safe_offset),
        )
        return [self._row_to_user(row) for row in rows]

    def update(self, user_id: int, **updates: object) -> UserInternal | None:
        """
        Patch-update allowed profile fields (whitelist-enforced).

        Unknown fields raise ValueError. None values are skipped.
        """
        if not updates:
            return self.get_by_id(user_id)

        unknown = set(updates.keys()) - self._PROFILE_UPDATE_WHITELIST
        if unknown:
            raise ValueError(f"Invalid fields for update: {', '.join(sorted(unknown))}")

        filtered: dict[str, object] = {
            key: value for key, value in updates.items() if value is not None
        }
        if not filtered:
            return self.get_by_id(user_id)

        set_clause = ", ".join(f"{field} = %s" for field in filtered)
        sql = (
            f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s"
        )
        execute_write(sql, (*filtered.values(), user_id))

        user = self.get_by_id(user_id)
        if user is None:
            raise RuntimeError(
                f"User {user_id} was updated but could not be retrieved."
            )
        return user

    def set_profile_picture_url(
        self,
        user_id: int,
        profile_picture_url: str | None,
    ) -> UserInternal | None:
        execute_write(
            "UPDATE users SET profile_picture_url = %s, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (profile_picture_url, user_id),
        )
        return self.get_by_id(user_id)

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        return (
            execute_write(
                "UPDATE users SET password_hash = %s, "
                "token_version = token_version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_password_hash, user_id),
            )
            > 0
        )

    def bump_token_version(self, user_id: int) -> bool:
        return (
            execute_write(
                "UPDATE users SET token_version = token_version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (user_id,),
            )
            > 0
        )

    def delete(self, user_id: int) -> bool:
        return execute_write("DELETE FROM users WHERE id = %s", (user_id,)) > 0

    @staticmethod
    def _parse_user_row(row: dict[str, object]) -> UserRow:
        id_value = row.get("id")
        username = row.get("username")
        first_name = row.get("first_name")
        last_name = row.get("last_name")
        date_of_birth = row.get("date_of_birth")
        email = row.get("email")
        password_hash = row.get("password_hash")
        profile_picture_url = row.get("profile_picture_url")
        token_version = row.get("token_version")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        if not isinstance(id_value, int):
            raise ValueError("Invalid user row: 'id' must be int")
        if not isinstance(username, str):
            raise ValueError("Invalid user row: 'username' must be str")
        if not isinstance(first_name, str):
            raise ValueError("Invalid user row: 'first_name' must be str")
        if not isinstance(last_name, str):
            raise ValueError("Invalid user row: 'last_name' must be str")
        if not isinstance(date_of_birth, date):
            raise ValueError("Invalid user row: 'date_of_birth' must be date")
        if not isinstance(email, str):
            raise ValueError("Invalid user row: 'email' must be str")
        if not isinstance(password_hash, str):
            raise ValueError("Invalid user row: 'password_hash' must be str")
        if profile_picture_url is not None and not isinstance(profile_picture_url, str):
            raise ValueError(
                "Invalid user row: 'profile_picture_url' must be str | None"
            )
        if not isinstance(token_version, int):
            raise ValueError("Invalid user row: 'token_version' must be int")
        if not isinstance(created_at, datetime):
            raise ValueError("Invalid user row: 'created_at' must be datetime")
        if not isinstance(updated_at, datetime):
            raise ValueError("Invalid user row: 'updated_at' must be datetime")

        return UserRow(
            id=id_value,
            username=username,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            email=email,
            password_hash=password_hash,
            profile_picture_url=profile_picture_url,
            token_version=token_version,
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _row_to_user(cls, row: dict[str, object]) -> UserInternal:
        user_row = cls._parse_user_row(row)
        return UserInternal.model_validate(user_row)
