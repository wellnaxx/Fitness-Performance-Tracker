"""Real JWT signing/verification with an isolated key and controlled creation time."""

import unittest
from dataclasses import asdict
from datetime import UTC, datetime
from unittest.mock import patch

from jose import jwt

from auth.jwt_handler import (
    TokenInput,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from core.config import AuthConfig


class JwtHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AuthConfig("unit-test-secret-never-used-in-production", "HS256", 15, 7)
        self.enterContext(patch("auth.jwt_handler.get_auth_config", return_value=self.config))
        self.data: TokenInput = {"user_id": 7, "username": "tester", "token_version": 2}
        self.claims: dict[str, object] = {
            "sub": "7",
            "iat": 1,
            "exp": 4102444800,
            "jti": "test-id",
            "type": "access",
            "username": "tester",
            "token_version": 2,
        }

    def sign(self, claims: dict[str, object]) -> str:
        return jwt.encode(claims, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)

    def test_access_and_refresh_tokens_round_trip_with_expected_claims_and_lifetimes(self) -> None:
        now = datetime.now(UTC).replace(microsecond=0)
        with patch("auth.jwt_handler.datetime") as clock:
            clock.now.return_value = now
            access = create_access_token(self.data)
            refresh = create_refresh_token(self.data)
        for token, token_type, lifetime in ((access, "access", 900), (refresh, "refresh", 604800)):
            with self.subTest(token_type=token_type):
                payload = decode_token(token, expected_type="access" if token_type == "access" else "refresh")
                if payload is None:
                    self.fail("Freshly signed token was rejected")
                self.assertEqual(payload.sub, "7")
                self.assertEqual(payload.username, "tester")
                self.assertEqual(payload.token_version, 2)
                self.assertEqual(payload.type, token_type)
                self.assertEqual(payload.iat, int(now.timestamp()))
                self.assertEqual(payload.exp - payload.iat, lifetime)
                self.assertTrue(payload.jti)

    def test_each_issued_token_has_a_unique_id(self) -> None:
        first = decode_token(create_access_token(self.data))
        second = decode_token(create_access_token(self.data))
        if first is None or second is None:
            self.fail("Freshly signed tokens were rejected")
        self.assertNotEqual(first.jti, second.jti)

    def test_access_and_refresh_types_cannot_be_interchanged(self) -> None:
        self.assertIsNone(decode_token(create_access_token(self.data), expected_type="refresh"))
        self.assertIsNone(decode_token(create_refresh_token(self.data), expected_type="access"))

    def test_expired_token_is_rejected(self) -> None:
        self.assertIsNone(decode_token(self.sign({**self.claims, "exp": 2})))

    def test_wrong_signing_key_is_rejected(self) -> None:
        token = jwt.encode(self.claims, "different-secret", algorithm="HS256")
        self.assertIsNone(decode_token(token))

    def test_unapproved_signing_algorithm_is_rejected(self) -> None:
        token = jwt.encode(self.claims, self.config.jwt_secret, algorithm="HS384")
        self.assertIsNone(decode_token(token))

    def test_malformed_and_tampered_tokens_are_rejected(self) -> None:
        token = self.sign(self.claims)
        header, payload, signature = token.split(".")
        changed_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        for invalid in ("", "not-a-jwt", "a.b.c", f"{header}.{payload}.{changed_signature}"):
            with self.subTest(token=invalid):
                self.assertIsNone(decode_token(invalid))

    def test_every_required_claim_must_be_present(self) -> None:
        for field in self.claims:
            with self.subTest(field=field):
                claims = {key: value for key, value in self.claims.items() if key != field}
                self.assertIsNone(TokenPayload.from_dict(claims))
                self.assertIsNone(decode_token(self.sign(claims)))

    def test_wrong_claim_types_and_unknown_token_type_are_rejected(self) -> None:
        invalid_values: dict[str, object] = {
            "sub": 7,
            "iat": "yesterday",
            "exp": "tomorrow",
            "jti": 123,
            "type": "password_reset",
            "username": ["tester"],
            "token_version": "2",
        }
        for field, value in invalid_values.items():
            with self.subTest(field=field):
                claims = {**self.claims, field: value}
                self.assertIsNone(TokenPayload.from_dict(claims))
                self.assertIsNone(decode_token(self.sign(claims)))

    def test_valid_payload_ignores_unrelated_claims(self) -> None:
        payload = TokenPayload.from_dict({**self.claims, "extra": "ignored"})
        if payload is None:
            self.fail("Valid payload was rejected")
        self.assertEqual(asdict(payload), self.claims)

    def test_null_and_container_claim_values_are_rejected_without_raising(self) -> None:
        invalid_values: tuple[object, ...] = (None, [], {})
        for field in self.claims:
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    self.assertIsNone(decode_token(self.sign({**self.claims, field: value})))
