"""Registered body weight routes, request validation, auth, and error contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.body_weight_entry import (
    BodyWeightEntryCreationError,
    BodyWeightEntryDateConflictError,
    BodyWeightEntryNotFoundError,
    BodyWeightEntryUpdateError,
)
from core.errors.database import DatabaseError
from core.errors.repository import (
    BodyWeightEntryDateConflictRepositoryError,
    BodyWeightEntryRepositoryError,
    BodyWeightEntryRowError,
)
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_body_weight_entry_repository,
    get_body_weight_entry_service,
    get_user_repository,
)
from main import app
from ports.repositories.body_weight_entry_repository import BodyWeightEntryRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from repositories.body_weight_entry_repository import BodyWeightEntryRepository
from schemas.body_weight_entry_schema import BodyWeightEntryCreate, BodyWeightEntryUpdate
from services.body_weight_entry_service import BodyWeightEntryService
from tests.fixtures import TODAY, USER_ID, WEIGHT_ENTRY_ID, user, weight_entry
from tests.unit.http.test_exception_handlers import HttpResponse, request

if TYPE_CHECKING:
    from schemas.body_weight_entry_schema import BodyWeightEntryPublic
    from schemas.user_schema import UserInternal


@dataclass(frozen=True)
class RouteCase:
    """A valid request and its service operation."""

    method: str
    path: str
    service_method: str
    payload: dict[str, object] | None = None
    status: int = 200


class BodyWeightEntryRouterTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = user()
        self.entry = weight_entry()
        self.service = create_autospec(BodyWeightEntryService, instance=True, spec_set=True)
        for method in ("create", "get_by_id", "get_by_date", "get_latest", "update"):
            getattr(self.service, method).return_value = self.entry
        self.service.list_by_user.return_value = [self.entry]
        self.service.delete.return_value = None
        overrides = patch.dict(
            app.dependency_overrides,
            {get_current_user: lambda: self.user, get_body_weight_entry_service: lambda: self.service},
            clear=True,
        )
        overrides.start()
        self.addCleanup(overrides.stop)

    def create_payload(self) -> dict[str, object]:
        return {"entry_date": TODAY.isoformat(), "weight": "75.5"}

    def routes(self) -> tuple[RouteCase, ...]:
        return (
            RouteCase("POST", "/body_weight_entries/", "create", self.create_payload(), 201),
            RouteCase("GET", "/body_weight_entries/", "list_by_user"),
            RouteCase("GET", "/body_weight_entries/latest", "get_latest"),
            RouteCase("GET", f"/body_weight_entries/date/{TODAY.isoformat()}", "get_by_date"),
            RouteCase("GET", f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "get_by_id"),
            RouteCase("PATCH", f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "update", {"weight": "76.25"}),
            RouteCase("DELETE", f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "delete", status=204),
        )

    def assert_validation_error(self, response: HttpResponse, location: tuple[str | int, ...]) -> None:
        self.assertEqual(response.status, 422)
        payload = cast("dict[str, list[dict[str, object]]]", response.payload)
        self.assertIn(list(location), [error["loc"] for error in payload["detail"]])
        self.assertEqual(self.service.mock_calls, [])

    def use_real_service(self) -> Mock:
        """Keep FastAPI's service provider and substitute only its repository dependency."""
        del app.dependency_overrides[get_body_weight_entry_service]
        repo = create_autospec(BodyWeightEntryRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_body_weight_entry_repository] = lambda: repo
        return repo

    async def test_all_endpoints_return_expected_models_and_forward_authenticated_user(self) -> None:
        expected_calls = (
            call.create(USER_ID, BodyWeightEntryCreate.model_validate(self.create_payload())),
            call.list_by_user(user_id=USER_ID, limit=100, offset=0, date_from=None, date_to=None),
            call.get_latest(USER_ID),
            call.get_by_date(USER_ID, TODAY),
            call.get_by_id(USER_ID, WEIGHT_ENTRY_ID),
            call.update(USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate.model_validate({"weight": "76.25"})),
            call.delete(USER_ID, WEIGHT_ENTRY_ID),
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
                    item = self.entry.model_dump(mode="json")
                    self.assertEqual(
                        response.payload, [item] if route.service_method == "list_by_user" else item
                    )
                    self.assertEqual(response.headers["content-type"], "application/json")

    async def test_empty_and_nonempty_lists_preserve_order_and_array_shape(self) -> None:
        pages: tuple[list[BodyWeightEntryPublic], ...] = (
            [],
            [self.entry.model_copy(update={"id": 99, "entry_date": TODAY + timedelta(days=1)}), self.entry],
        )
        for entries in pages:
            self.service.list_by_user.return_value = entries
            response = await request(app, "/body_weight_entries/")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload, [entry.model_dump(mode="json") for entry in entries])

    async def test_optional_date_filters_are_parsed_and_reversed_ranges_are_forwarded(self) -> None:
        self.service.list_by_user.return_value = []
        for query, lower, upper in (
            (f"date_from={TODAY}", TODAY, None),
            (f"date_to={TODAY}", None, TODAY),
            (f"date_from={TODAY}&date_to={TODAY}", TODAY, TODAY),
            (f"date_from={TODAY + timedelta(days=1)}&date_to={TODAY}", TODAY + timedelta(days=1), TODAY),
        ):
            with self.subTest(query=query):
                self.service.reset_mock()
                response = await request(app, f"/body_weight_entries/?limit=1&offset=2&{query}")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [])
                self.service.list_by_user.assert_called_once_with(
                    user_id=USER_ID, limit=1, offset=2, date_from=lower, date_to=upper
                )

    async def test_invalid_path_ids_are_422_before_service_calls(self) -> None:
        for method in ("GET", "PATCH", "DELETE"):
            for value in ("0", "-1", "bad", "1.5"):
                with self.subTest(method=method, value=value):
                    response = await request(
                        app, f"/body_weight_entries/{value}", method, {} if method == "PATCH" else None
                    )
                    self.assert_validation_error(response, ("path", "entry_id"))

    async def test_minimum_id_is_valid_and_query_parameters_cannot_replace_it(self) -> None:
        for method, operation in (("GET", "get_by_id"), ("PATCH", "update"), ("DELETE", "delete")):
            with self.subTest(method=method):
                self.service.reset_mock()
                response = await request(
                    app, "/body_weight_entries/1?entry_id=999", method, {} if method == "PATCH" else None
                )
                self.assertIn(response.status, (200, 204))
                self.assertEqual(getattr(self.service, operation).call_args.args[:2], (USER_ID, 1))

    async def test_dates_reject_invalid_values_and_accept_a_leap_day(self) -> None:
        for value in ("bad", "2026-02-30", "2026-13-01", "2025-02-29"):
            with self.subTest(value=value):
                response = await request(app, f"/body_weight_entries/date/{value}")
                self.assert_validation_error(response, ("path", "entry_date"))
                for field in ("date_from", "date_to"):
                    response = await request(app, f"/body_weight_entries/?{field}={value}")
                    self.assert_validation_error(response, ("query", field))
                for method, path in (
                    ("POST", "/body_weight_entries/"),
                    ("PATCH", f"/body_weight_entries/{WEIGHT_ENTRY_ID}"),
                ):
                    response = await request(app, path, method, {"entry_date": value, "weight": "75.5"})
                    self.assert_validation_error(response, ("body", "entry_date"))
        for field in ("date_from", "date_to"):
            response = await request(app, f"/body_weight_entries/?{field}=")
            self.assert_validation_error(response, ("query", field))
        response = await request(app, "/body_weight_entries/date/2024-02-29")
        self.assertEqual(response.status, 200)
        self.service.get_by_date.assert_called_once_with(USER_ID, date(2024, 2, 29))

    async def test_weight_validation_accepts_storable_values_and_rejects_invalid_values(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            ("0.01", True),
            (1, True),
            (75.5, True),
            ("75.5000", True),
            ("999.99", True),
            (0, False),
            (-1, False),
            ("bad", False),
            ("NaN", False),
            ("Infinity", False),
            ("-Infinity", False),
            ("1000", False),
            ("75.125", False),
            ("0.001", False),
            (True, False),
            (False, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for method in ("POST", "PATCH"):
            path = "/body_weight_entries/" if method == "POST" else f"/body_weight_entries/{WEIGHT_ENTRY_ID}"
            for value, valid in cases:
                with self.subTest(method=method, value=value):
                    self.service.reset_mock()
                    payload: dict[str, object] = {"entry_date": TODAY.isoformat(), "weight": value}
                    response = await request(app, path, method, payload)
                    if valid:
                        self.assertEqual(response.status, 201 if method == "POST" else 200)
                        if method == "POST":
                            self.service.create.assert_called_once_with(
                                USER_ID, BodyWeightEntryCreate.model_validate(payload)
                            )
                        else:
                            self.service.update.assert_called_once_with(
                                USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate.model_validate(payload)
                            )
                    else:
                        self.assert_validation_error(response, ("body", "weight"))

    async def test_create_requires_both_weight_and_a_valid_date(self) -> None:
        cases: tuple[tuple[dict[str, object], str], ...] = (
            ({"weight": "75.5"}, "entry_date"),
            ({"entry_date": None, "weight": "75.5"}, "entry_date"),
            ({"entry_date": "bad", "weight": "75.5"}, "entry_date"),
            ({"entry_date": TODAY.isoformat()}, "weight"),
            ({"entry_date": TODAY.isoformat(), "weight": None}, "weight"),
        )
        for payload, field in cases:
            with self.subTest(payload=payload):
                response = await request(app, "/body_weight_entries/", "POST", payload)
                self.assert_validation_error(response, ("body", field))

    async def test_update_accepts_empty_null_same_date_and_full_payloads(self) -> None:
        payloads: tuple[dict[str, object], ...] = (
            {},
            {"entry_date": None, "weight": None},
            {"entry_date": TODAY.isoformat()},
            {"weight": "0.01"},
            {"weight": "76.25", "entry_date": (TODAY + timedelta(days=1)).isoformat()},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.service.reset_mock()
                response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "PATCH", payload)
                self.assertEqual(response.status, 200)
                self.service.update.assert_called_once_with(
                    USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate.model_validate(payload)
                )

    async def test_write_endpoints_reject_missing_malformed_and_nonobject_bodies(self) -> None:
        for method, path in (
            ("POST", "/body_weight_entries/"),
            ("PATCH", f"/body_weight_entries/{WEIGHT_ENTRY_ID}"),
        ):
            for body in (b"", b"null", b"{", b"[]", b'"text"', b"1"):
                with self.subTest(method=method, body=body):
                    response = await request(app, path, method, raw_body=body)
                    self.assertEqual(response.status, 422)
                    self.assertEqual(self.service.mock_calls, [])

    async def test_all_endpoints_require_authentication(self) -> None:
        del app.dependency_overrides[get_current_user]
        for route in self.routes():
            for headers in ({}, {"Authorization": "Basic credentials"}):
                with self.subTest(method=route.method, path=route.path):
                    response = await request(app, route.path, route.method, route.payload, headers)
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    self.assertEqual(self.service.mock_calls, [])

    async def test_invalid_deleted_and_revoked_tokens_block_every_endpoint(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(str(USER_ID), 0, 1, "test", "access", "test_user", self.user.token_version)
        cases: tuple[tuple[TokenPayload | None, UserInternal | None, bool], ...] = (
            (None, self.user, False),
            (TokenPayload("", 0, 1, "test", "access", "test_user", self.user.token_version), self.user, False),
            (
                TokenPayload("bad", 0, 1, "test", "access", "test_user", self.user.token_version),
                self.user,
                False,
            ),
            (token, None, True),
            (token, self.user.model_copy(update={"token_version": self.user.token_version + 1}), True),
        )
        for decoded, current_user, lookup_expected in cases:
            for route in self.routes():
                with (
                    self.subTest(path=route.path, decoded=decoded, user=current_user),
                    patch("dependencies.auth.decode_token", return_value=decoded),
                    patch("dependencies.auth.logger"),
                ):
                    repo.reset_mock()
                    repo.get_by_id.return_value = current_user
                    response = await request(
                        app,
                        route.path,
                        route.method,
                        route.payload,
                        {"Authorization": "Bearer sentinel-secret-token"},
                    )
                    self.assertEqual(response.status, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
                    self.assertNotIn("sentinel-secret-token", str(response.payload))
                    self.assertEqual(self.service.mock_calls, [])
                    if lookup_expected:
                        repo.get_by_id.assert_called_once_with(USER_ID)
                    else:
                        repo.get_by_id.assert_not_called()

    async def test_authenticated_user_cannot_be_overridden_in_query_or_body(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        repo.get_by_id.return_value = self.user
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(str(USER_ID), 0, 1, "test", "access", "test_user", self.user.token_version)
        for route in self.routes():
            with (
                self.subTest(method=route.method, path=route.path),
                patch("dependencies.auth.decode_token", return_value=token),
            ):
                self.service.reset_mock()
                payload = {**route.payload, "user_id": 999} if route.payload is not None else None
                response = await request(
                    app, f"{route.path}?user_id=999", route.method, payload, {"Authorization": "Bearer token"}
                )
                self.assertEqual(response.status, route.status)
                args = getattr(self.service, route.service_method).call_args
                actual_user = args.kwargs["user_id"] if route.service_method == "list_by_user" else args.args[0]
                self.assertEqual(actual_user, USER_ID)

    async def test_domain_errors_keep_registered_statuses_and_safe_messages(self) -> None:
        routes = self.routes()
        cases = (
            (routes[0], BodyWeightEntryCreationError.create_failed(), 500),
            (routes[0], BodyWeightEntryDateConflictError.already_exists(TODAY), 409),
            (routes[2], BodyWeightEntryNotFoundError.no_entries(USER_ID), 404),
            (routes[3], BodyWeightEntryNotFoundError.not_found_by_date(TODAY), 404),
            (routes[4], BodyWeightEntryNotFoundError.not_found(WEIGHT_ENTRY_ID), 404),
            (routes[5], BodyWeightEntryNotFoundError.not_accessible(WEIGHT_ENTRY_ID), 404),
            (routes[5], BodyWeightEntryDateConflictError.already_exists(TODAY), 409),
            (routes[5], BodyWeightEntryUpdateError.update_failed(WEIGHT_ENTRY_ID), 500),
            (routes[6], BodyWeightEntryNotFoundError.not_accessible(WEIGHT_ENTRY_ID), 404),
        )
        for route, error, status_code in cases:
            with (
                self.subTest(method=route.method, error=type(error).__name__),
                patch("core.exception_handlers.logger"),
            ):
                self.service.reset_mock(side_effect=True)
                getattr(self.service, route.service_method).side_effect = error
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, status_code)
                self.assertEqual(response.payload, {"detail": str(error)})

    async def test_internal_failures_are_sanitized_on_every_endpoint(self) -> None:
        for route in self.routes():
            for error, detail in (
                (DatabaseError("private SQL"), "Database operation failed."),
                (BodyWeightEntryRepositoryError("private query"), "Database operation failed."),
                (BodyWeightEntryRowError("private row"), "Database operation failed."),
                (RuntimeError("private failure"), "Internal server error."),
            ):
                with (
                    self.subTest(method=route.method, path=route.path, error=type(error).__name__),
                    patch("core.exception_handlers.logger"),
                ):
                    self.service.reset_mock(side_effect=True)
                    getattr(self.service, route.service_method).side_effect = error
                    response = await request(app, route.path, route.method, route.payload)
                    self.assertEqual(response.status, 500)
                    self.assertEqual(response.payload, {"detail": detail})
                    self.assertNotIn("private", str(response.payload))

    async def test_real_service_provider_checks_ownership_and_translates_racing_conflicts(self) -> None:
        repo = self.use_real_service()
        repo.get_by_user_and_id.return_value = self.entry
        response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}")
        self.assertEqual(response.status, 200)
        repo.get_by_user_and_id.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID)
        repo.get_by_id.assert_not_called()
        repo.get_by_user_and_id.return_value = None
        for method in ("PATCH", "DELETE"):
            response = await request(
                app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", method, {} if method == "PATCH" else None
            )
            self.assertEqual(response.status, 404)
        repo.update_owned.assert_not_called()
        repo.delete_owned.assert_not_called()
        repo.get_by_user_and_date.return_value = self.entry
        response = await request(app, "/body_weight_entries/", "POST", self.create_payload())
        self.assertEqual(response.status, 409)
        repo.create.assert_not_called()
        repo.get_by_user_and_date.return_value = None
        repo.create.side_effect = BodyWeightEntryDateConflictRepositoryError(TODAY)
        response = await request(app, "/body_weight_entries/", "POST", self.create_payload())
        self.assertEqual(response.status, 409)
        self.assertEqual(
            response.payload, {"detail": str(BodyWeightEntryDateConflictError.already_exists(TODAY))}
        )

    async def test_real_service_update_conflicts_return_409_before_or_during_persistence(self) -> None:
        repo = self.use_real_service()
        new_date = TODAY + timedelta(days=1)
        repo.get_by_user_and_id.return_value = self.entry
        repo.get_by_user_and_date.return_value = self.entry.model_copy(
            update={"id": 99, "entry_date": new_date}
        )
        payload: dict[str, object] = {"entry_date": new_date.isoformat(), "weight": "76.25"}
        response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "PATCH", payload)
        self.assertEqual(response.status, 409)
        repo.update_owned.assert_not_called()
        repo.get_by_user_and_date.return_value = None
        conflict = BodyWeightEntryDateConflictRepositoryError(new_date)
        conflict.__cause__ = DatabaseError("private SQL and weight values")
        repo.update_owned.side_effect = conflict
        response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "PATCH", payload)
        self.assertEqual(response.status, 409)
        self.assertEqual(
            response.payload, {"detail": str(BodyWeightEntryDateConflictError.already_exists(new_date))}
        )
        self.assertNotIn("private", str(response.payload))
        repo.update_owned.assert_called_once_with(
            USER_ID, WEIGHT_ENTRY_ID, BodyWeightEntryUpdate.model_validate(payload)
        )

    async def test_repeated_delete_returns_404_after_a_successful_empty_204(self) -> None:
        repo = self.use_real_service()
        repo.get_by_user_and_id.side_effect = (self.entry, None)
        repo.delete_owned.return_value = True
        response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "DELETE")
        self.assertEqual(response.status, 204)
        self.assertEqual(response.body, b"")
        response = await request(app, f"/body_weight_entries/{WEIGHT_ENTRY_ID}", "DELETE")
        self.assertEqual(response.status, 404)
        repo.delete_owned.assert_called_once_with(USER_ID, WEIGHT_ENTRY_ID)

    async def test_invalid_service_response_models_return_sanitized_500(self) -> None:
        for route in self.routes()[:-1]:
            with self.subTest(method=route.method, path=route.path), patch("core.exception_handlers.logger"):
                self.service.reset_mock()
                getattr(self.service, route.service_method).return_value = None
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": "Internal server error."})

    def test_repository_provider_is_typed_and_does_not_open_a_connection(self) -> None:
        with patch("data.executor.get_connection") as connect:
            self.assertIsInstance(get_body_weight_entry_repository(), BodyWeightEntryRepository)
        connect.assert_not_called()

    async def test_openapi_documents_routes_security_parameters_and_responses(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        for method, path, status_code in (
            ("post", "/body_weight_entries/", "201"),
            ("get", "/body_weight_entries/", "200"),
            ("get", "/body_weight_entries/latest", "200"),
            ("get", "/body_weight_entries/date/{entry_date}", "200"),
            ("get", "/body_weight_entries/{entry_id}", "200"),
            ("patch", "/body_weight_entries/{entry_id}", "200"),
            ("delete", "/body_weight_entries/{entry_id}", "204"),
        ):
            with self.subTest(method=method, path=path):
                operation = paths[path][method]
                self.assertEqual(operation["tags"], ["body_weight_entries"])
                if method == "post":
                    self.assertTrue(
                        cast("str", operation["operationId"]).startswith("create_body_weight_entry_")
                    )
                description = cast("str", operation["description"])
                for section in ("Args:", "Returns:", "Raises:"):
                    self.assertIn(section, description)
                self.assertTrue(operation["security"])
                responses = cast("dict[str, dict[str, object]]", operation["responses"])
                self.assertTrue({status_code, "401", "500"}.issubset(responses))
                if method in ("post", "patch"):
                    self.assertIn("409", responses)
                    self.assertTrue(cast("dict[str, object]", operation["requestBody"])["required"])
                if path.endswith(("/latest", "{entry_date}", "{entry_id}")):
                    self.assertIn("404", responses)
                if method == "delete":
                    self.assertNotIn("content", responses[status_code])
                parameters = cast("list[dict[str, object]]", operation.get("parameters", []))
                params = {cast("str", parameter["name"]): parameter for parameter in parameters}
                self.assertNotIn("user_id", params)
                if "entry_id" in params:
                    self.assertEqual(params["entry_id"]["in"], "path")
                    self.assertEqual(
                        cast("dict[str, object]", params["entry_id"]["schema"])["exclusiveMinimum"], 0
                    )
                if "entry_date" in params:
                    self.assertEqual(params["entry_date"]["in"], "path")
                    self.assertEqual(
                        cast("dict[str, object]", params["entry_date"]["schema"])["format"], "date"
                    )
                if method == "get" and path == "/body_weight_entries/":
                    self.assertEqual(set(params), {"limit", "offset", "date_from", "date_to"})
                    self.assertTrue(all(parameter["in"] == "query" for parameter in params.values()))
                    self.assertNotIn("requestBody", operation)
