"""Registered body measurement routes, request validation, auth, and error contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.body_measurement import (
    BodyMeasurementCreationError,
    BodyMeasurementDateConflictError,
    BodyMeasurementNotFoundError,
    BodyMeasurementUpdateError,
)
from core.errors.database import DatabaseError
from core.errors.repository import BodyMeasurementDateConflictRepositoryError, BodyMeasurementRowError
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_body_measurement_repository,
    get_body_measurement_service,
    get_user_repository,
)
from main import app
from ports.repositories.body_measurement_repository import BodyMeasurementRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from repositories.body_measurement_repository import BodyMeasurementRepository
from schemas.body_measurement_schema import BodyMeasurementCreate, BodyMeasurementUpdate
from services.body_measurement_service import BodyMeasurementService
from tests.fixtures import MEASUREMENT_ID, TODAY, USER_ID, measurement, user
from tests.unit.http.test_exception_handlers import HttpResponse, request

if TYPE_CHECKING:
    from schemas.body_measurement_schema import BodyMeasurementPublic


@dataclass(frozen=True)
class RouteCase:
    """A valid request and its service operation."""

    method: str
    path: str
    service_method: str
    payload: dict[str, object] | None = None
    status: int = 200


class BodyMeasurementRouterTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = user()
        self.entry = measurement()
        self.service = create_autospec(BodyMeasurementService, instance=True, spec_set=True)
        for method in ("create", "get_by_id", "get_by_date", "get_latest", "update"):
            getattr(self.service, method).return_value = self.entry
        self.service.list_by_user.return_value = [self.entry]
        self.service.delete.return_value = None
        overrides = patch.dict(
            app.dependency_overrides,
            {get_current_user: lambda: self.user, get_body_measurement_service: lambda: self.service},
            clear=True,
        )
        overrides.start()
        self.addCleanup(overrides.stop)

    def create_payload(self) -> dict[str, object]:
        return {"entry_date": TODAY.isoformat(), "waist": "80.5"}

    def routes(self) -> tuple[RouteCase, ...]:
        return (
            RouteCase("POST", "/body_measurements/", "create", self.create_payload(), 201),
            RouteCase("GET", "/body_measurements/", "list_by_user"),
            RouteCase("GET", "/body_measurements/latest", "get_latest"),
            RouteCase("GET", f"/body_measurements/date/{TODAY.isoformat()}", "get_by_date"),
            RouteCase("GET", f"/body_measurements/{MEASUREMENT_ID}", "get_by_id"),
            RouteCase("PATCH", f"/body_measurements/{MEASUREMENT_ID}", "update", {"notes": ""}),
            RouteCase("DELETE", f"/body_measurements/{MEASUREMENT_ID}", "delete", status=204),
        )

    def assert_validation_error(self, response: HttpResponse, location: tuple[str | int, ...]) -> None:
        self.assertEqual(response.status, 422)
        payload = cast("dict[str, list[dict[str, object]]]", response.payload)
        self.assertIn(list(location), [error["loc"] for error in payload["detail"]])
        self.assertEqual(self.service.mock_calls, [])

    async def test_all_endpoints_return_expected_models_and_forward_authenticated_user(self) -> None:
        expected_calls = (
            call.create(USER_ID, BodyMeasurementCreate.model_validate(self.create_payload())),
            call.list_by_user(user_id=USER_ID, limit=100, offset=0, date_from=None, date_to=None),
            call.get_latest(USER_ID),
            call.get_by_date(USER_ID, TODAY),
            call.get_by_id(USER_ID, MEASUREMENT_ID),
            call.update(USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate(notes="")),
            call.delete(USER_ID, MEASUREMENT_ID),
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
        pages: tuple[list[BodyMeasurementPublic], ...] = (
            [],
            [self.entry.model_copy(update={"id": 99, "entry_date": TODAY + timedelta(days=1)}), self.entry],
        )
        for entries in pages:
            self.service.list_by_user.return_value = entries
            response = await request(app, "/body_measurements/")
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
                response = await request(app, f"/body_measurements/?limit=1&offset=2&{query}")
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
                        app, f"/body_measurements/{value}", method, {} if method == "PATCH" else None
                    )
                    self.assert_validation_error(response, ("path", "entry_id"))

    async def test_minimum_id_is_valid_and_query_parameters_cannot_replace_it(self) -> None:
        for method, operation in (("GET", "get_by_id"), ("PATCH", "update"), ("DELETE", "delete")):
            with self.subTest(method=method):
                self.service.reset_mock()
                response = await request(
                    app, "/body_measurements/1?entry_id=999", method, {} if method == "PATCH" else None
                )
                self.assertIn(response.status, (200, 204))
                self.assertEqual(getattr(self.service, operation).call_args.args[:2], (USER_ID, 1))

    async def test_dates_reject_invalid_values_and_accept_a_leap_day(self) -> None:
        for value in ("bad", "2026-02-30", "2026-13-01"):
            with self.subTest(value=value):
                response = await request(app, f"/body_measurements/date/{value}")
                self.assert_validation_error(response, ("path", "entry_date"))
                for field in ("date_from", "date_to"):
                    response = await request(app, f"/body_measurements/?{field}={value}")
                    self.assert_validation_error(response, ("query", field))
        response = await request(app, "/body_measurements/date/2024-02-29")
        self.assertEqual(response.status, 200)
        self.service.get_by_date.assert_called_once_with(USER_ID, date(2024, 2, 29))

    async def test_every_measurement_accepts_positive_values_and_rejects_invalid_ones(self) -> None:
        fields = tuple(
            field for field in BodyMeasurementUpdate.model_fields if field not in {"entry_date", "notes"}
        )
        for method in ("POST", "PATCH"):
            path = "/body_measurements/" if method == "POST" else f"/body_measurements/{MEASUREMENT_ID}"
            for field in fields:
                for value in ("0.01", 0, -1, "bad", "NaN", "Infinity"):
                    with self.subTest(method=method, field=field, value=value):
                        self.service.reset_mock()
                        payload: dict[str, object] = {"entry_date": TODAY.isoformat(), field: value}
                        response = await request(app, path, method, payload)
                        if value == "0.01":
                            self.assertIn(response.status, (200, 201))
                        else:
                            self.assert_validation_error(response, ("body", field))

    async def test_create_requires_a_date_and_at_least_one_measurement(self) -> None:
        invalid_dates: tuple[dict[str, object], ...] = (
            {"waist": "80"},
            {"entry_date": None, "waist": "80"},
            {"entry_date": "bad", "waist": "80"},
        )
        for payload in invalid_dates:
            response = await request(app, "/body_measurements/", "POST", payload)
            self.assert_validation_error(response, ("body", "entry_date"))
        missing_measurements: tuple[dict[str, object], ...] = (
            {"entry_date": TODAY.isoformat()},
            {"entry_date": TODAY.isoformat(), "notes": "only notes"},
            {"entry_date": TODAY.isoformat(), "waist": None},
        )
        for payload in missing_measurements:
            response = await request(app, "/body_measurements/", "POST", payload)
            self.assert_validation_error(response, ("body",))

    async def test_update_accepts_empty_null_same_date_and_full_payloads(self) -> None:
        full_payload: dict[str, object] = {
            field: "0.01"
            for field in BodyMeasurementUpdate.model_fields
            if field not in {"entry_date", "notes"}
        }
        full_payload.update({"entry_date": TODAY.isoformat(), "notes": ""})
        payloads: tuple[dict[str, object], ...] = (
            {},
            {"entry_date": None, "waist": None, "notes": None},
            {"entry_date": TODAY.isoformat()},
            {"waist": "0.01", "notes": ""},
            full_payload,
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.service.reset_mock()
                response = await request(app, f"/body_measurements/{MEASUREMENT_ID}", "PATCH", payload)
                self.assertEqual(response.status, 200)
                self.service.update.assert_called_once_with(
                    USER_ID, MEASUREMENT_ID, BodyMeasurementUpdate.model_validate(payload)
                )

    async def test_write_endpoints_reject_missing_malformed_and_nonobject_bodies(self) -> None:
        for method, path in (
            ("POST", "/body_measurements/"),
            ("PATCH", f"/body_measurements/{MEASUREMENT_ID}"),
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

    async def test_invalid_tokens_cannot_call_any_service_method(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_user_repository] = lambda: repo
        for route in self.routes():
            with (
                self.subTest(path=route.path),
                patch("dependencies.auth.decode_token", return_value=None),
                patch("dependencies.auth.logger"),
            ):
                response = await request(
                    app, route.path, route.method, route.payload, {"Authorization": "Bearer invalid-token"}
                )
                self.assertEqual(response.status, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(self.service.mock_calls, [])
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
            (routes[0], BodyMeasurementCreationError.create_failed(), 500),
            (routes[0], BodyMeasurementDateConflictError.already_exists(TODAY), 409),
            (routes[2], BodyMeasurementNotFoundError.no_entries(USER_ID), 404),
            (routes[3], BodyMeasurementNotFoundError.not_found_by_date(TODAY), 404),
            (routes[4], BodyMeasurementNotFoundError.not_found(MEASUREMENT_ID), 404),
            (routes[5], BodyMeasurementNotFoundError.not_accessible(MEASUREMENT_ID), 404),
            (routes[5], BodyMeasurementDateConflictError.already_exists(TODAY), 409),
            (routes[5], BodyMeasurementUpdateError.update_failed(MEASUREMENT_ID), 500),
            (routes[6], BodyMeasurementNotFoundError.not_accessible(MEASUREMENT_ID), 404),
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
                (BodyMeasurementRowError("private row"), "Database operation failed."),
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
        del app.dependency_overrides[get_body_measurement_service]
        repo = create_autospec(BodyMeasurementRepositoryPort, instance=True, spec_set=True)
        app.dependency_overrides[get_body_measurement_repository] = lambda: repo
        repo.get_by_user_and_id.return_value = self.entry
        response = await request(app, f"/body_measurements/{MEASUREMENT_ID}")
        self.assertEqual(response.status, 200)
        repo.get_by_user_and_id.assert_called_once_with(USER_ID, MEASUREMENT_ID)
        repo.get_by_id.assert_not_called()
        repo.get_by_user_and_id.return_value = None
        for method in ("PATCH", "DELETE"):
            response = await request(
                app, f"/body_measurements/{MEASUREMENT_ID}", method, {} if method == "PATCH" else None
            )
            self.assertEqual(response.status, 404)
        repo.update_owned.assert_not_called()
        repo.delete_owned.assert_not_called()
        repo.get_by_user_and_date.return_value = None
        repo.create.side_effect = BodyMeasurementDateConflictRepositoryError(TODAY)
        response = await request(app, "/body_measurements/", "POST", self.create_payload())
        self.assertEqual(response.status, 409)
        self.assertEqual(
            response.payload, {"detail": str(BodyMeasurementDateConflictError.already_exists(TODAY))}
        )

    def test_repository_provider_is_typed_and_does_not_open_a_connection(self) -> None:
        with patch("data.executor.get_connection") as connect:
            self.assertIsInstance(get_body_measurement_repository(), BodyMeasurementRepository)
        connect.assert_not_called()

    async def test_openapi_documents_routes_security_parameters_and_responses(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        for method, path, status_code in (
            ("post", "/body_measurements/", "201"),
            ("get", "/body_measurements/", "200"),
            ("get", "/body_measurements/latest", "200"),
            ("get", "/body_measurements/date/{entry_date}", "200"),
            ("get", "/body_measurements/{entry_id}", "200"),
            ("patch", "/body_measurements/{entry_id}", "200"),
            ("delete", "/body_measurements/{entry_id}", "204"),
        ):
            with self.subTest(method=method, path=path):
                operation = paths[path][method]
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
                if method == "get" and path == "/body_measurements/":
                    self.assertEqual(set(params), {"limit", "offset", "date_from", "date_to"})
                    self.assertTrue(all(parameter["in"] == "query" for parameter in params.values()))
                    self.assertNotIn("requestBody", operation)
