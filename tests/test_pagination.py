"""Shared pagination bounds and their SQL and HTTP contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch

from fastapi import FastAPI

from dependencies.auth import get_current_user
from dependencies.providers import (
    get_exercise_service,
    get_meal_service,
    get_user_goals_service,
    get_workout_service,
)
from repositories.body_measurement_repository import BodyMeasurementRepository
from repositories.body_weight_entry_repository import BodyWeightEntryRepository
from repositories.exercise_repository import ExerciseRepository
from repositories.meal_repository import MealRepository
from repositories.progress_photo_repository import ProgressPhotoRepository
from repositories.user_goals_repository import UserGoalsRepository
from repositories.user_repository import UserRepository
from repositories.workout_repository import WorkoutRepository
from routers.api.exercise_router import exercise_router
from routers.api.meal_router import meal_router
from routers.api.user_goals_router import user_goals_router
from routers.api.workout_router import workout_router
from tests.fixtures import TODAY, USER_ID, exercise, goal, meal, user, workout
from tests.test_exception_handlers import request
from utils.pagination import PaginationParams, normalize_pagination

if TYPE_CHECKING:
    from collections.abc import Callable


class PaginationTests(TestCase):
    def test_default_page_preserves_existing_values(self) -> None:
        self.assertEqual(PaginationParams(), PaginationParams(limit=100, offset=0))
        self.assertEqual(normalize_pagination(), PaginationParams(limit=100, offset=0))

    def test_normalization_preserves_valid_values_and_clamps_out_of_range_values(self) -> None:
        cases = (
            (1, 0, 1, 0),
            (1000, 0, 1000, 0),
            (10, 25, 10, 25),
            (0, 0, 1, 0),
            (-10, -5, 1, 0),
            (1001, -1, 1000, 0),
            (10**20, 10**20, 1000, 10**20),
        )
        for limit, offset, expected_limit, expected_offset in cases:
            with self.subTest(limit=limit, offset=offset):
                self.assertEqual(
                    normalize_pagination(limit, offset), PaginationParams(expected_limit, expected_offset)
                )


class RepositoryPaginationTests(TestCase):
    def listings(self) -> tuple[tuple[str, Callable[..., object], tuple[int, ...]], ...]:
        return (
            ("body_measurement_repository", BodyMeasurementRepository().list_by_user, (USER_ID,)),
            ("body_weight_entry_repository", BodyWeightEntryRepository().list_by_user, (USER_ID,)),
            ("exercise_repository", ExerciseRepository().list_visible, (USER_ID,)),
            ("meal_repository", MealRepository().list_by_user, (USER_ID,)),
            ("progress_photo_repository", ProgressPhotoRepository().list_by_user, (USER_ID,)),
            ("user_goals_repository.default_executor", UserGoalsRepository().get_all, (USER_ID,)),
            ("user_repository", UserRepository().get_all, ()),
            ("workout_repository", WorkoutRepository().list_by_user, (USER_ID,)),
            ("workout_repository", WorkoutRepository().get_all_visible_for_user, (USER_ID,)),
        )

    def test_every_paginated_repository_binds_shared_defaults(self) -> None:
        for module, listing, args in self.listings():
            with self.subTest(module=module, method=listing.__name__):
                with patch(f"repositories.{module}.fetch_all", return_value=[]) as fetch:
                    self.assertEqual(listing(*args), [])
                sql, params = fetch.call_args.args
                self.assertEqual(params, (*args, 100, 0))
                self.assertIn("LIMIT %s OFFSET %s", " ".join(sql.split()))
                self.assertEqual(sql.count("%s"), len(params))

    def test_every_paginated_repository_binds_normalized_values(self) -> None:
        for module, listing, args in self.listings():
            for limit, offset, expected in (
                (0, -1, (1, 0)),
                (-100, -100, (1, 0)),
                (1001, 25, (1000, 25)),
                (1, 0, (1, 0)),
                (1000, 50, (1000, 50)),
                (12, 10**12, (12, 10**12)),
            ):
                with self.subTest(module=module, method=listing.__name__, limit=limit, offset=offset):
                    with patch(f"repositories.{module}.fetch_all", return_value=[]) as fetch:
                        self.assertEqual(listing(*args, limit=limit, offset=offset), [])
                    sql, params = fetch.call_args.args
                    self.assertEqual(params, (*args, *expected))
                    self.assertEqual(sql.count("%s"), len(params))


class HttpPaginationTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        for router in (exercise_router, meal_router, user_goals_router, workout_router):
            self.app.include_router(router)
        self.user = user()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.exercises = Mock()
        self.meals = Mock()
        self.goals = Mock()
        self.workouts = Mock()
        self.exercises.list_visible_by_user.return_value = []
        self.meals.list_visible_by_user.return_value = []
        self.goals.get_goal_history.return_value = []
        self.workouts.list_visible_by_user.return_value = []
        self.app.dependency_overrides[get_exercise_service] = lambda: self.exercises
        self.app.dependency_overrides[get_meal_service] = lambda: self.meals
        self.app.dependency_overrides[get_user_goals_service] = lambda: self.goals
        self.app.dependency_overrides[get_workout_service] = lambda: self.workouts
        self.routes: tuple[tuple[str, Mock], ...] = (
            ("/exercises/", self.exercises.list_visible_by_user),
            ("/meals/", self.meals.list_visible_by_user),
            ("/goals/history", self.goals.get_goal_history),
            ("/workouts/", self.workouts.list_visible_by_user),
        )

    def assert_page_forwarded(self, path: str, method: Mock, limit: int, offset: int) -> None:
        method.assert_called_once()
        if path == "/goals/history":
            method.assert_called_once_with(self.user, limit, offset)
        else:
            self.assertEqual(method.call_args.kwargs["limit"], limit)
            self.assertEqual(method.call_args.kwargs["offset"], offset)
            if path == "/workouts/":
                self.assertEqual(method.call_args.args, (USER_ID,))
            else:
                self.assertEqual(method.call_args.kwargs["user_id"], USER_ID)

    async def test_all_list_routes_keep_defaults_and_empty_list_responses(self) -> None:
        for path, method in self.routes:
            with self.subTest(path=path):
                response = await request(self.app, path)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [])
                self.assert_page_forwarded(path, method, 100, 0)

    async def test_all_list_routes_accept_boundaries_and_partial_pagination(self) -> None:
        for path, method in self.routes:
            for query, limit, offset in (
                ("limit=1", 1, 0),
                ("limit=1000&offset=5", 1000, 5),
                ("offset=7", 100, 7),
                ("limit=12&offset=1000000000000", 12, 10**12),
            ):
                with self.subTest(path=path, query=query):
                    method.reset_mock()
                    response = await request(self.app, f"{path}?{query}")
                    self.assertEqual(response.status, 200)
                    self.assert_page_forwarded(path, method, limit, offset)

    async def test_invalid_pagination_is_422_before_any_listing_call(self) -> None:
        for path, method in self.routes:
            for query, field in (
                ("limit=0", "limit"),
                ("limit=-1", "limit"),
                ("limit=1001", "limit"),
                ("offset=-1", "offset"),
                ("limit=abc", "limit"),
                ("offset=abc", "offset"),
                ("limit=1.5", "limit"),
                ("offset=1.5", "offset"),
                ("limit=", "limit"),
                ("offset=", "offset"),
            ):
                with self.subTest(path=path, query=query):
                    method.reset_mock()
                    response = await request(self.app, f"{path}?{query}")
                    self.assertEqual(response.status, 422)
                    payload = cast("dict[str, object]", response.payload)
                    details = cast("list[dict[str, object]]", payload["detail"])
                    self.assertIn(["query", field], [detail["loc"] for detail in details])
                    method.assert_not_called()

    async def test_nonempty_pages_keep_existing_array_response_shape(self) -> None:
        for (path, method), item in zip(self.routes, (exercise(), meal(), goal(), workout()), strict=True):
            with self.subTest(path=path):
                method.return_value = [item]
                response = await request(self.app, f"{path}?limit=1")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload, [item.model_dump(mode="json")])

    async def test_pagination_does_not_discard_resource_filters(self) -> None:
        cases: tuple[tuple[str, Mock, dict[str, object]], ...] = (
            (
                "/exercises/?limit=3&offset=2&search=squat&muscle_group=Legs&equipment=Barbell"
                "&is_compound=false&is_custom=false",
                self.exercises.list_visible_by_user,
                {
                    "search": "squat",
                    "muscle_group": "Legs",
                    "equipment": "Barbell",
                    "is_compound": False,
                    "is_custom": False,
                },
            ),
            (
                "/meals/?limit=3&offset=2&date_from=2026-10-01&date_to=2026-10-01&meal_type=LUNCH",
                self.meals.list_visible_by_user,
                {"date_from": TODAY, "date_to": TODAY, "meal_type": "lunch"},
            ),
            (
                "/workouts/?limit=3&offset=2&search=Strength&date_from=2026-10-01&date_to=2026-10-01",
                self.workouts.list_visible_by_user,
                {"search": "Strength", "date_from": TODAY, "date_to": TODAY},
            ),
        )
        for path, method, expected in cases:
            with self.subTest(path=path):
                response = await request(self.app, path)
                self.assertEqual(response.status, 200)
                self.assertEqual(method.call_args.kwargs["limit"], 3)
                self.assertEqual(method.call_args.kwargs["offset"], 2)
                for key, value in expected.items():
                    self.assertEqual(method.call_args.kwargs[key], value)

    def test_openapi_documents_shared_query_bounds_and_defaults_on_every_route(self) -> None:
        paths = self.app.openapi()["paths"]
        for path, _ in self.routes:
            with self.subTest(path=path):
                operation = paths[path]["get"]
                params = {param["name"]: param for param in operation["parameters"]}
                self.assertNotIn("requestBody", operation)
                self.assertEqual(params["limit"]["in"], "query")
                self.assertEqual(params["offset"]["in"], "query")
                self.assertEqual(params["limit"]["schema"]["default"], 100)
                self.assertEqual(params["limit"]["schema"]["minimum"], 1)
                self.assertEqual(params["limit"]["schema"]["maximum"], 1000)
                self.assertEqual(params["offset"]["schema"]["default"], 0)
                self.assertEqual(params["offset"]["schema"]["minimum"], 0)
