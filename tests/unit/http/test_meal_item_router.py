"""Registered meal-item HTTP contracts, validation, authentication, and ownership."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, call, create_autospec, patch

from auth.jwt_handler import TokenPayload
from core.errors.database import DatabaseError
from core.errors.meal import MealNotFoundError
from core.errors.meal_item import (
    MealItemCreationError,
    MealItemDeleteError,
    MealItemNotFoundError,
    MealItemUpdateError,
)
from core.errors.repository import MealItemRepositoryError, MealItemRowError, MealRepositoryError, MealRowError
from dependencies.auth import get_current_user
from dependencies.providers import (
    get_meal_item_repository,
    get_meal_item_service,
    get_meal_repository,
    get_user_repository,
)
from main import app
from ports.repositories.meal_item_repository import MealItemRepositoryPort
from ports.repositories.meal_repository import MealRepositoryPort
from ports.repositories.user_repository import UserRepositoryPort
from repositories.meal_item_repository import MealItemRepository
from schemas.meal_item_schema import MealItemCreate, MealItemUpdate
from services.meal_item_service import MealItemService
from tests.fixtures import MEAL_ID, MEAL_ITEM_ID, USER_ID, meal, meal_item, user
from tests.unit.http.test_exception_handlers import HttpResponse, request

if TYPE_CHECKING:
    from schemas.meal_item_schema import MealItemPublic
    from schemas.user_schema import UserInternal


@dataclass(frozen=True)
class RouteCase:
    """A valid request and the service operation it should reach."""

    method: str
    path: str
    service_method: str
    payload: dict[str, object] | None = None
    status: int = 200


class MealItemRouterTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = user()
        self.item = meal_item()
        self.collection = f"/meals/{MEAL_ID}/meal_items/"
        self.detail = f"{self.collection}{MEAL_ITEM_ID}"
        self.service = create_autospec(MealItemService, instance=True, spec_set=True)
        for method in ("create", "get_by_id", "update"):
            getattr(self.service, method).return_value = self.item
        self.service.list_by_meal.return_value = [self.item]
        self.service.delete.return_value = None
        self.enterContext(
            patch.dict(
                app.dependency_overrides,
                {get_current_user: lambda: self.user, get_meal_item_service: lambda: self.service},
                clear=True,
            )
        )

    def create_payload(self) -> dict[str, object]:
        return {
            "meal_id": MEAL_ID,
            "name": "Oats",
            "serving_size": "50.25",
            "calories": "190.75",
            "protein": "6.50",
            "carbs": "33.25",
            "fats": "3.75",
        }

    def routes(self) -> tuple[RouteCase, ...]:
        return (
            RouteCase("POST", self.collection, "create", self.create_payload(), 201),
            RouteCase("GET", self.detail, "get_by_id"),
            RouteCase("GET", self.collection, "list_by_meal"),
            RouteCase("PATCH", self.detail, "update", {"calories": "0"}),
            RouteCase("DELETE", self.detail, "delete", status=204),
        )

    def assert_validation_error(self, response: HttpResponse, location: tuple[str | int, ...]) -> None:
        self.assertEqual(response.status, 422)
        payload = cast("dict[str, list[dict[str, object]]]", response.payload)
        self.assertIn(list(location), [error["loc"] for error in payload["detail"]])
        self.assertEqual(self.service.mock_calls, [])

    def use_real_service(self) -> tuple[Mock, Mock]:
        """Keep the real service provider and replace only its two repositories."""
        del app.dependency_overrides[get_meal_item_service]
        meals = create_autospec(MealRepositoryPort, instance=True, spec_set=True)
        items = create_autospec(MealItemRepositoryPort, instance=True, spec_set=True)
        meals.get_by_user_and_id.return_value = meal()
        items.create.return_value = self.item
        items.get_by_meal_and_id.return_value = self.item
        items.list_by_meal.return_value = [self.item]
        items.update_in_meal.return_value = self.item
        items.delete_in_meal.return_value = True
        app.dependency_overrides[get_meal_repository] = lambda: meals
        app.dependency_overrides[get_meal_item_repository] = lambda: items
        self.enterContext(patch("services.meal_item_service.logging.getLogger"))
        return meals, items

    async def test_all_routes_return_expected_status_models_and_authenticated_service_arguments(self) -> None:
        expected_calls = (
            call.create(USER_ID, MealItemCreate.model_validate(self.create_payload())),
            call.get_by_id(USER_ID, MEAL_ID, MEAL_ITEM_ID),
            call.list_by_meal(USER_ID, MEAL_ID),
            call.update(USER_ID, MEAL_ID, MEAL_ITEM_ID, MealItemUpdate(calories=Decimal("0"))),
            call.delete(USER_ID, MEAL_ID, MEAL_ITEM_ID),
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
                    item = self.item.model_dump(mode="json")
                    self.assertEqual(
                        response.payload, [item] if route.service_method == "list_by_meal" else item
                    )
                    self.assertEqual(response.headers["content-type"], "application/json")

    async def test_lists_preserve_empty_single_and_multiple_results_without_pagination(self) -> None:
        another = self.item.model_copy(update={"id": MEAL_ITEM_ID + 1, "name": "Rice"})
        cases: tuple[list[MealItemPublic], ...] = ([], [self.item], [self.item, another])
        for entries in cases:
            with self.subTest(size=len(entries)):
                self.service.reset_mock()
                self.service.list_by_meal.return_value = entries
                response = await request(app, f"{self.collection}?limit=1&offset=999")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [item.model_dump(mode="json") for item in entries])
                self.service.list_by_meal.assert_called_once_with(USER_ID, MEAL_ID)

    async def test_invalid_meal_path_ids_are_rejected_on_every_route(self) -> None:
        for route in self.routes():
            for invalid in ("0", "-1", "bad", "1.5", "NaN"):
                with self.subTest(method=route.method, invalid=invalid):
                    self.service.reset_mock()
                    path = route.path.replace(f"/meals/{MEAL_ID}/", f"/meals/{invalid}/")
                    response = await request(app, path, route.method, route.payload)
                    self.assert_validation_error(response, ("path", "meal_id"))

    async def test_invalid_item_path_ids_are_rejected_for_get_patch_and_delete(self) -> None:
        for method in ("GET", "PATCH", "DELETE"):
            for invalid in ("0", "-1", "bad", "1.5", "NaN"):
                with self.subTest(method=method, invalid=invalid):
                    response = await request(
                        app, f"{self.collection}{invalid}", method, {} if method == "PATCH" else None
                    )
                    self.assert_validation_error(response, ("path", "meal_item_id"))

    async def test_create_rejects_missing_invalid_or_mismatched_body_meal_ids(self) -> None:
        for value in (None, 0, -1, "bad", 1.5, MEAL_ID + 1):
            with self.subTest(value=value):
                payload = {**self.create_payload(), "meal_id": value}
                response = await request(app, self.collection, "POST", payload)
                self.assert_validation_error(response, ("body", "meal_id"))
        payload = self.create_payload()
        del payload["meal_id"]
        self.assert_validation_error(await request(app, self.collection, "POST", payload), ("body", "meal_id"))

    async def test_create_cannot_use_a_valid_body_meal_to_bypass_a_different_path(self) -> None:
        meals, items = self.use_real_service()
        for parent in (MEAL_ID + 1, 999):
            response = await request(app, f"/meals/{parent}/meal_items/", "POST", self.create_payload())
            self.assert_validation_error(response, ("body", "meal_id"))
        meals.get_by_user_and_id.assert_not_called()
        self.assertEqual(items.mock_calls, [])

    async def test_create_requires_each_nonnullable_field(self) -> None:
        for field in ("name", "calories", "protein", "carbs", "fats"):
            for omitted in (True, False):
                with self.subTest(field=field, omitted=omitted):
                    payload = self.create_payload()
                    if omitted:
                        del payload[field]
                    else:
                        payload[field] = None
                    self.assert_validation_error(
                        await request(app, self.collection, "POST", payload), ("body", field)
                    )

    async def test_name_boundaries_are_checked_for_create_and_update(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            ("A", True),
            ("x" * 100, True),
            ("Овес", True),
            ("Oats'; DROP TABLE meals; --", True),
            ("", False),
            ("x" * 101, False),
            (1, False),
            (True, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for value, valid in cases:
                with self.subTest(method=method, value=value):
                    self.service.reset_mock()
                    payload: dict[str, object] = (
                        {**self.create_payload(), "name": value} if method == "POST" else {"name": value}
                    )
                    response = await request(app, path, method, payload)
                    if valid:
                        self.assertEqual(response.status, 201 if method == "POST" else 200)
                    else:
                        self.assert_validation_error(response, ("body", "name"))

    async def test_all_decimal_fields_accept_zero_and_numbers_and_reject_invalid_values(self) -> None:
        cases: tuple[tuple[object, bool], ...] = (
            (0, True),
            ("0", True),
            ("0.01", True),
            (1, True),
            (12.5, True),
            ("12.5000", True),
            (-1, False),
            ("-0.01", False),
            ("bad", False),
            ("NaN", False),
            ("Infinity", False),
            ("-Infinity", False),
            (True, False),
            (False, False),
            (list[object](), False),
            (dict[str, object](), False),
        )
        for field in ("serving_size", "calories", "protein", "carbs", "fats"):
            for method, path in (("POST", self.collection), ("PATCH", self.detail)):
                for value, valid in cases:
                    with self.subTest(field=field, method=method, value=value):
                        self.service.reset_mock()
                        payload: dict[str, object] = (
                            {**self.create_payload(), field: value} if method == "POST" else {field: value}
                        )
                        response = await request(app, path, method, payload)
                        if valid:
                            self.assertEqual(response.status, 201 if method == "POST" else 200)
                            if method == "POST":
                                self.service.create.assert_called_once_with(
                                    USER_ID, MealItemCreate.model_validate(payload)
                                )
                            else:
                                self.service.update.assert_called_once_with(
                                    USER_ID, MEAL_ID, MEAL_ITEM_ID, MealItemUpdate.model_validate(payload)
                                )
                        else:
                            self.assert_validation_error(response, ("body", field))

    async def test_optional_serving_size_can_be_omitted_or_null_on_creation(self) -> None:
        for omitted in (True, False):
            payload = self.create_payload()
            if omitted:
                del payload["serving_size"]
            else:
                payload["serving_size"] = None
            self.service.reset_mock()
            response = await request(app, self.collection, "POST", payload)
            self.assertEqual(response.status, 201)
            self.service.create.assert_called_once_with(USER_ID, MealItemCreate.model_validate(payload))

    async def test_update_accepts_empty_null_partial_and_full_payloads(self) -> None:
        payloads: tuple[dict[str, object], ...] = (
            {},
            {
                "name": None,
                "serving_size": None,
                "calories": None,
                "protein": None,
                "carbs": None,
                "fats": None,
            },
            {"name": "Rice"},
            {"serving_size": None, "calories": 0},
            {
                "name": "Rice",
                "serving_size": "0",
                "calories": "0",
                "protein": "1.25",
                "carbs": "2.50",
                "fats": "0",
            },
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.service.reset_mock()
                response = await request(app, self.detail, "PATCH", payload)
                self.assertEqual(response.status, 200)
                self.service.update.assert_called_once_with(
                    USER_ID, MEAL_ID, MEAL_ITEM_ID, MealItemUpdate.model_validate(payload)
                )

    async def test_malformed_missing_and_nonobject_bodies_are_rejected(self) -> None:
        for method, path in (("POST", self.collection), ("PATCH", self.detail)):
            for body in (b"", b"{", b"null", b"[]", b"1", b'"text"'):
                with self.subTest(method=method, body=body):
                    response = await request(app, path, method, raw_body=body)
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

    async def test_authenticated_user_and_parent_cannot_be_overridden_by_query_or_update_fields(self) -> None:
        del app.dependency_overrides[get_current_user]
        repo = create_autospec(UserRepositoryPort, instance=True, spec_set=True)
        repo.get_by_id.return_value = self.user
        app.dependency_overrides[get_user_repository] = lambda: repo
        token = TokenPayload(str(USER_ID), 0, 1, "test", "access", "test_user", self.user.token_version)
        for route in self.routes():
            with self.subTest(method=route.method), patch("dependencies.auth.decode_token", return_value=token):
                self.service.reset_mock()
                payload = {**route.payload, "user_id": 999} if route.payload is not None else None
                if route.method == "PATCH":
                    payload = {**(payload or {}), "meal_id": 999, "id": 999}
                response = await request(
                    app,
                    f"{route.path}?user_id=999&meal_id=999&meal_item_id=999",
                    route.method,
                    payload,
                    {"Authorization": "Bearer valid-token"},
                )
                self.assertEqual(response.status, route.status)
                arguments = getattr(self.service, route.service_method).call_args.args
                self.assertEqual(arguments[0], USER_ID)
                if route.method == "POST":
                    self.assertEqual(arguments[1].meal_id, MEAL_ID)
                else:
                    self.assertEqual(arguments[1], MEAL_ID)
                if route.method == "PATCH":
                    self.assertEqual(arguments[2], MEAL_ITEM_ID)
                    self.assertNotIn("meal_id", arguments[3].model_dump())

    async def test_registered_service_errors_keep_expected_statuses_and_messages(self) -> None:
        cases = (
            (self.routes()[0], MealItemCreationError.create_failed(), 500),
            (self.routes()[1], MealItemNotFoundError.not_in_meal(MEAL_ITEM_ID, MEAL_ID), 404),
            (self.routes()[3], MealItemUpdateError.update_failed(MEAL_ITEM_ID), 500),
            (self.routes()[4], MealItemDeleteError.delete_failed(MEAL_ITEM_ID), 500),
        )
        for route, error, expected in cases:
            with self.subTest(method=route.method), patch("core.exception_handlers.logger"):
                self.service.reset_mock(side_effect=True)
                getattr(self.service, route.service_method).side_effect = error
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, expected)
                self.assertEqual(response.payload, {"detail": str(error)})
        for route in self.routes():
            self.service.reset_mock(side_effect=True)
            error = MealNotFoundError.not_accessible(MEAL_ID)
            getattr(self.service, route.service_method).side_effect = error
            response = await request(app, route.path, route.method, route.payload)
            self.assertEqual(response.status, 404)
            self.assertEqual(response.payload, {"detail": str(error)})

    async def test_internal_errors_are_sanitized_on_every_route(self) -> None:
        for route in self.routes():
            for error, detail in (
                (DatabaseError("private SQL"), "Database operation failed."),
                (MealItemRepositoryError("private query"), "Database operation failed."),
                (MealItemRowError("private row"), "Database operation failed."),
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

    async def test_real_providers_perform_owned_parent_and_scoped_item_lookups(self) -> None:
        meals, items = self.use_real_service()
        for route in self.routes():
            with self.subTest(method=route.method):
                meals.reset_mock()
                items.reset_mock()
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, route.status)
                meals.get_by_user_and_id.assert_called_once_with(USER_ID, MEAL_ID)
                if route.method in {"GET", "PATCH", "DELETE"} and route.path == self.detail:
                    items.get_by_meal_and_id.assert_called_once_with(MEAL_ID, MEAL_ITEM_ID)
                items.get_by_id.assert_not_called()

    async def test_real_service_rejects_unowned_parents_before_any_item_access(self) -> None:
        meals, items = self.use_real_service()
        meals.get_by_user_and_id.return_value = None
        for route in self.routes():
            with self.subTest(method=route.method):
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 404)
                self.assertEqual(response.payload, {"detail": str(MealNotFoundError.not_accessible(MEAL_ID))})
                self.assertEqual(items.mock_calls, [])

    async def test_real_service_rejects_missing_or_wrong_meal_items_before_mutations(self) -> None:
        _meals, items = self.use_real_service()
        items.get_by_meal_and_id.return_value = None
        for method in ("GET", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = await request(app, self.detail, method, {} if method == "PATCH" else None)
                self.assertEqual(response.status, 404)
                self.assertEqual(
                    response.payload, {"detail": str(MealItemNotFoundError.not_in_meal(MEAL_ITEM_ID, MEAL_ID))}
                )
        items.update_in_meal.assert_not_called()
        items.delete_in_meal.assert_not_called()
        items.get_by_id.assert_not_called()

    async def test_real_service_translates_write_failures_and_sanitizes_causes(self) -> None:
        _meals, items = self.use_real_service()
        for route, method, error in (
            (self.routes()[0], "create", MealItemCreationError.create_failed()),
            (self.routes()[3], "update_in_meal", MealItemUpdateError.update_failed(MEAL_ITEM_ID)),
            (self.routes()[4], "delete_in_meal", MealItemDeleteError.delete_failed(MEAL_ITEM_ID)),
        ):
            with (
                self.subTest(method=method),
                patch.object(items, method, side_effect=MealItemRepositoryError("private SQL")),
                patch("core.exception_handlers.logger"),
            ):
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": str(error)})
                self.assertNotIn("private", str(response.payload))

    async def test_disappearing_items_and_repeated_delete_return_404_after_empty_204(self) -> None:
        _meals, items = self.use_real_service()
        items.update_in_meal.return_value = None
        response = await request(app, self.detail, "PATCH", {})
        self.assertEqual(response.status, 404)
        items.delete_in_meal.return_value = False
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 404)
        items.delete_in_meal.return_value = True
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 204)
        self.assertEqual(response.body, b"")
        items.get_by_meal_and_id.return_value = None
        response = await request(app, self.detail, "DELETE")
        self.assertEqual(response.status, 404)
        self.assertEqual(items.delete_in_meal.call_count, 2)

    async def test_parent_lookup_failures_are_server_errors_without_accessing_items(self) -> None:
        meals, items = self.use_real_service()
        for error in (
            DatabaseError("private SQL"),
            MealRepositoryError("private meal"),
            MealRowError("private row"),
        ):
            for route in self.routes():
                with (
                    self.subTest(method=route.method, error=type(error).__name__),
                    patch("core.exception_handlers.logger"),
                ):
                    meals.get_by_user_and_id.side_effect = error
                    response = await request(app, route.path, route.method, route.payload)
                    self.assertEqual(response.status, 500)
                    self.assertEqual(response.payload, {"detail": "Database operation failed."})
                    self.assertEqual(items.mock_calls, [])

    async def test_invalid_service_response_models_return_sanitized_500(self) -> None:
        for route in self.routes()[:-1]:
            with self.subTest(method=route.method, path=route.path), patch("core.exception_handlers.logger"):
                getattr(self.service, route.service_method).return_value = None
                response = await request(app, route.path, route.method, route.payload)
                self.assertEqual(response.status, 500)
                self.assertEqual(response.payload, {"detail": "Internal server error."})

    def test_repository_and_service_providers_do_not_open_database_connections(self) -> None:
        with patch("data.executor.get_connection") as connect:
            items = get_meal_item_repository()
            meals = get_meal_repository()
            service = get_meal_item_service(meals, items)
            self.assertIsInstance(items, MealItemRepository)
            self.assertIs(service.meal_repo, meals)
            self.assertIs(service.meal_item_repo, items)
        connect.assert_not_called()

    async def test_openapi_documents_all_routes_security_parameters_and_responses(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        for method, path, success in (
            ("post", "/meals/{meal_id}/meal_items/", "201"),
            ("get", "/meals/{meal_id}/meal_items/", "200"),
            ("get", "/meals/{meal_id}/meal_items/{meal_item_id}", "200"),
            ("patch", "/meals/{meal_id}/meal_items/{meal_item_id}", "200"),
            ("delete", "/meals/{meal_id}/meal_items/{meal_item_id}", "204"),
        ):
            with self.subTest(method=method, path=path):
                operation = paths[path][method]
                self.assertEqual(operation["tags"], ["meal_items"])
                self.assertTrue(operation["security"])
                description = cast("str", operation["description"])
                for section in ("Args:", "Returns:", "Raises:"):
                    self.assertIn(section, description)
                responses = cast("dict[str, dict[str, object]]", operation["responses"])
                self.assertTrue({success, "401", "404", "422", "500"}.issubset(responses))
                if method == "delete":
                    self.assertNotIn("content", responses[success])
                if method in {"post", "patch"}:
                    self.assertTrue(cast("dict[str, object]", operation["requestBody"])["required"])
                params = cast("list[dict[str, object]]", operation["parameters"])
                expected = {"meal_id", "meal_item_id"} if path.endswith("{meal_item_id}") else {"meal_id"}
                self.assertEqual({parameter["name"] for parameter in params}, expected)
                for parameter in params:
                    self.assertEqual(parameter["in"], "path")
                    self.assertTrue(parameter["required"])
                    self.assertEqual(cast("dict[str, object]", parameter["schema"])["exclusiveMinimum"], 0)
