"""Normalization and invalid input behavior shared by request schemas."""

import unittest

from core.errors.validation import InputValidationError
from utils.validators import validate_meal_type, validate_password_strength, validate_username


class ValidatorTests(unittest.TestCase):
    def test_username_accepts_boundaries_and_trims_outer_whitespace(self) -> None:
        for value, expected in (("ab", "ab"), ("a" * 16, "a" * 16), (" Test_123 ", "Test_123")):
            with self.subTest(value=value):
                self.assertEqual(validate_username(value), expected)

    def test_username_rejects_invalid_length_characters_and_internal_whitespace(self) -> None:
        for value in ("", " ", "a", "a" * 17, "test user", "test-user", "test.user", "тестер", "a\nb"):
            with self.subTest(value=value), self.assertRaises(InputValidationError):
                validate_username(value)

    def test_strong_password_is_preserved_exactly(self) -> None:
        self.assertEqual(validate_password_strength(" Strong123! "), " Strong123! ")

    def test_password_error_reports_all_missing_requirements(self) -> None:
        with self.assertRaises(InputValidationError) as raised:
            validate_password_strength("")
        for requirement in ("uppercase", "lowercase", "digit", "special character"):
            self.assertIn(requirement, str(raised.exception))

    def test_each_meal_type_is_normalized(self) -> None:
        for value in ("breakfast", "lunch", "dinner", "snack"):
            with self.subTest(value=value):
                self.assertEqual(validate_meal_type(f" {value.upper()} "), value)

    def test_unknown_meal_types_are_rejected(self) -> None:
        for value in ("", " ", "brunch", "breakfast lunch"):
            with self.subTest(value=value), self.assertRaises(InputValidationError):
                validate_meal_type(value)
