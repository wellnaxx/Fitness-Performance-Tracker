"""Registered progress-photo routes, validation, auth, ownership, and error contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.database import DatabaseError
from core.errors.progress_photo import (
    ProgressPhotoCreationError,
    ProgressPhotoDeleteError,
    ProgressPhotoNotFoundError,
    ProgressPhotoUpdateError,
)
from core.errors.repository import ProgressPhotoRepositoryError, ProgressPhotoRowError
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_progress_photo_repository,
    get_progress_photo_service,
    get_user_repository,
)
from main import app
from ports.repositories.progress_photo_repository import ProgressPhotoRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from repositories.progress_photo_repository import ProgressPhotoRepository
from schemas.progress_photo_schema import ProgressPhotoCreate, ProgressPhotoUpdate
from services.progress_photo_service import ProgressPhotoService
from tests.fixtures import PHOTO_ID, TODAY, USER_ID, progress_photo, user
from tests.unit.http.test_exception_handlers import HttpResponse, request

if TYPE_CHECKING:
    from schemas.progress_photo_schema import ProgressPhotoPublic
    from schemas.user_schema import UserInternal


@dataclass(frozen=True)
class RouteCase:
    """A valid request and the service operation it should reach."""

    method: str
    path: str
    service_method: str
    payload: dict[str, object] | None = None
    status: int = 200


class ProgressPhotoRouterTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = user()
        self.photo = progress_photo()
        self.collection = "/progress_photos/"
        self.detail = f"{self.collection}{PHOTO_ID}"
        self.service = create_autospec(ProgressPhotoService, instance=True, spec_set=True)
        for method in ("create", "get_by_id", "update"):
            getattr(self.service, method).return_value = self.photo
        self.service.list_by_user.return_value = [self.photo]
        self.service.delete.return_value = None
        self.enterContext(
            patch.dict(
                app.dependency_overrides,
                {
                    get_current_user: lambda: self.user,
                    get_progress_photo_service: lambda: self.service,
                },
                clear=True,
            )
        )

    def create_payload(self) -> dict[str, object]:
        return {"photo_url": str(self.photo.photo_url), "entry_date": TODAY.isoformat(), "notes": "Front view"}

    def routes(self) -> tuple[RouteCase, ...]:
        return (
            RouteCase("POST", self.collection, "create", self.create_payload(), 201),
            RouteCase("GET", self.detail, "get_by_id"),
            RouteCase("GET", self.collection, "list_by_user"),
            RouteCase("PATCH", self.detail, "update", {"notes": "Side view"}),
            RouteCase("DELETE", self.detail, "delete", status=204),
        )

    def assert_validation_error(self, response: HttpResponse, location: tuple[str | int, ...]) -> None:
        self.assertEqual(response.status, 422)
        payload = cast("dict[str, list[dict[str, object]]]", response.payload)
        self.assertIn(list(location), [error["loc"] for error in payload["detail"]])
        self.assertEqual(self.service.mock_calls, [])

    def use_real_service(self) -> Mock:
        """Keep the real service provider and replace only the repository dependency."""
        del app.dependency_overrides[get_progress_photo_service]
        repo = create_autospec(ProgressPhotoRepositoryPort, instance=True, spec_set=True)
        repo.create.return_value = self.photo
        repo.get_by_user_and_id.return_value = self.photo
        repo.list_by_user.return_value = [self.photo]
        repo.update_owned.return_value = self.photo
        repo.delete_owned.return_value = True
        app.dependency_overrides[get_progress_photo_repository] = lambda: repo
        self.enterContext(patch("services.progress_photo_service.logging.getLogger"))
        return repo

    async def test_all_routes_return_expected_status_models_and_authenticated_arguments(self) -> None:
        expected_calls = (
            call.create(USER_ID, ProgressPhotoCreate.model_validate(self.create_payload())),
            call.get_by_id(USER_ID, PHOTO_ID),
            call.list_by_user(user_id=USER_ID, limit=100, offset=0, date_from=None, date_to=None),
            call.update(USER_ID, PHOTO_ID, ProgressPhotoUpdate(notes="Side view")),
            call.delete(USER_ID, PHOTO_ID),
        )
        for route, expected in zip(self.routes(), expected_calls, strict=True):
            with self.subTest(method=route.method, path=route.path):
                self.service.reset_mock()
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, route.status)
                self.assertEqual(self.service.mock_calls, [expected])
                if route.status == 204:
                    self.assertEqual(response.body, b"")
                    self.assertIsNone(response.payload)
                else:
                    photo = self.photo.model_dump(mode="json")
                    self.assertEqual(
                        response.payload, [photo] if route.service_method == "list_by_user" else photo
                    )
                    self.assertEqual(response.headers["content-type"], "application/json")

    async def test_empty_single_and_multiple_lists_preserve_order_and_array_shape(self) -> None:
        second = self.photo.model_copy(update={"id": PHOTO_ID + 1})
        newer = self.photo.model_copy(update={"id": PHOTO_ID + 2, "entry_date": TODAY + timedelta(days=1)})
        cases: tuple[list[ProgressPhotoPublic], ...] = ([], [self.photo], [newer, second, self.photo])
        for photos in cases:
            with self.subTest(count=len(photos)):
                self.service.list_by_user.return_value = photos
                response = await request(app, self.collection)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [photo.model_dump(mode="json") for photo in photos])

    async def test_inclusive_date_filters_and_reversed_bounds_are_parsed_and_forwarded(self) -> None:
        cases = (
            (f"date_from={TODAY}", TODAY, None),
            (f"date_to={TODAY}", None, TODAY),
            (f"date_from={TODAY}&date_to={TODAY}", TODAY, TODAY),
            (f"date_from={TODAY + timedelta(days=1)}&date_to={TODAY}", TODAY + timedelta(days=1), TODAY),
            ("date_from=0001-01-01&date_to=9999-12-31", date.min, date.max),
            ("date_from=2024-02-29", date(2024, 2, 29), None),
        )
        self.service.list_by_user.return_value = []
        for query, lower, upper in cases:
            with self.subTest(query=query):
                self.service.reset_mock()
                response = await request(app, f"{self.collection}?limit=1&offset=2&{query}")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [])
                self.service.list_by_user.assert_called_once_with(
                    user_id=USER_ID, limit=1, offset=2, date_from=lower, date_to=upper
                )

    async def test_invalid_photo_ids_are_rejected_before_service_calls(self) -> None:
        for method in ("GET", "PATCH", "DELETE"):
            for value in ("0", "-1", "bad", "1.5", "NaN"):
                with self.subTest(method=method, value=value):
                    response = await request(
                        app, f"{self.collection}{value}", method, {} if method == "PATCH" else None
                    )
                    self.assert_validation_error(response, ("path", "photo_id"))

    async def test_invalid_date_query_values_are_422(self) -> None:
        for field in ("date_from", "date_to"):
            for value in ("", "bad", "2026-02-29", "2026-02-30", "2026-13-01", "2026-01-00"):
                with self.subTest(field=field, value=value):
                    response = await request(app, f"{self.collection}?{field}={value}")
                    self.assert_validation_error(response, ("query", field))

    async def test_http_urls_are_normalized_and_other_schemes_and_types_rejected(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            ("http://EXAMPLE.com", True),
            ("https://example.com/p.jpg?view=front#photo", True),
            ("", False),
            ("bad", False),
            ("relative/photo.jpg", False),
            ("ftp://example.com/p.jpg", False),
            ("file:///photo.jpg", False),
            ("data:image/png;base64,abc", False),
            ("javascript:alert(1)", False),
            (123, False),
            (True, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for value, valid in cases:
                with self.subTest(method=method, value=value):
                    self.service.reset_mock()
                    payload: dict[str, object] = (
                        {**self.create_payload(), "photo_url": value}
                        if method == "POST"
                        else {"photo_url": value}
                    )
                    response = await request(app, path, method, payload)
                    if valid:
                        self.assertEqual(response.status, 201 if method == "POST" else 200)
                        if method == "POST":
                            self.service.create.assert_called_once_with(
                                USER_ID, ProgressPhotoCreate.model_validate(payload)
                            )
                        else:
                            self.service.update.assert_called_once_with(
                                USER_ID, PHOTO_ID, ProgressPhotoUpdate.model_validate(payload)
                            )
                    else:
                        self.assert_validation_error(response, ("body", "photo_url"))

    async def test_body_dates_accept_boundaries_and_leap_days_and_reject_invalid_values(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            ("0001-01-01", True),
            ("9999-12-31", True),
            ("2024-02-29", True),
            ((TODAY + timedelta(days=1)).isoformat(), True),
            ("", False),
            ("bad", False),
            ("2026-02-29", False),
            ("2026-13-01", False),
            (True, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for value, valid in cases:
                with self.subTest(method=method, value=value):
                    self.service.reset_mock()
                    payload: dict[str, object] = (
                        {**self.create_payload(), "entry_date": value}
                        if method == "POST"
                        else {"entry_date": value}
                    )
                    response = await request(app, path, method, payload)
                    if valid:
                        self.assertEqual(response.status, 201 if method == "POST" else 200)
                        arguments = getattr(
                            self.service, "create" if method == "POST" else "update"
                        ).call_args.args
                        self.assertEqual(arguments[-1].entry_date, date.fromisoformat(cast("str", value)))
                    else:
                        self.assert_validation_error(response, ("body", "entry_date"))

    async def test_notes_accept_null_empty_unicode_and_maximum_length(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            (None, True),
            ("", True),
            ("Фото", True),
            ("x" * 1000, True),
            ("O'Brien'); DROP TABLE progress_photos; --", True),
            ("x" * 1001, False),
            (123, False),
            (True, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for value, valid in cases:
                with self.subTest(method=method, value=value):
                    self.service.reset_mock()
                    payload: dict[str, object] = (
                        {**self.create_payload(), "notes": value} if method == "POST" else {"notes": value}
                    )
                    response = await request(app, path, method, payload)
                    if valid:
                        self.assertEqual(response.status, 201 if method == "POST" else 200)
                        arguments = getattr(
                            self.service, "create" if method == "POST" else "update"
                        ).call_args.args
                        self.assertEqual(arguments[-1].notes, value)
                    else:
                        self.assert_validation_error(response, ("body", "notes"))

    async def test_create_requires_url_and_date_but_notes_are_optional(self) -> None:
        for field in ("photo_url", "entry_date"):
            for omitted in (True, False):
                payload = self.create_payload()
                if omitted:
                    del payload[field]
                else:
                    payload[field] = None
                with self.subTest(field=field, omitted=omitted):
                    response = await request(app, self.collection, "POST", payload)
                    self.assert_validation_error(response, ("body", field))
        payload = self.create_payload()
        del payload["notes"]
        response = await request(app, self.collection, "POST", payload)
        self.assertEqual(response.status, 201)
        self.service.create.assert_called_once_with(USER_ID, ProgressPhotoCreate.model_validate(payload))

    async def test_updates_accept_empty_null_partial_unchanged_and_full_payloads(self) -> None:
        payloads: tuple[dict[str, object], ...] = (
            {},
            {"photo_url": None, "entry_date": None, "notes": None},
            {"photo_url": str(self.photo.photo_url)},
            {"entry_date": TODAY.isoformat()},
            {"notes": ""},
            {"photo_url": "https://example.com/side.jpg", "entry_date": "2024-02-29", "notes": "Side view"},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.service.reset_mock()
                response = await request(app, self.detail, "PATCH", payload)
                self.assertEqual(response.status, 200)
                self.service.update.assert_called_once_with(
                    USER_ID, PHOTO_ID, ProgressPhotoUpdate.model_validate(payload)
                )

    async def test_malformed_missing_and_nonobject_bodies_are_422(self) -> None:
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for body in (b"", b"{", b"null", b"[]", b"1", b'"text"'):
                with self.subTest(method=method, body=body):
                    response = await request(app, path, method, raw_body=body)
                    self.assertEqual(response.status, 422)
                    self.assertEqual(self.service.mock_calls, [])

    async def test_non_json_content_types_do_not_bypass_body_validation(self) -> None:
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for content_type in ("text/plain", "application/x-www-form-urlencoded"):
                with self.subTest(method=method, content_type=content_type):
                    response = await request(
                        app, path, method, self.create_payload(), {"content-type": content_type}
                    )
                    self.assertEqual(response.status, 422)
                    self.assertEqual(self.service.mock_calls, [])

    async def test_missing_or_wrong_authentication_scheme_blocks_every_route(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_user_repository] = lambda: repo
        for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
            for route in self.routes():
                with (
                    self.subTest(method=route.method, headers=headers),
                    patch("dependencies.auth.decode_token", return_value=None),
                    patch("dependencies.auth.logger"),
                ):
                    response = await request(app, route.path, route.method, route.payload, headers)
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    self.assertEqual(self.service.mock_calls, [])

    async def test_invalid_deleted_revoked_and_malformed_subject_tokens_block_every_route(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(str(USER_ID), 0, 1, "test", "access", "test_user", self.user.token_version)
        cases: tuple[tuple[TokenPayload | None, UserInternal | None], ...] = (
            (None, self.user),
            (TokenPayload("", 0, 1, "test", "access", "test_user", self.user.token_version), self.user),
            (TokenPayload("bad", 0, 1, "test", "access", "test_user", self.user.token_version), self.user),
            (token, None),
            (token, self.user.model_copy(update={"token_version": self.user.token_version + 1})),
        )
        for decoded, current in cases:
            for route in self.routes():
                with (
                    self.subTest(method=route.method, decoded=decoded, current=current),
                    patch("dependencies.auth.decode_token", return_value=decoded),
                    patch("dependencies.auth.logger"),
                ):
                    repo.get_by_id.return_value = current
                    response = await request(
                        app, route.path, route.method, route.payload, {"Authorization": "Bearer private-token"}
                    )
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    self.assertNotIn("private-token", str(response.payload))
                    self.assertEqual(self.service.mock_calls, [])

    async def test_authenticated_owner_and_record_id_cannot_be_overridden_in_query_or_body(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        repo.get_by_id.return_value = self.user
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(str(USER_ID), 0, 1, "test", "access", "test_user", self.user.token_version)
        for route in self.routes():
            with self.subTest(method=route.method), patch("dependencies.auth.decode_token", return_value=token):
                self.service.reset_mock()
                payload = (
                    {**route.payload, "user_id": 999, "id": 999, "created_at": "2000-01-01T00:00:00"}
                    if route.payload is not None
                    else None
                )
                response = await request(
                    app,
                    f"{route.path}?user_id=999&photo_id=999",
                    route.method,
                    payload,
                    {"Authorization": "Bearer valid-token"},
                )
                self.assertEqual(response.status, route.status)
                arguments = getattr(self.service, route.service_method).call_args
                self.assertEqual(
                    arguments.kwargs["user_id"]
                    if route.service_method == "list_by_user"
                    else arguments.args[0],
                    USER_ID,
                )
                if route.path == self.detail:
                    self.assertEqual(arguments.args[1], PHOTO_ID)
                if route.method in {"POST", "PATCH"}:
                    fields = arguments.args[-1].model_dump()
                    self.assertTrue({"user_id", "id", "created_at"}.isdisjoint(fields))

    async def test_service_errors_have_registered_status_codes_and_safe_messages(self) -> None:
        cases = (
            (self.routes()[0], ProgressPhotoCreationError.create_failed(), 500),
            (self.routes()[1], ProgressPhotoNotFoundError.not_found(PHOTO_ID), 404),
            (self.routes()[3], ProgressPhotoUpdateError.update_failed(PHOTO_ID), 500),
            (self.routes()[4], ProgressPhotoDeleteError.delete_failed(PHOTO_ID), 500),
            (self.routes()[3], ProgressPhotoNotFoundError.not_accessible(PHOTO_ID), 404),
            (self.routes()[4], ProgressPhotoNotFoundError.not_accessible(PHOTO_ID), 404),
        )
        for route, error, expected in cases:
            with (
                self.subTest(method=route.method, error=type(error).__name__),
                patch("core.exception_handlers.logger"),
            ):
                self.service.reset_mock(side_effect=True)
                getattr(self.service, route.service_method).side_effect = error
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, expected)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_internal_errors_are_sanitized_on_every_route(self) -> None:
        for route in self.routes():
            for error, detail in (
                (DatabaseError("private SQL"), "Database operation failed."),
                (ProgressPhotoRepositoryError("private query"), "Database operation failed."),
                (ProgressPhotoRowError("private row"), "Database operation failed."),
                (RuntimeError("private failure"), "Internal server error."),
            ):
                with (
                    self.subTest(method=route.method, error=type(error).__name__),
                    patch("core.exception_handlers.logger"),
                ):
                    self.service.reset_mock(side_effect=True)
                    getattr(self.service, route.service_method).side_effect = error
                    response = await request(app, route.path, route.method, route.payload)
                    self.assertEqual(response.status, 500)
                    self.assertEqual(response.payload, {"detail": detail})

    async def test_real_service_provider_uses_authenticated_owner_for_all_operations(self) -> None:
        repo = self.use_real_service()
        expected_calls = (
            [call.create(USER_ID, ProgressPhotoCreate.model_validate(self.create_payload()))],
            [call.get_by_user_and_id(USER_ID, PHOTO_ID)],
            [call.list_by_user(USER_ID, 100, 0, None, None)],
            [
                call.get_by_user_and_id(USER_ID, PHOTO_ID),
                call.update_owned(USER_ID, PHOTO_ID, ProgressPhotoUpdate(notes="Side view")),
            ],
            [call.get_by_user_and_id(USER_ID, PHOTO_ID), call.delete_owned(USER_ID, PHOTO_ID)],
        )
        for route, expected in zip(self.routes(), expected_calls, strict=True):
            with self.subTest(method=route.method):
                repo.reset_mock()
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, route.status)
                self.assertEqual(repo.mock_calls, expected)
                repo.get_by_id.assert_not_called()

    async def test_real_service_rejects_missing_or_unowned_records_before_mutations(self) -> None:
        repo = self.use_real_service()
        repo.get_by_user_and_id.return_value = None
        for method in ("GET", "PATCH", "DELETE"):
            response = await request(app, self.detail, method, {} if method == "PATCH" else None)
            self.assertEqual(response.status, 404)
            self.assertEqual(response.payload, {"detail": str(ProgressPhotoNotFoundError.not_found(PHOTO_ID))})
        repo.update_owned.assert_not_called()
        repo.delete_owned.assert_not_called()
        repo.get_by_id.assert_not_called()

    async def test_real_service_translates_repository_write_failures(self) -> None:
        repo = self.use_real_service()
        for route, operation, error in (
            (self.routes()[0], "create", ProgressPhotoCreationError.create_failed()),
            (self.routes()[3], "update_owned", ProgressPhotoUpdateError.update_failed(PHOTO_ID)),
            (self.routes()[4], "delete_owned", ProgressPhotoDeleteError.delete_failed(PHOTO_ID)),
        ):
            with (
                self.subTest(operation=operation),
                patch.object(
                    repo, operation, side_effect=ProgressPhotoRepositoryError("private SQL and image URL")
                ),
                patch("core.exception_handlers.logger"),
            ):
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_disappearing_records_and_repeated_delete_use_not_found_after_empty_204(self) -> None:
        repo = self.use_real_service()
        repo.update_owned.return_value = None
        response = await request(app, self.detail, "PATCH", {})
        self.assertEqual(response.status, 404)
        repo.delete_owned.return_value = False
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 404)
        repo.delete_owned.return_value = True
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 204)
        self.assertEqual(response.body, b"")
        repo.get_by_user_and_id.return_value = None
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 404)
        self.assertEqual(repo.delete_owned.call_count, 2)

    async def test_repeated_urls_and_dates_are_not_treated_as_conflicts(self) -> None:
        repo = self.use_real_service()
        second = self.photo.model_copy(update={"id": PHOTO_ID + 1})
        repo.create.side_effect = (self.photo, second)
        for photo in (self.photo, second):
            response = await request(app, self.collection, "POST", self.create_payload())
            self.assertEqual(response.status, 201)
            self.assertEqual(response.payload, photo.model_dump(mode="json"))
        repo.get_by_user_and_id.assert_not_called()

    async def test_invalid_response_models_are_sanitized_as_internal_server_errors(self) -> None:
        for route in self.routes()[:-1]:
            with self.subTest(method=route.method, path=route.path), patch("core.exception_handlers.logger"):
                getattr(self.service, route.service_method).return_value = None
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": "Internal server error."})

    def test_repository_and_service_providers_are_typed_and_do_not_open_connections(self) -> None:
        with patch("data.executor.get_connection") as connect:
            repo = get_progress_photo_repository()
            service = get_progress_photo_service(repo)
            self.assertIsInstance(repo, ProgressPhotoRepository)
            self.assertIs(service.progress_photo_repo, repo)
        connect.assert_not_called()

    async def test_openapi_documents_all_routes_auth_validation_and_models(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        for method, path, success in (
            ("post", "/progress_photos/", "201"),
            ("get", "/progress_photos/", "200"),
            ("get", "/progress_photos/{photo_id}", "200"),
            ("patch", "/progress_photos/{photo_id}", "200"),
            ("delete", "/progress_photos/{photo_id}", "204"),
        ):
            with self.subTest(method=method, path=path):
                operation = paths[path][method]
                self.assertEqual(operation["tags"], ["progress_photos"])
                self.assertTrue(operation["security"])
                description = cast("str", operation["description"])
                for section in ("Args:", "Returns:", "Raises:"):
                    self.assertIn(section, description)
                responses = cast("dict[str, dict[str, object]]", operation["responses"])
                self.assertTrue({success, "401", "422", "500"}.issubset(responses))
                if path.endswith("{photo_id}"):
                    self.assertIn("404", responses)
                if method == "post":
                    self.assertNotIn("409", responses)
                if method == "delete":
                    self.assertNotIn("content", responses[success])
                if method in {"post", "patch"}:
                    self.assertTrue(cast("dict[str, object]", operation["requestBody"])["required"])
                params = cast("list[dict[str, object]]", operation.get("parameters", []))
                by_name = {cast("str", param["name"]): param for param in params}
                self.assertNotIn("user_id", by_name)
                if "photo_id" in by_name:
                    self.assertEqual(by_name["photo_id"]["in"], "path")
                    self.assertTrue(by_name["photo_id"]["required"])
                    self.assertEqual(
                        cast("dict[str, object]", by_name["photo_id"]["schema"])["exclusiveMinimum"], 0
                    )
                if method == "get" and path == "/progress_photos/":
                    self.assertEqual(set(by_name), {"limit", "offset", "date_from", "date_to"})
                    for name in ("date_from", "date_to"):
                        schema = cast("dict[str, object]", by_name[name]["schema"])
                        choices = cast("list[dict[str, object]]", schema["anyOf"])
                        self.assertTrue(any(choice.get("format") == "date" for choice in choices))
        components = cast("dict[str, dict[str, dict[str, object]]]", document["components"])
        schemas = components["schemas"]
        self.assertEqual(
            set(cast("list[str]", schemas["ProgressPhotoCreate"]["required"])), {"photo_url", "entry_date"}
        )
        self.assertEqual(
            set(cast("dict[str, object]", schemas["ProgressPhotoUpdate"]["properties"])),
            {"photo_url", "entry_date", "notes"},
        )
