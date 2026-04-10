from __future__ import annotations

from datetime import date, datetime

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    NonNegativeInt,
    field_validator,
)

from utils.validators import validate_password_strength, validate_username


class UserBase(BaseModel):
    """Base user model with minimal public information."""

    username: str = Field(
        min_length=2,
        max_length=16,
        description="Unique username for the user. ",
        examples=["johndoe", "alice_2024"],
    )

    @field_validator("username")
    @classmethod
    def validate_username_field(cls, v: str) -> str:
        return validate_username(v)


class UserWithEmail(UserBase):
    """User model including email address."""

    email: EmailStr = Field(
        description="Valid email address, must be unique in the system",
        examples=["john@example.com"],
    )  # pip install email-validator


class UserCreate(UserWithEmail):
    """
    Schema for user registration.

    All fields are required. Password must meet complexity requirements:
    - At least 8 characters
    - Contains uppercase letter
    - Contains lowercase letter
    - Contains digit
    - Contains special character
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2005-10-12",
                "password": "SecurePass123!",
            }
        }
    )

    first_name: str = Field(min_length=2, max_length=32)
    last_name: str = Field(min_length=2, max_length=32)
    date_of_birth: date
    password: str = Field(min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength requirements."""
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    """
    Schema for updating user profile.

    All fields are optional. Only provided fields will be updated.
    If password is provided, it must meet complexity requirements.
    """

    first_name: str | None = Field(default=None, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, min_length=2, max_length=32)
    date_of_birth: date | None = None
    email: EmailStr | None = None  # pip install email-validator


class UserLogin(BaseModel):
    """Schema for users to login."""

    email: EmailStr
    password: str


class ChangeUserPassword(BaseModel):
    old_password: str = Field(min_length=8, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength requirements."""
        return validate_password_strength(v)


class ProfilePictureUpdate(BaseModel):
    """Schema for updating a user's profile picture URL."""

    profile_picture_url: AnyHttpUrl | None = Field(
        default=None,
        description="Publicly accessible URL of the profile picture, or null to remove it.",
    )


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences."""

    weight_unit_preference: str | None = Field(
        default=None,
        description="Preferred unit for weight measurements",
        examples=["kg", "lb"],
    )
    measurement_unit_preference: str | None = Field(
        default=None,
        description="Preferred unit for body measurements",
        examples=["cm", "in"],
    )

    @field_validator("weight_unit_preference")
    @classmethod
    def validate_weight_unit_preference(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.lower().strip()
        if normalized not in {"kg", "lb"}:
            raise ValueError("weight_unit_preference must be either 'kg' or 'lb'")
        return normalized

    @field_validator("measurement_unit_preference")
    @classmethod
    def validate_measurement_unit_preference(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.lower().strip()
        if normalized not in {"cm", "in"}:
            raise ValueError("measurement_unit_preference must be either 'cm' or 'in'")
        return normalized


class UserProfile(UserBase):
    """
    Safe user model for the logged-in user.
    """

    id: int
    first_name: str = Field(min_length=2, max_length=32)
    last_name: str = Field(min_length=2, max_length=32)
    date_of_birth: date
    email: EmailStr
    profile_picture_url: AnyHttpUrl | None
    weight_unit_preference: str = Field(
        description="Preferred unit for weight measurements",
        examples=["kg", "lb"],
    )
    measurement_unit_preference: str = Field(
        description="Preferred unit for body measurements",
        examples=["cm", "in"],
    )
    created_at: datetime
    updated_at: datetime


class UserInternal(BaseModel):
    """
    Internal user model for database operations.

    Contains all user data including password hash. Never exposed via API.
    """

    id: int
    username: str = Field(min_length=2, max_length=16)
    first_name: str = Field(min_length=2, max_length=32)
    last_name: str = Field(min_length=2, max_length=32)
    date_of_birth: date
    email: EmailStr
    password_hash: str
    profile_picture_url: AnyHttpUrl | None
    token_version: NonNegativeInt = 0
    weight_unit_preference: str = Field(
        description="Preferred unit for weight measurements",
        examples=["kg", "lb"],
    )
    measurement_unit_preference: str = Field(
        description="Preferred unit for body measurements",
        examples=["cm", "in"],
    )
    created_at: datetime
    updated_at: datetime
