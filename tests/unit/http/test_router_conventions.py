"""Shared router validation and published HTTP contracts across application resources."""

from __future__ import annotations

from typing import cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from dependencies import providers
from dependencies.auth import get_current_user
from main import app
from tests.fixtures import ENTRY_ID, EXERCISE_ID, MEAL_ID, MEAL_ITEM_ID, WORKOUT_ID, user
from tests.unit.http.test_exception_handlers import request


class RouterConventionTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = Mock()
        self.enterContext(
            patch.dict(
                app.dependency_overrides,
                {
                    get_current_user: user,
                    providers.get_user_service: lambda: self.service,
                    providers.get_user_goals_service: lambda: self.service,
                    providers.get_exercise_service: lambda: self.service,
                    providers.get_meal_service: lambda: self.service,
                    providers.get_workout_service: lambda: self.service,
                    providers.get_workout_exercise_service: lambda: self.service,
                    providers.get_set_entry_service: lambda: self.service,
                    providers.get_meal_item_service: lambda: self.service,
                    providers.get_body_measurement_service: lambda: self.service,
                    providers.get_body_weight_entry_service: lambda: self.service,
                    providers.get_progress_photo_service: lambda: self.service,
                },
                clear=True,
            )
        )

    async def test_nonpositive_and_invalid_ids_are_rejected_before_business_operations(self) -> None:
        cases: list[tuple[str, str, str, dict[str, object] | None]] = []
        for resource, field in (
            ("exercises", "exercise_id"),
            ("meals", "meal_id"),
            ("workouts", "workout_id"),
            ("goals", "goal_id"),
            ("body_measurements", "entry_id"),
            ("body_weight_entries", "entry_id"),
            ("progress_photos", "photo_id"),
        ):
            for method in ("GET", "PATCH", "DELETE"):
                if resource == "goals" and method == "DELETE":
                    continue
                cases.append((method, f"/{resource}/{{id}}", field, {} if method == "PATCH" else None))
        cases.extend(
            [
                ("POST", "/goals/{id}/activate", "goal_id", None),
                ("POST", "/goals/{id}/deactivate", "goal_id", None),
                ("GET", "/sets/{id}", "set_entry_id", None),
                ("PATCH", f"/sets/{{id}}?workout_exercise_id={ENTRY_ID}", "set_entry_id", {}),
                ("DELETE", f"/sets/{{id}}?workout_exercise_id={ENTRY_ID}", "set_entry_id", None),
                ("GET", "/sets/workout_exercise/{id}", "workout_exercise_id", None),
                (
                    "POST",
                    "/workouts/{id}/exercises/",
                    "workout_id",
                    {"exercise_id": EXERCISE_ID, "order_index": 0},
                ),
                ("GET", "/workouts/{id}/exercises/", "workout_id", None),
                ("GET", "/meals/{id}/meal_items/", "meal_id", None),
                (
                    "POST",
                    "/meals/{id}/meal_items/",
                    "meal_id",
                    {"meal_id": MEAL_ID, "name": "Oats", "calories": 0, "protein": 0, "carbs": 0, "fats": 0},
                ),
            ]
        )
        for method in ("GET", "PATCH", "DELETE"):
            payload: dict[str, object] | None = {} if method == "PATCH" else None
            cases.extend(
                [
                    (method, f"/workouts/{{id}}/exercises/{ENTRY_ID}", "workout_id", payload),
                    (method, f"/workouts/{WORKOUT_ID}/exercises/{{id}}", "workout_exercise_id", payload),
                    (method, f"/meals/{{id}}/meal_items/{MEAL_ITEM_ID}", "meal_id", payload),
                    (method, f"/meals/{MEAL_ID}/meal_items/{{id}}", "meal_item_id", payload),
                ]
            )
        for method, template, field, payload in cases:
            for value in ("0", "-1", "bad", "1.5"):
                with self.subTest(method=method, template=template, value=value):
                    response = await request(app, template.format(id=value), method, payload)
                    self.assertEqual(response.status, 422)
                    body = cast("dict[str, list[dict[str, object]]]", response.payload)
                    self.assertIn(["path", field], [error["loc"] for error in body["detail"]])
                    self.assertEqual(self.service.mock_calls, [])

    async def test_openapi_has_one_tag_and_structured_docs_for_every_resource_operation(self) -> None:
        response = await request(app, "/openapi.json")
        self.assertEqual(response.status, 200)
        document = cast("dict[str, object]", response.payload)
        paths = cast("dict[str, dict[str, dict[str, object]]]", document["paths"])
        operation_ids: set[str] = set()
        for path, methods in paths.items():
            if path == "/":
                continue
            for method, operation in methods.items():
                with self.subTest(path=path, method=method):
                    self.assertEqual(len(cast("list[str]", operation["tags"])), 1)
                    description = cast("str", operation["description"])
                    for section in ("Args:", "Returns:", "Raises:"):
                        self.assertIn(section, description)
                    responses = cast("dict[str, dict[str, object]]", operation["responses"])
                    self.assertIn("500", responses)
                    if operation.get("security"):
                        self.assertIn("401", responses)
                    operation_id = cast("str", operation["operationId"])
                    self.assertNotIn(operation_id, operation_ids)
                    operation_ids.add(operation_id)
                    if method == "delete" or (path.endswith("/change-password") and method == "post"):
                        self.assertIn("204", responses)
                        self.assertNotIn("content", responses["204"])
