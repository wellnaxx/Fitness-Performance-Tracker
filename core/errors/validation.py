from __future__ import annotations


class InputValidationError(ValueError):
    """Invalid input reported by shared validators and handled by Pydantic."""

    @classmethod
    def invalid_username(cls) -> InputValidationError:
        return cls("Username must be 2-16 characters long and contain only letters, digits, or underscores.")

    @classmethod
    def weak_password(cls, requirements: list[str]) -> InputValidationError:
        return cls(f"Password must contain {', '.join(requirements)}")

    @classmethod
    def invalid_meal_type(cls, valid_types: set[str]) -> InputValidationError:
        return cls(f"meal_type must be one of {valid_types}")
