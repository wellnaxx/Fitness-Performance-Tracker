"""Fresh, validated models for service tests; IDs differ to catch argument swaps."""

from datetime import date, datetime
from decimal import Decimal

from schemas.exercise_schema import ExercisePublic
from schemas.meal_schema import MealPublic
from schemas.user_goals_schema import UserGoalPublic
from schemas.user_schema import UserInternal
from schemas.workout_exercises_schema import WorkoutExercisePublic
from schemas.workout_schema import WorkoutPublic

NOW = datetime(2026, 10, 1, 12)
TODAY = NOW.date()
USER_ID = 7
WORKOUT_ID = 11
EXERCISE_ID = 13
ENTRY_ID = 17
GOAL_ID = 19
MEAL_ID = 23


def user() -> UserInternal:
    return UserInternal.model_validate(
        {
            "id": USER_ID,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": date(2000, 1, 1),
            "email": "test@example.com",
            "password_hash": "stored-hash",
            "profile_picture_url": None,
            "token_version": 2,
            "weight_unit_preference": "kg",
            "measurement_unit_preference": "cm",
            "created_at": NOW,
            "updated_at": NOW,
        }
    )


def workout() -> WorkoutPublic:
    return WorkoutPublic(
        id=WORKOUT_ID,
        user_id=USER_ID,
        name="Strength",
        workout_date=TODAY,
        created_at=NOW,
        updated_at=NOW,
    )


def exercise() -> ExercisePublic:
    return ExercisePublic(
        id=EXERCISE_ID,
        name="Squat",
        muscle_group="Legs",
        is_compound=True,
        is_custom=True,
        created_by=USER_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def entry() -> WorkoutExercisePublic:
    return WorkoutExercisePublic(
        id=ENTRY_ID,
        workout_id=WORKOUT_ID,
        exercise_id=EXERCISE_ID,
        order_index=0,
        rest_seconds=60,
    )


def goal() -> UserGoalPublic:
    return UserGoalPublic(
        id=GOAL_ID,
        user_id=USER_ID,
        daily_calorie_target=2000,
        protein_target=150,
        carbs_target=200,
        fat_target=60,
        weekly_workout_target=3,
        target_body_weight=Decimal("75.5"),
        start_date=TODAY,
        end_date=date(2026, 10, 31),
    )


def meal() -> MealPublic:
    return MealPublic(
        id=MEAL_ID,
        user_id=USER_ID,
        name="Oatmeal",
        eaten_at=NOW,
        meal_type="breakfast",
        created_at=NOW,
        updated_at=NOW,
    )
