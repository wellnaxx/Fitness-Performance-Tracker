"""Exercise the real password hashing boundary independently of service mocks."""

import unittest

from auth.hashing import hash_password, verify_password


class PasswordHashingTests(unittest.TestCase):
    def test_passwords_round_trip_and_wrong_passwords_are_rejected(self) -> None:
        for password in ("Strong123!", "密碼123!"):
            with self.subTest(password=password):
                hashed = hash_password(password)
                self.assertNotEqual(hashed, password)
                self.assertTrue(verify_password(password, hashed))
                self.assertFalse(verify_password(password + "wrong", hashed))

    def test_same_password_gets_different_salted_hashes(self) -> None:
        first = hash_password("Strong123!")
        second = hash_password("Strong123!")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("Strong123!", first))
        self.assertTrue(verify_password("Strong123!", second))

    def test_malformed_stored_hash_is_reported(self) -> None:
        for hashed in ("", "not-a-bcrypt-hash"):
            with self.subTest(hashed=hashed), self.assertRaises(ValueError):
                verify_password("Strong123!", hashed)
