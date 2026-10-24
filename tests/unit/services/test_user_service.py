"""Authentication, account ownership, retry behavior, and safe profile responses."""

import unittest
from dataclasses import replace
from unittest.mock import call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.repository import UserRepositoryError
from core.errors.user import (
    EmailAlreadyExistsError,
    IdenticalPasswordsError,
    IncorrectOldPasswordError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserCreationError,
    UserDeleteError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from ports.repositories.user_repository import UserRepositoryPort
from schemas.token_schema import RefreshRequest
from schemas.user_schema import ChangeUserPassword, UserCreate, UserLogin, UserProfile, UserUpdate
from services.user_service import UserService
from tests.fixtures import USER_ID, user


class UserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        self.service = UserService(self.repo)
        self.user = user()
        self.registration = UserCreate.model_validate(
            {
                **self.user.model_dump(),
                "password": "Original123!",
            }
        )
        self.repo.username_exists.return_value = False
        self.repo.email_exists.return_value = False
        self.repo.create.return_value = self.user
        self.repo.get_by_email.return_value = self.user
        self.repo.get_by_id.return_value = self.user
        self.repo.update.return_value = self.user
        self.repo.set_profile_picture_url.return_value = self.user
        self.repo.update_password.return_value = True
        self.repo.delete.return_value = True
        self.hash = self.enterContext(patch("services.user_service.hash_password", return_value="new-hash"))
        self.verify = self.enterContext(patch("services.user_service.verify_password", return_value=True))
        self.access = self.enterContext(
            patch("services.user_service.create_access_token", return_value="access")
        )
        self.refresh = self.enterContext(
            patch("services.user_service.create_refresh_token", return_value="refresh")
        )
        self.payload = TokenPayload(str(USER_ID), 1, 2, "token-id", "refresh", "test_user", 2)
        self.decode = self.enterContext(patch("services.user_service.decode_token", return_value=self.payload))

    def assert_safe_profile(self, profile: UserProfile) -> None:
        self.assertEqual(profile.id, USER_ID)
        self.assertEqual(profile.email, self.user.email)
        self.assertNotIn("password_hash", profile.model_dump())
        self.assertNotIn("token_version", profile.model_dump())

    def test_registration_hashes_password_and_returns_safe_profile(self) -> None:
        self.assert_safe_profile(self.service.register_user(self.registration))
        self.repo.username_exists.assert_called_once_with(self.registration.username)
        self.repo.email_exists.assert_called_once_with(self.registration.email)
        self.hash.assert_called_once_with(self.registration.password)
        self.repo.create.assert_called_once_with(self.registration, "new-hash")

    def test_duplicate_username_stops_before_email_check_or_write(self) -> None:
        self.repo.username_exists.return_value = True
        with self.assertRaises(UsernameAlreadyExistsError):
            self.service.register_user(self.registration)
        self.repo.email_exists.assert_not_called()
        self.hash.assert_not_called()
        self.repo.create.assert_not_called()

    def test_duplicate_email_stops_before_hash_or_write(self) -> None:
        self.repo.email_exists.return_value = True
        with self.assertRaises(EmailAlreadyExistsError):
            self.service.register_user(self.registration)
        self.hash.assert_not_called()
        self.repo.create.assert_not_called()

    def test_registration_wraps_repository_failure_and_preserves_cause(self) -> None:
        failure = UserRepositoryError("database unavailable")
        self.repo.create.side_effect = failure
        with self.assertRaises(UserCreationError) as raised:
            self.service.register_user(self.registration)
        self.assertIs(raised.exception.__cause__, failure)

    def test_login_issues_both_tokens_with_current_version(self) -> None:
        data = UserLogin.model_validate({"email": self.user.email, "password": "Original123!"})
        result = self.service.login_user(data)
        self.repo.get_by_email.assert_called_once_with(data.email)
        self.verify.assert_called_once_with(data.password, self.user.password_hash)
        expected = {"user_id": USER_ID, "username": self.user.username, "token_version": 2}
        self.access.assert_called_once_with(expected)
        self.refresh.assert_called_once_with(expected)
        self.assertEqual(
            (result.access_token, result.refresh_token, result.token_type), ("access", "refresh", "bearer")
        )

    def test_login_rejects_missing_user_and_bad_password_with_same_message(self) -> None:
        messages: list[str] = []
        for found in (None, self.user):
            with self.subTest(user_exists=found is not None):
                self.repo.get_by_email.return_value = found
                self.verify.return_value = False
                self.verify.reset_mock()
                with self.assertRaises(InvalidCredentialsError) as raised:
                    self.service.login_user(
                        UserLogin.model_validate(
                            {
                                "email": self.user.email,
                                "password": "wrong",
                            }
                        )
                    )
                messages.append(str(raised.exception))
                if found is None:
                    self.verify.assert_not_called()
                self.access.assert_not_called()
                self.refresh.assert_not_called()
        self.assertEqual(messages[0], messages[1])

    def test_profile_does_not_expose_authentication_fields(self) -> None:
        self.assert_safe_profile(self.service.get_my_profile(self.user))
        self.repo.get_by_id.assert_not_called()

    def test_partial_profile_update_excludes_unspecified_fields(self) -> None:
        self.repo.update.return_value = self.user.model_copy(update={"first_name": "Changed"})
        result = self.service.update_my_profile(self.user, UserUpdate(first_name="Changed"))
        self.assertEqual(result.first_name, "Changed")
        self.assert_safe_profile(result)
        self.repo.update.assert_called_once_with(USER_ID, first_name="Changed")
        self.repo.email_exists.assert_not_called()

    def test_profile_email_change_checks_uniqueness(self) -> None:
        updates = UserUpdate.model_validate({"email": "new@example.com"})
        self.service.update_my_profile(self.user, updates)
        self.repo.email_exists.assert_called_once_with("new@example.com")
        self.repo.update.assert_called_once_with(USER_ID, email="new@example.com")

    def test_unchanged_email_does_not_conflict_with_own_account(self) -> None:
        self.repo.email_exists.return_value = True
        self.service.update_my_profile(self.user, UserUpdate.model_validate({"email": self.user.email}))
        self.repo.email_exists.assert_not_called()
        self.repo.update.assert_called_once_with(USER_ID, email=self.user.email)

    def test_duplicate_profile_email_prevents_write(self) -> None:
        self.repo.email_exists.return_value = True
        with self.assertRaises(EmailAlreadyExistsError):
            self.service.update_my_profile(self.user, UserUpdate.model_validate({"email": "new@example.com"}))
        self.repo.update.assert_not_called()

    def test_empty_and_null_profile_updates_do_not_overwrite_fields(self) -> None:
        for updates in (UserUpdate(), UserUpdate(first_name=None, email=None)):
            with self.subTest(updates=updates):
                self.repo.update.reset_mock()
                self.assert_safe_profile(self.service.update_my_profile(self.user, updates))
                self.repo.update.assert_called_once_with(USER_ID)

    def test_profile_update_of_deleted_user_fails(self) -> None:
        self.repo.update.return_value = None
        with self.assertRaises(UserNotFoundError):
            self.service.update_my_profile(self.user, UserUpdate(first_name="Changed"))

    def test_password_change_verifies_old_password_and_stores_only_hash(self) -> None:
        self.service.change_password(
            self.user,
            ChangeUserPassword(
                old_password="Original123!",
                new_password="Changed123!",
            ),
        )
        self.verify.assert_called_once_with("Original123!", "stored-hash")
        self.hash.assert_called_once_with("Changed123!")
        self.repo.update_password.assert_called_once_with(USER_ID, "new-hash")

    def test_password_retry_is_idempotent_when_new_password_already_matches(self) -> None:
        self.verify.side_effect = [False, True]
        self.service.change_password(
            self.user,
            ChangeUserPassword(
                old_password="Original123!",
                new_password="Changed123!",
            ),
        )
        self.assertEqual(
            self.verify.call_args_list,
            [
                call("Original123!", "stored-hash"),
                call("Changed123!", "stored-hash"),
            ],
        )
        self.hash.assert_not_called()
        self.repo.update_password.assert_not_called()

    def test_wrong_old_password_does_not_change_password(self) -> None:
        self.verify.return_value = False
        with self.assertRaises(IncorrectOldPasswordError):
            self.service.change_password(
                self.user,
                ChangeUserPassword(
                    old_password="Original123!",
                    new_password="Changed123!",
                ),
            )
        self.hash.assert_not_called()
        self.repo.update_password.assert_not_called()

    def test_identical_password_is_rejected(self) -> None:
        with self.assertRaises(IdenticalPasswordsError):
            self.service.change_password(
                self.user,
                ChangeUserPassword(
                    old_password="Original123!",
                    new_password="Original123!",
                ),
            )
        self.hash.assert_not_called()
        self.repo.update_password.assert_not_called()

    def test_password_update_of_deleted_user_fails(self) -> None:
        self.repo.update_password.return_value = False
        with self.assertRaises(UserNotFoundError):
            self.service.change_password(
                self.user,
                ChangeUserPassword(
                    old_password="Original123!",
                    new_password="Changed123!",
                ),
            )

    def test_account_deletion_uses_authenticated_user(self) -> None:
        self.service.delete_my_account(self.user)
        self.repo.get_by_id.assert_called_once_with(USER_ID)
        self.repo.delete.assert_called_once_with(USER_ID)

    def test_missing_account_is_not_deleted(self) -> None:
        self.repo.get_by_id.return_value = None
        with self.assertRaises(UserNotFoundError):
            self.service.delete_my_account(self.user)
        self.repo.delete.assert_not_called()

    def test_blocked_account_deletion_raises_domain_error(self) -> None:
        self.repo.delete.return_value = False
        with self.assertRaises(UserDeleteError):
            self.service.delete_my_account(self.user)

    def test_profile_picture_can_be_set_and_removed(self) -> None:
        for url in ("https://example.com/avatar.png", None):
            with self.subTest(url=url):
                self.repo.set_profile_picture_url.reset_mock()
                self.assert_safe_profile(self.service.update_profile_picture(self.user, url))
                self.repo.set_profile_picture_url.assert_called_once_with(USER_ID, url)

    def test_picture_update_of_deleted_user_fails(self) -> None:
        self.repo.set_profile_picture_url.return_value = None
        with self.assertRaises(UserNotFoundError):
            self.service.update_profile_picture(self.user, None)

    def test_refresh_uses_current_account_details_and_rotates_both_tokens(self) -> None:
        self.decode.return_value = replace(self.payload, username="old_username")
        result = self.service.refresh_access_token(RefreshRequest(refresh_token="incoming"))
        self.decode.assert_called_once_with("incoming", expected_type="refresh")
        self.repo.get_by_id.assert_called_once_with(USER_ID)
        expected = {"user_id": USER_ID, "username": self.user.username, "token_version": 2}
        self.access.assert_called_once_with(expected)
        self.refresh.assert_called_once_with(expected)
        self.assertEqual((result.access_token, result.refresh_token), ("access", "refresh"))

    def test_invalid_refresh_token_never_queries_user_or_issues_tokens(self) -> None:
        for payload in (None, replace(self.payload, sub="not-an-id"), replace(self.payload, sub="")):
            with self.subTest(payload=payload):
                self.decode.return_value = payload
                with self.assertRaises(InvalidRefreshTokenError):
                    self.service.refresh_access_token(RefreshRequest(refresh_token="incoming"))
                self.repo.get_by_id.assert_not_called()
                self.access.assert_not_called()
                self.refresh.assert_not_called()

    def test_deleted_user_cannot_refresh_tokens(self) -> None:
        self.repo.get_by_id.return_value = None
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_access_token(RefreshRequest(refresh_token="incoming"))
        self.access.assert_not_called()
        self.refresh.assert_not_called()

    def test_revoked_refresh_token_never_issues_tokens(self) -> None:
        self.decode.return_value = replace(self.payload, token_version=1)
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_access_token(RefreshRequest(refresh_token="incoming"))
        self.access.assert_not_called()
        self.refresh.assert_not_called()
