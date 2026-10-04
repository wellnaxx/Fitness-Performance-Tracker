"""Services can use typed repository substitutes without PostgreSQL or mocks."""

from datetime import date, datetime
from unittest import TestCase

from core.errors.meal import MealNotFoundError
from dependencies.providers import get_meal_service
from schemas.meal_schema import MealCreate, MealPublic, MealUpdate

NOW = datetime(2026, 10, 1, 12)


class InMemoryMealRepository:
    """Minimal test implementation that satisfies MealRepositoryPort structurally."""

    def __init__(self) -> None:
        self.meals: dict[int, MealPublic] = {}
        self.next_id = 1

    def create(self, user_id: int, meal_data: MealCreate) -> MealPublic:
        meal = MealPublic(
            **meal_data.model_dump(),
            id=self.next_id,
            user_id=user_id,
            created_at=NOW,
            updated_at=NOW,
        )
        self.meals[meal.id] = meal
        self.next_id += 1
        return meal

    def get_by_user_and_id(self, user_id: int, meal_id: int) -> MealPublic | None:
        meal = self.meals.get(meal_id)
        return meal if meal is not None and meal.user_id == user_id else None

    def list_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
        meal_type: str | None = None,
    ) -> list[MealPublic]:
        meals = [
            meal
            for meal in self.meals.values()
            if meal.user_id == user_id
            and (date_from is None or meal.eaten_at.date() >= date_from)
            and (date_to is None or meal.eaten_at.date() <= date_to)
            and (meal_type is None or meal.meal_type == meal_type)
        ]
        meals.sort(key=lambda meal: (meal.eaten_at, meal.id), reverse=True)
        start = max(0, offset)
        return meals[start : start + max(1, min(limit, 1000))]

    def update_owned(self, user_id: int, meal_id: int, update_data: MealUpdate) -> MealPublic | None:
        meal = self.get_by_user_and_id(user_id, meal_id)
        if meal is None:
            return None
        updated = MealPublic.model_validate({**meal.model_dump(), **update_data.model_dump(exclude_none=True)})
        self.meals[meal_id] = updated
        return updated

    def delete_owned(self, user_id: int, meal_id: int) -> bool:
        if self.get_by_user_and_id(user_id, meal_id) is None:
            return False
        del self.meals[meal_id]
        return True


class RepositoryProtocolTests(TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryMealRepository()
        # This call is also a static type check: the fake does not inherit the port
        # or a concrete repository and must implement the required signatures.
        self.service = get_meal_service(self.repository)

    def test_service_can_create_read_update_and_delete_using_a_typed_fake(self) -> None:
        meal = self.service.create_meal(7, MealCreate(name="Lunch", eaten_at=NOW, meal_type="lunch"))
        self.assertEqual(self.service.get_visible_by_user(meal.id, 7), meal)
        updated = self.service.update_meal(meal.id, 7, MealUpdate(name="Updated lunch"))
        self.assertEqual(updated.name, "Updated lunch")
        self.assertEqual(self.service.list_visible_by_user(7), [updated])
        self.service.delete_meal(meal.id, 7)
        self.assertEqual(self.service.list_visible_by_user(7), [])

    def test_service_preserves_ownership_checks_with_a_typed_fake(self) -> None:
        meal = self.service.create_meal(7, MealCreate(name="Lunch", eaten_at=NOW, meal_type="lunch"))
        with self.assertLogs("services.meal_service", level="WARNING"):
            with self.assertRaises(MealNotFoundError):
                self.service.get_visible_by_user(meal.id, 8)
            with self.assertRaises(MealNotFoundError):
                self.service.update_meal(meal.id, 8, MealUpdate(name="Other user's meal"))
            with self.assertRaises(MealNotFoundError):
                self.service.delete_meal(meal.id, 8)
        self.assertEqual(self.service.get_visible_by_user(meal.id, 7), meal)
        self.assertEqual(self.service.list_visible_by_user(8), [])

    def test_service_forwards_filters_and_pagination_to_the_port(self) -> None:
        self.service.create_meal(7, MealCreate(name="Older", eaten_at=NOW.replace(day=1), meal_type="lunch"))
        middle = self.service.create_meal(
            7, MealCreate(name="Middle", eaten_at=NOW.replace(day=2), meal_type="lunch")
        )
        self.service.create_meal(7, MealCreate(name="Newest", eaten_at=NOW.replace(day=3), meal_type="lunch"))
        self.service.create_meal(7, MealCreate(name="Dinner", eaten_at=NOW.replace(day=3), meal_type="dinner"))
        result = self.service.list_visible_by_user(
            7,
            date_from=date(2026, 10, 2),
            date_to=date(2026, 10, 3),
            meal_type="lunch",
            limit=1,
            offset=1,
        )
        self.assertEqual(result, [middle])
