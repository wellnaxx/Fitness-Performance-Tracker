import re

from core.errors.validation import InputValidationError

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,16}$")


def validate_username(username: str) -> str:
    """
    Validate username format.

    Rules:
    - 2-16 characters
    - letters, digits, underscore only
    - no leading/trailing spaces
    """

    username = username.strip()

    if not USERNAME_PATTERN.fullmatch(username):
        raise InputValidationError.invalid_username()

    return username


def validate_password_strength(password: str) -> str:
    """Validate password meets security requirements."""
    errors: list[str] = []

    if not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("at least one special character")

    if errors:
        raise InputValidationError.weak_password(errors)

    return password


def validate_meal_type(meal_type: str) -> str:
    """Validate meal type is one of the allowed lowercase values."""
    valid_types = {"breakfast", "lunch", "dinner", "snack"}
    normalized = meal_type.lower().strip()

    if normalized not in valid_types:
        raise InputValidationError.invalid_meal_type(valid_types)

    return normalized
